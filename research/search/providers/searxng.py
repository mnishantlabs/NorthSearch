"""SearXNG provider — queries public SearXNG instances with automatic fallback."""

from __future__ import annotations

import logging
from typing import Any

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_DEFAULT_INSTANCES = [
    "https://searx.be",
    "https://priv.au",
    "https://search.sapti.me",
    "https://searxng.site",
]


class SearXNGProvider(SearchProvider):
    """Search via a public SearXNG instance with fallback support."""

    name = "searxng"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        base = getattr(self.config, "searxng_base_url", "https://searx.be").rstrip("/")
        self._instances = [base] + [u for u in _DEFAULT_INSTANCES if u != base]

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

    def _raw_query(self, query: str, category: str, max_results: int) -> list[dict[str, Any]]:
        params = {
            "q": query,
            "format": "json",
            "categories": category,
            "language": "en",
            "pageno": 1,
        }
        for base_url in self._instances:
            try:
                r = self.client.get(f"{base_url}/search", params=params, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    res = data.get("results", [])
                    if res:
                        return res[:max_results]
            except Exception:
                continue

        # Fallback via DDGS
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                fallback_results = []
                for hit in ddgs.text(query, max_results=max_results):
                    fallback_results.append({
                        "url": hit.get("href", ""),
                        "title": hit.get("title", ""),
                        "content": hit.get("body", ""),
                    })
                return fallback_results
        except Exception:
            pass

        return []