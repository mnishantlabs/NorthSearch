"""Base class for search engine providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from research.config import SearchConfig
from research.models import ImageResult, SearchResult

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    """Interface every search engine provider implements."""

    name: str = "base"

    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                },
            )
        return self._client

    @abstractmethod
    def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Search text/web results for a query."""

    def search_images(
        self, query: str, max_results: int
    ) -> list[ImageResult]:
        """Search images for a query. Defaults to no results."""
        return []

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    @staticmethod
    def _classify(url: str) -> str:
        """Rough source classification; overridden to add academic markers."""
        return "clearnet"