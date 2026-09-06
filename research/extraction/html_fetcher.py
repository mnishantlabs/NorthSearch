"""HTTP fetcher supporting both clearnet and Tor (.onion) requests."""

from __future__ import annotations

import logging

import httpx
from httpx_socks import SyncProxyTransport

from research.config import ExtractionConfig, TorConfig

logger = logging.getLogger(__name__)


class HttpFetcher:
    """Unified HTTP fetcher for clearnet and dark web content."""

    def __init__(
        self,
        extraction_config: ExtractionConfig,
        tor_config: TorConfig | None = None,
    ) -> None:
        self.config = extraction_config
        self.tor_config = tor_config
        self._clearnet_client: httpx.Client | None = None
        self._tor_client: httpx.Client | None = None

    @property
    def clearnet(self) -> httpx.Client:
        if self._clearnet_client is None or self._clearnet_client.is_closed:
            self._clearnet_client = httpx.Client(
                timeout=self.config.request_timeout,
                follow_redirects=True,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._clearnet_client

    def _get_tor_client(self) -> httpx.Client:
        if self._tor_client is None or self._tor_client.is_closed:
            if self.tor_config is None:
                raise RuntimeError("Tor config not provided, cannot fetch .onion")
            proxy = self.tor_config.socks_proxy
            transport = SyncProxyTransport.from_url(proxy)
            self._tor_client = httpx.Client(
                transport=transport,
                timeout=self.tor_config.request_timeout,
                follow_redirects=True,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._tor_client

    def fetch(self, url: str, use_tor: bool = False) -> str | None:
        """Fetch a URL and return the HTML content.

        Args:
            url: The URL to fetch.
            use_tor: If True, route through Tor proxy.
        """
        # Ensure URL has scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # .onion sites must use http and go through Tor
        if ".onion" in url:
            use_tor = True
            if url.startswith("https://"):
                url = "http://" + url[8:]
            elif not url.startswith("http://"):
                url = "http://" + url

        try:
            client = self._get_tor_client() if use_tor else self.clearnet
            r = client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logger.warning("Fetch failed [%s] %s: %s", "tor" if use_tor else "clear", url, e)
            return None

    def close(self) -> None:
        if self._clearnet_client and not self._clearnet_client.is_closed:
            self._clearnet_client.close()
        if self._tor_client and not self._tor_client.is_closed:
            self._tor_client.close()

    def __enter__(self) -> "HttpFetcher":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
