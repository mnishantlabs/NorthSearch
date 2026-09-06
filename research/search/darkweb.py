"""Tor integration and dark web search. Manages Tor process internally."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import socket
import subprocess
import time
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from httpx_socks import AsyncProxyTransport, SyncProxyTransport

from research.config import TorConfig
from research.models import SearchResult, SourceType

logger = logging.getLogger(__name__)

# Known .onion search engines, link directories, and content databases.
# These are regular (non-torrent) services: search portals, archives,
# news indexes, and general content directories reachable via Tor.
AHMIA_SEARCH_URL = "https://ahmia.fi/search/?q={query}"
ONION_SEARCH_DATABASES = [
    # Ahmia is the main clearnet-accessible .onion index.
    ("ahmia", "https://ahmia.fi/search/?q={query}"),
    # Tor66 - general-purpose .onion search
    ("tor66", "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5uwxiisujad.onion/search?q={query}"),
    # Onion Search Engine (dark.fail listed)
    ("onionland", "http://3bbad7fauom4d6sg3alyqe2f2iiv2ltyfyzc2nbqm34h5xkelj5icnad.onion"),
    # Darkness search
    ("darkness", "https://darkness.eqlz3x3zvaykh6b2.onion/?q={query}"),
    # DuckDuckGo .onion mirror
    ("ddgonion", "https://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/?q={query}&ia=web"),
]
ONION_LINK_DIRECTORIES = [
    "http://juhanurmihplp777qz7pyc7gafqqgbvsvuognwbttenxpwidkpwid.onion",
]


class TorManager:
    """Manages the Tor process - auto-downloads, starts, and stops Tor."""

    def __init__(self, config: TorConfig) -> None:
        self.config = config
        self._process: subprocess.Popen | None = None
        self._tor_path: Path | None = None

    @property
    def is_running(self) -> bool:
        """Check if Tor is already running by testing the SOCKS port."""
        try:
            host, port = self._parse_proxy()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            return result == 0
        except Exception:
            return False

    def ensure_running(self) -> str:
        """Ensure Tor is running. Returns the SOCKS proxy URL.

        Priority:
        1. Check if Tor is already running (system service or Tor Browser)
        2. Try to find/start bundled Tor
        3. Try to find/start system-installed Tor
        4. Download and run Tor Expert Bundle (Windows)
        """
        # Already running?
        if self.is_running:
            logger.info("Tor is already running on %s", self.config.socks_proxy)
            return self.config.socks_proxy

        if not self.config.auto_manage:
            raise ConnectionError(
                "Tor is not running and auto_manage is disabled. "
                "Start Tor manually or set auto_manage=True."
            )

        # Try to find and start Tor
        tor_path = self._find_tor_binary()
        if tor_path:
            self._start_tor(tor_path)
            return self.config.socks_proxy

        # Try to download Tor Expert Bundle (Windows)
        if platform.system() == "Windows":
            tor_path = self._download_tor_windows()
            if tor_path:
                self._start_tor(tor_path)
                return self.config.socks_proxy

        raise ConnectionError(
            "Could not find or start Tor. Please install Tor manually:\n"
            "  - Windows: Download Tor Expert Bundle from https://www.torproject.org/download/tor/\n"
            "  - Linux: sudo apt install tor && sudo systemctl start tor\n"
            "  - macOS: brew install tor && brew services start tor"
        )

    def stop(self) -> None:
        """Stop the managed Tor process."""
        if self._process and self._process.poll() is None:
            logger.info("Stopping managed Tor process (PID %d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _find_tor_binary(self) -> Path | None:
        """Search for an existing Tor binary."""
        # Check config override
        if self.config.tor_binary and self.config.tor_binary.exists():
            return self.config.tor_binary

        # Check common locations
        search_paths = [
            # Windows
            Path("C:/Tor/tor.exe"),
            Path(os.environ.get("PROGRAMFILES", "")) / "Tor" / "tor.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Tor" / "tor.exe",
            Path(os.environ.get("APPDATA", "")) / "Tor" / "tor.exe",
            # Linux/macOS
            Path("/usr/bin/tor"),
            Path("/usr/local/bin/tor"),
            Path("/opt/homebrew/bin/tor"),
            # Bundled in our data dir
            self.config.data_dir / "tor" / "tor.exe",
            self.config.data_dir / "tor" / "tor",
        ]

        # Also check PATH
        tor_in_path = shutil.which("tor")
        if tor_in_path:
            return Path(tor_in_path)

        for p in search_paths:
            if p.exists():
                return p

        return None

    def _start_tor(self, tor_path: Path) -> None:
        """Start Tor as a subprocess."""
        logger.info("Starting Tor from: %s", tor_path)

        tor_data = self.config.data_dir / "tor_data"
        tor_data.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(tor_path),
            "--SocksPort", str(self._parse_proxy()[1]),
            "--DataDirectory", str(tor_data),
            "--Log", "notice stdout",
        ]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
        )

        # Wait for Tor to bootstrap
        logger.info("Waiting for Tor to bootstrap...")
        for _ in range(30):
            if self.is_running:
                logger.info("Tor is ready!")
                return
            time.sleep(1)

        raise ConnectionError("Tor failed to start within 30 seconds")

    def _download_tor_windows(self) -> Path | None:
        """Download Tor Expert Bundle for Windows."""
        dest = self.config.data_dir / "tor"
        dest.mkdir(parents=True, exist_ok=True)
        tor_exe = dest / "tor.exe"

        if tor_exe.exists():
            return tor_exe

        logger.info("Downloading Tor Expert Bundle for Windows...")
        url = "https://dist.torproject.org/torbrowser/14.5.4/tor-win64-0.4.8.14.zip"

        try:
            with httpx.Client(timeout=120, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()

            with zipfile.ZipFile(BytesIO(r.content)) as zf:
                # Extract tor.exe and required DLLs
                for name in zf.namelist():
                    if name.endswith((".exe", ".dll")):
                        data = zf.read(name)
                        out_path = dest / Path(name).name
                        out_path.write_bytes(data)

            if tor_exe.exists():
                logger.info("Tor downloaded to: %s", dest)
                return tor_exe
        except Exception as e:
            logger.warning("Failed to download Tor: %s", e)

        return None

    def _parse_proxy(self) -> tuple[str, int]:
        """Parse host:port from socks_proxy URL."""
        url = self.config.socks_proxy
        # Strip protocol prefix
        url = url.replace("socks5h://", "").replace("socks5://", "")
        url = url.replace("socks4://", "")
        host, port = url.split(":")
        return host, int(port)


class DarkWebSearcher:
    """Search and crawl dark web (.onion) content through Tor."""

    def __init__(self, config: TorConfig) -> None:
        self.config = config
        self.manager = TorManager(config)

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search the dark web for a query across several .onion indexes.

        Queries normal services only (search portals, content databases) —
        no torrent specialization. Tor is started automatically when needed.
        """
        results: list[SearchResult] = []

        # Search via Ahmia (clearnet-accessible .onion search)
        try:
            ahmia_results = self._search_ahmia(query, max_results)
            results.extend(ahmia_results)
        except Exception as e:
            logger.warning("Ahmia search failed: %s", e)

        # Try .onion search engines directly through Tor
        onion_results = self._search_onion_engines(query, max_results)
        results.extend(onion_results)

        logger.info("Dark web search for '%s': %d results", query, len(results))
        return results

    def _search_onion_engines(self, query: str, max_results: int) -> list[SearchResult]:
        """Query .onion search engines through the Tor proxy."""
        from bs4 import BeautifulSoup

        results: list[SearchResult] = []
        try:
            proxy = self.manager.ensure_running()
        except ConnectionError:
            logger.warning("Tor unavailable; skipping .onion search engines")
            return []

        transport = SyncProxyTransport.from_url(proxy)
        for name, url_tmpl in ONION_SEARCH_DATABASES:
            if name == "ahmia":
                continue  # already searched via clearnet
            if "{query}" in url_tmpl:
                url = url_tmpl.format(query=query.replace(" ", "+"))
            else:
                url = url_tmpl
            # .onion requires http
            if url.startswith("https://"):
                url = "http://" + url[8:]

            try:
                with httpx.Client(transport=transport, timeout=self.config.request_timeout) as client:
                    r = client.get(url)
                    r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                # Collect anchor links to .onion pages
                seen = set()
                for a in soup.select("a[href]")[:max_results * 3]:
                    href = a["href"]
                    if ".onion" not in href:
                        continue
                    if href in seen:
                        continue
                    seen.add(href)
                    if not href.startswith("http"):
                        href = "http://" + href
                    results.append(
                        SearchResult(
                            url=href,
                            title=a.get_text(strip=True) or href,
                            snippet="",
                            source_engine=name,
                            rank=len(results) + 1,
                            source_type=SourceType.DARKWEB,
                        )
                    )
                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.warning("Onion engine '%s' failed: %s", name, e)

        return results

    def fetch_onion(self, url: str, timeout: int | None = None) -> str | None:
        """Fetch content from a .onion URL through Tor."""
        timeout = timeout or self.config.request_timeout

        try:
            proxy = self.manager.ensure_running()
        except ConnectionError as e:
            logger.error("Cannot fetch .onion: %s", e)
            return None

        try:
            transport = SyncProxyTransport.from_url(proxy)
            with httpx.Client(transport=transport, timeout=timeout) as client:
                # .onion sites are almost always HTTP, not HTTPS
                if url.startswith("https://"):
                    url = "http://" + url[8:]
                elif not url.startswith("http://"):
                    url = "http://" + url

                r = client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as e:
            logger.warning("Failed to fetch .onion %s: %s", url, e)
            return None

    def _search_ahmia(self, query: str, max_results: int) -> list[SearchResult]:
        """Search Ahmia.fi for .onion content."""
        url = AHMIA_SEARCH_URL.format(query=query.replace(" ", "+"))

        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
        except Exception as e:
            logger.warning("Ahmia request failed: %s", e)
            return []

        # Parse results from Ahmia HTML
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(r.text, "html.parser")
        results: list[SearchResult] = []

        for item in soup.select(".result")[:max_results]:
            link_el = item.select_one("a")
            if not link_el:
                continue

            href = link_el.get("href", "")
            title = link_el.get_text(strip=True)
            desc_el = item.select_one(".description")
            snippet = desc_el.get_text(strip=True) if desc_el else ""

            if href:
                # Ensure .onion URLs go through http
                if not href.startswith("http"):
                    href = "http://" + href

                results.append(
                    SearchResult(
                        url=href,
                        title=title,
                        snippet=snippet,
                        source_engine="ahmia",
                        rank=len(results) + 1,
                        source_type=SourceType.DARKWEB,
                    )
                )

        return results

    def close(self) -> None:
        """Stop managed Tor process."""
        self.manager.stop()
