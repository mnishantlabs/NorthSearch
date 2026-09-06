"""DuckDuckGo search provider via the ddgs library."""

from __future__ import annotations

from ddgs import DDGS

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        try:
            with DDGS() as ddgs:
                for i, hit in enumerate(ddgs.text(query, max_results=max_results)):
                    url = hit.get("href", "")
                    if not url:
                        continue
                    results.append(
                        SearchResult(
                            url=url,
                            title=hit.get("title", ""),
                            snippet=hit.get("body", ""),
                            source_engine=self.name,
                            rank=i + 1,
                            source_type=classify_source(url),
                        )
                    )
        except Exception as e:  # noqa: BLE001
            self._log_error(query, e)
        return results

    def search_images(self, query: str, max_results: int) -> list[ImageResult]:
        images: list[ImageResult] = []
        try:
            with DDGS() as ddgs:
                for hit in ddgs.images(query, max_results=max_results):
                    images.append(
                        ImageResult(
                            image_url=hit.get("image", ""),
                            thumbnail_url=hit.get("thumbnail", ""),
                            title=hit.get("title", ""),
                            page_url=hit.get("url", ""),
                            source_engine=self.name,
                            source_type=classify_source(hit.get("url", "")),
                            width=int(hit.get("width") or 0),
                            height=int(hit.get("height") or 0),
                        )
                    )
        except Exception as e:  # noqa: BLE001
            self._log_error(query, e)
        return images

    @staticmethod
    def _log_error(query: str, e: Exception) -> None:
        import logging

        logging.getLogger(__name__).warning(
            "DuckDuckGo search failed for '%s': %s", query, e
        )