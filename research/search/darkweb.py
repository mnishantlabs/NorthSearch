"""Tor integration and dark web search. Manages Tor process internally and queries multiple .onion engines."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from httpx_socks import AsyncProxyTransport, SyncProxyTransport

from research.config import TorConfig
from research.models import SearchResult, SourceType

logger = logging.getLogger(__name__)

# Expanded list of .onion and darknet search engines & indexers
ONION_SEARCH_DATABASES: list[tuple[str, str]] = [
    ("ahmia", "https://ahmia.fi/search/?q={query}"),
    ("ahmia_onion", "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"),
    ("tor66", "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5uwxiisujad.onion/search?q={query}"),
    ("onionland", "http://3bbad7fauom4d6sg3alyqe2f2iiv2ltyfyzc2nbqm34h5xkelj5icnad.onion/search?q={query}"),
    ("darkness", "http://darkness.eqlz3x3zvaykh6b2.onion/?q={query}"),
    ("ddgonion", "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion/?q={query}&ia=web"),
    ("torch", "http://torchde3p3spjiz2.onion/search?q={query}"),
    ("candle", "http://gda5c3p57jbyh42q.onion/search?q={query}"),
    ("haystak", "http://haystak5nwoytnnurjmpst77xn2wglixlz4r7xcooljgahgahhgah.onion/?q={query}"),
    ("excavator", "http://2fd6avmvmvavqgah.onion/search?q={query}"),
    ("phobos", "http://phobosxilamwcgwxipknx2jldgmn72zpjg244xvgnrgydtp7w6647wid.onion/search?query={query}"),
    ("subora", "http://suborave7vkvb4b574j7oxz7o4sfg4bkm5y2z35t736px7k26g2224qd.onion/search?q={query}"),
    ("venus", "http://venus5xeb2q2b7p3e23b2c6a4m2a3b3c3d3e3f3g3h3i3j3k3l3m3n3o.onion/?q={query}"),
    ("onionsearch", "http://onionsearchee2cvkhf2bcv3m64q6f3v32x23g25x47j22b3v6w5n.onion/search?q={query}"),
    ("recon", "http://recon222fetm4tvppjjwtvxq4nwhnxh4s3rhgqd272j6n327wqwad4qd.onion/?q={query}"),
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
            sock.settimeout(2)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            return result == 0
        except Exception:
            return False

    def ensure_running(self) -> str:
        """Ensure Tor is running. Returns the SOCKS proxy URL."""
        if self.is_running:
            return self.config.socks_proxy

        if not self.config.auto_manage:
            raise ConnectionError("Tor is not running and auto_manage is disabled.")

        # Try to find and start Tor
        tor_path = self._find_tor_binary()
        if tor_path:
            try:
                self._start_tor(tor_path)
                return self.config.socks_proxy
            except Exception as e:
                logger.warning("Failed to start existing Tor binary: %s", e)

        # Try to download Tor Expert Bundle (Windows)
        if platform.system() == "Windows":
            tor_path = self._download_tor_windows()
            if tor_path:
                self._start_tor(tor_path)
                return self.config.socks_proxy

        raise ConnectionError("Could not start local Tor. Dark search will use clearnet onion gateways.")

    def stop(self) -> None:
        """Stop the managed Tor process."""
        if self._process and self._process.poll() is None:
            logger.info("Stopping managed Tor process (PID %d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _find_tor_binary(self) -> Path | None:
        """Search for an existing Tor binary."""
        if self.config.tor_binary and self.config.tor_binary.exists():
            return self.config.tor_binary

        home = Path.home()
        search_paths = [
            home / "Desktop" / "Tor Browser" / "Browser" / "TorBrowser" / "Tor" / "tor.exe",
            home / "OneDrive" / "Desktop" / "Tor Browser" / "Browser" / "TorBrowser" / "Tor" / "tor.exe",
            home / "AppData" / "Local" / "Tor Browser" / "Browser" / "TorBrowser" / "Tor" / "tor.exe",
            Path("C:/Tor Browser/Browser/TorBrowser/Tor/tor.exe"),
            Path("C:/Tor/tor.exe"),
            Path("C:/Program Files/Tor Browser/Browser/TorBrowser/Tor/tor.exe"),
            Path("C:/Program Files (x86)/Tor Browser/Browser/TorBrowser/Tor/tor.exe"),
            Path(os.environ.get("PROGRAMFILES", "")) / "Tor" / "tor.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Tor" / "tor.exe",
            Path(os.environ.get("APPDATA", "")) / "Tor" / "tor.exe",
            Path("/usr/bin/tor"),
            Path("/usr/local/bin/tor"),
            Path("/opt/homebrew/bin/tor"),
            self.config.data_dir / "tor" / "tor.exe",
            self.config.data_dir / "tor" / "tor",
            Path(__file__).parent.parent.parent / "tor_data" / "tor" / "tor.exe",
        ]

        tor_in_path = shutil.which("tor")
        if tor_in_path:
            return Path(tor_in_path)

        for p in search_paths:
            if p and p.exists():
                return p

        return None

    def _start_tor(self, tor_path: Path) -> None:
        """Start Tor as a background subprocess."""
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

        for _ in range(25):
            if self.is_running:
                logger.info("Tor successfully initialized and listening on %s", self.config.socks_proxy)
                return
            time.sleep(1)

        raise ConnectionError("Tor failed to bind within 25 seconds")

    def _download_tor_windows(self) -> Path | None:
        """Download Tor Expert Bundle for Windows."""
        dest = self.config.data_dir / "tor"
        dest.mkdir(parents=True, exist_ok=True)
        tor_exe = dest / "tor.exe"

        if tor_exe.exists():
            return tor_exe

        logger.info("Downloading Tor Expert Bundle...")
        url = "https://dist.torproject.org/torbrowser/14.5.4/tor-win64-0.4.8.14.zip"

        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()

            with zipfile.ZipFile(BytesIO(r.content)) as zf:
                for name in zf.namelist():
                    if name.endswith((".exe", ".dll")):
                        data = zf.read(name)
                        out_path = dest / Path(name).name
                        out_path.write_bytes(data)

            if tor_exe.exists():
                logger.info("Tor downloaded to: %s", dest)
                return tor_exe
        except Exception as e:
            logger.warning("Tor download failed: %s", e)

        return None

    def _parse_proxy(self) -> tuple[str, int]:
        url = self.config.socks_proxy
        url = url.replace("socks5h://", "").replace("socks5://", "").replace("socks4://", "")
        host, port = url.split(":")
        return host, int(port)


class DarkWebSearcher:
    """Search and crawl dark web (.onion) content with parallel multi-engine fallback."""

    def __init__(self, config: TorConfig) -> None:
        self.config = config
        self.manager = TorManager(config)

    def search(self, query: str, max_results: int = 15) -> list[SearchResult]:
        """Search the dark web across multiple .onion engines and indexers."""
        # Strip redundant site:onion tokens from query
        clean_query = re.sub(r'\bsite:\.?onion\b', '', query, flags=re.IGNORECASE).strip()
        search_term = clean_query or query

        results: list[SearchResult] = []

        # 1. Native Tor querying if Tor is running
        tor_available = False
        proxy_url = ""
        try:
            if self.manager.is_running:
                proxy_url = self.config.socks_proxy
                tor_available = True
            elif self.config.auto_manage:
                proxy_url = self.manager.ensure_running()
                tor_available = True
        except Exception:
            pass

        if tor_available:
            try:
                onion_results = self._parallel_onion_search(search_term, proxy_url, max_results)
                results.extend(onion_results)
            except Exception as e:
                logger.debug("Native Tor search error: %s", e)

        # 2. Clearnet Darknet Discovery & Ahmia Gateway
        if len(results) < max_results:
            try:
                ahmia_results = self._search_ahmia(search_term, max_results)
                results.extend(ahmia_results)
            except Exception as e:
                logger.debug("Ahmia clearnet search failed: %s", e)

        # 3. DuckDuckGo Onion Discovery Fallback
        if len(results) < max_results:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    for hit in ddgs.text(f"{search_term} site:onion", max_results=max_results):
                        href = hit.get("href", "")
                        if ".onion" in href or "onion" in href:
                            results.append(
                                SearchResult(
                                    url=href,
                                    title=hit.get("title", "") or href,
                                    snippet=hit.get("body", ""),
                                    source_engine="tor-index",
                                    rank=len(results) + 1,
                                    source_type=SourceType.DARKWEB,
                                )
                            )
            except Exception as e:
                logger.debug("DDGS onion search fallback failed: %s", e)

        # Deduplicate results by URL
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in results:
            clean = r.url.rstrip("/")
            if clean not in seen:
                seen.add(clean)
                deduped.append(r)
                if len(deduped) >= max_results:
                    break

        return deduped

    def _search_ahmia(self, query: str, max_results: int) -> list[SearchResult]:
        """Search Ahmia.fi with clean redirect decoding."""
        url = f"https://ahmia.fi/search/?q={quote_plus(query)}"
        results: list[SearchResult] = []

        with httpx.Client(timeout=8, follow_redirects=True) as client:
            r = client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if r.status_code != 200:
                return []

        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".result, li.result, tr")[:max_results]:
            link_el = item.select_one("a[href]")
            if not link_el:
                continue

            href = link_el["href"]
            title = link_el.get_text(strip=True)
            desc_el = item.select_one(".description, p, p.snippet, td")
            snippet = desc_el.get_text(strip=True) if desc_el else ""

            if "redirect_url=" in href:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(href).query)
                href = qs.get("redirect_url", [href])[0]

            if ".onion" in href:
                if not href.startswith("http"):
                    href = "http://" + href
                results.append(
                    SearchResult(
                        url=href,
                        title=title or href,
                        snippet=snippet,
                        source_engine="ahmia",
                        rank=len(results) + 1,
                        source_type=SourceType.DARKWEB,
                    )
                )

        return results

    def _parallel_onion_search(self, query: str, proxy: str, max_results: int) -> list[SearchResult]:
        """Query multiple onion engines simultaneously through Tor."""
        all_results: list[SearchResult] = []
        transport = SyncProxyTransport.from_url(proxy)

        def _query_single_engine(name: str, url_tmpl: str) -> list[SearchResult]:
            if name == "ahmia":
                return []
            url = url_tmpl.format(query=quote_plus(query))
            if url.startswith("https://"):
                url = "http://" + url[8:]
            res: list[SearchResult] = []
            try:
                with httpx.Client(transport=transport, timeout=12) as client:
                    r = client.get(url, headers={"User-Agent": "TorBrowser/14.0"})
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        for a in soup.select("a[href]")[:max_results * 2]:
                            href = a["href"]
                            if ".onion" not in href or href == url:
                                continue
                            if not href.startswith("http"):
                                href = "http://" + href
                            title = a.get_text(strip=True) or href
                            res.append(
                                SearchResult(
                                    url=href,
                                    title=title,
                                    snippet="",
                                    source_engine=name,
                                    rank=len(res) + 1,
                                    source_type=SourceType.DARKWEB,
                                )
                            )
                            if len(res) >= max_results:
                                break
            except Exception:
                pass
            return res

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_query_single_engine, name, tmpl)
                for name, tmpl in ONION_SEARCH_DATABASES
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass

        return all_results

    def fetch_onion(self, url: str, timeout: int | None = None) -> str | None:
        """Fetch content from a .onion URL through Tor."""
        timeout = timeout or self.config.request_timeout
        try:
            proxy = self.manager.ensure_running()
        except Exception:
            logger.debug("Cannot fetch .onion without active Tor: %s", url)
            return None

        try:
            transport = SyncProxyTransport.from_url(proxy)
            with httpx.Client(transport=transport, timeout=timeout) as client:
                if url.startswith("https://"):
                    url = "http://" + url[8:]
                elif not url.startswith("http://"):
                    url = "http://" + url
                r = client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as e:
            logger.debug("Failed to fetch .onion %s: %s", url, e)
            return None

    def close(self) -> None:
        """Stop managed Tor process."""
        self.manager.stop()
