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

        # Adult mode swaps the engine roster toward uncensored-capable
        # engines (Yandex first, DuckDuckGo with safesearch off).
        engine_names = (
            config.adult_engines if config.mode == "adult" else config.engines
        )
        for name in engine_names:
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
            "Search engine active (%s mode): %s",
            config.mode,
            ", ".join(p.name for p in self._providers),
        )

    # ------------------------------------------------------------------
    # Text / web search
    # ------------------------------------------------------------------

    def _is_blocked(self, url: str) -> bool:
        """True if the URL matches an adult-mode excluded domain."""
        if self.config.mode != "adult":
            return False
        try:
            from urllib.parse import urlparse

            host = urlparse(url).netloc.lower().split(":")[0]
        except Exception:  # noqa: BLE001
            host = ""
        if not host:
            return False
        for domain in self.config.adult_blocked_domains:
            d = domain.lower().strip()
            if not d:
                continue
            if d.startswith("."):
                # suffix rule, e.g. ".gov" blocks any tld
                if host.endswith(d):
                    return True
            elif host == d or host.endswith("." + d):
                # exact host or subdomain, e.g. "nih.gov" blocks "pmc.ncbi.nlm.nih.gov"
                return True
        return False

    def _allowed(self, results: list[SearchResult]) -> list[SearchResult]:
        if self.config.mode != "adult":
            return results
        kept = [r for r in results if not self._is_blocked(r.url)]
        if len(kept) != len(results):
            logger.info(
                "Adult mode: filtered %d gov/academic/academic-style results",
                len(results) - len(kept),
            )
        return kept

    def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        """Run *query* across every enabled provider, merge results."""
        limit = max_results or self.config.max_results_per_query
        if self.config.deep:
            limit = int(limit * 1.5)
        all_results: list[SearchResult] = []
        for provider in self._providers:
            try:
                hits = provider.search(query, limit)
                all_results.extend(hits)
            except Exception as e:  # noqa: BLE001
                logger.warning("Provider %s failed: %s", provider.name, e)
        return self._allowed(all_results)

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
        if self.config.mode == "adult":
            all_images = [i for i in all_images if not self._is_blocked(i.page_url or i.image_url)]
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
