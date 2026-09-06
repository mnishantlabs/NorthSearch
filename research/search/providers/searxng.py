"""SearXNG provider — queries any public SearXNG instance via its JSON API."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)


class SearXNGProvider(SearchProvider):
    """Search via a public SearXNG instance.

    SearXNG exposes ``/search?format=json&q=...&categories=...``.
    """

    name = "searxng"

    def __init__(self, *args, **kwargs):  # noqa: ANN002
        super().__init__(*args, **kwargs)
        self._base = self.config.searxng_base_url.rstrip("/")

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        return self._query(query, "general", max_results)

    def search_images(self, query: str, max_results: int) -> list[ImageResult]:
        raw = self._raw_query(query, "images", max_results)
        images: list[ImageResult] = []
        for item in raw:
            images.append(
                ImageResult(
                    image_url=item.get("img_src", item.get("url", "")),
                    thumbnail_url=item.get("thumbnail_src", ""),
                    title=item.get("title", ""),
                    page_url=item.get("url", ""),
                    source_engine=self.name,
                    source_type=classify_source(item.get("url", "")),
                    width=int(item.get("img_width") or 0),
                    height=int(item.get("img_height") or 0),
                )
            )
        return images

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _query(
        self, query: str, category: str, max_results: int
    ) -> list[SearchResult]:
        raw = self._raw_query(query, category, max_results)
        results: list[SearchResult] = []
        for item in raw:
            href = item.get("url", "")
            if not href:
                continue
            results.append(
                SearchResult(
                    url=href,
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    source_engine=self.name,
                    rank=len(results) + 1,
                    source_type=classify_source(href),
                )
            )
        return results

    def _raw_query(self, query: str, category: str, max_results: int) -> list[dict]:
        params = {
            "q": query,
            "format": "json",
            "categories": category,
            "language": "en",
            "pageno": 1,
        }
        try:
            r = self.client.get(f"{self._base}/search", params=params)
            r.raise_for_status()
            data = r.json()
            return data.get("results", [])[:max_results]
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "SearXNG request failed (%s): %s", self._base, e
            )
            return []