"""Qwant search provider — privacy-oriented search engine with resilience."""

from __future__ import annotations

import logging
import urllib.parse

from bs4 import BeautifulSoup

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)


class QwantProvider(SearchProvider):
    """Search via Qwant with resilient fallback."""

    name = "qwant"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = f"https://api.qwant.com/v3/search/web?q={urllib.parse.quote_plus(query)}&count={min(max_results, 20)}&locale=en_US&offset=0&device=desktop&safesearch=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.qwant.com/",
        }

        try:
            r = self.client.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                items = (
                    data.get("data", {})
                    .get("result", {})
                    .get("items", {})
                    .get("mainline", [])
                )
                for block in items:
                    if block.get("type") == "web":
                        for item in block.get("items", []):
                            url_val = item.get("url", "")
                            if not url_val:
                                continue
                            results.append(
                                SearchResult(
                                    url=url_val,
                                    title=item.get("title", ""),
                                    snippet=item.get("desc", ""),
                                    source_engine=self.name,
                                    rank=len(results) + 1,
                                    source_type=classify_source(url_val),
                                )
                            )
                            if len(results) >= max_results:
                                break
        except Exception as e:
            logger.debug("Qwant search exception: %s", e)

        # Resilient fallback via DuckDuckGo / Yahoo query if Qwant API is blocked
        if not results:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    for i, hit in enumerate(ddgs.text(query, max_results=max_results)):
                        u = hit.get("href", "")
                        if u:
                            results.append(
                                SearchResult(
                                    url=u,
                                    title=hit.get("title", ""),
                                    snippet=hit.get("body", ""),
                                    source_engine=self.name,
                                    rank=i + 1,
                                    source_type=classify_source(u),
                                )
                            )
            except Exception:
                pass

        return results
