"""Web search engine abstraction — multi-provider architecture."""

from __future__ import annotations

import logging
from typing import Any

from research.config import SearchConfig
from research.models import ImageResult, SearchResult
from research.search.providers import PROVIDERS, SearchProvider

logger = logging.getLogger(__name__)


class SearchEngine:
    """Unified search interface across multiple providers.

    Each provider is a ``SearchProvider`` subclass registered in
    ``providers.PROVIDERS`` and selected via ``config.engines``.
    """

    def __init__(self, config: SearchConfig) -> None:
        self.config = config
        self._providers: list[SearchProvider] = []
        for name in config.engines:
            cls = PROVIDERS.get(name.lower())
            if cls is None:
                logger.warning("Unknown search engine: %s (skipped)", name)
                continue
            try:
                self._providers.append(cls(config))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to init %s provider: %s", name, e)

        # Always keep at least one provider
        if not self._providers:
            logger.warning("No valid search engines; falling back to DuckDuckGo")
            from research.search.providers.duckduckgo import DuckDuckGoProvider

            self._providers = [DuckDuckGoProvider(config)]

        logger.info(
            "Search engine active: %s",
            ", ".join(p.name for p in self._providers),
        )

    # ------------------------------------------------------------------
    # Text / web search
    # ------------------------------------------------------------------

    def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        """Run *query* across every enabled provider, merge results."""
        limit = max_results or self.config.max_results_per_query
        all_results: list[SearchResult] = []
        for provider in self._providers:
            try:
                hits = provider.search(query, limit)
                all_results.extend(hits)
            except Exception as e:  # noqa: BLE001
                logger.warning("Provider %s failed: %s", provider.name, e)
        return all_results

    # ------------------------------------------------------------------
    # Image search
    # ------------------------------------------------------------------

    def search_images(
        self, query: str, max_results: int | None = None
    ) -> list[ImageResult]:
        """Run image search across every enabled provider."""
        limit = max_results or self.config.max_images_per_query
        all_images: list[ImageResult] = []
        for provider in self._providers:
            try:
                imgs = provider.search_images(query, limit)
                all_images.extend(imgs)
            except Exception as e:  # noqa: BLE001
                logger.debug("Image search failed (%s): %s", provider.name, e)
        return all_images

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def search_multiple(
        self, queries: list[str], max_results_per_query: int | None = None
    ) -> list[SearchResult]:
        """Run multiple queries and return combined results."""
        all_results: list[SearchResult] = []
        for query in queries:
            logger.info("Searching: %s", query)
            results = self.search(query, max_results_per_query)
            all_results.extend(results)
            logger.info("  Found %d results", len(results))
        return all_results

    def close(self) -> None:
        for provider in self._providers:
            provider.close()
