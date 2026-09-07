"""DuckDuckGo search provider with API & resilient HTML fallback."""

from __future__ import annotations

import logging
import urllib.parse

from bs4 import BeautifulSoup
from ddgs import DDGS

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)


def _clean_ddg_url(url: str) -> str:
    if "duckduckgo.com/l/?" in url:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return qs["uddg"][0]
    return url


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def _safesearch(self) -> str:
        return "off" if getattr(self.config, "mode", "normal") == "adult" else "moderate"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        # 1. Try DDGS library
        try:
            with DDGS() as ddgs:
                for i, hit in enumerate(
                    ddgs.text(
                        query,
                        max_results=max_results,
                        safesearch=self._safesearch(),
                    )
                ):
                    url = hit.get("href", "")
                    if not url:
                        continue
                    results.append(
                        SearchResult(
                            url=_clean_ddg_url(url),
                            title=hit.get("title", ""),
                            snippet=hit.get("body", ""),
                            source_engine=self.name,
                            rank=i + 1,
                            source_type=classify_source(url),
                        )
                    )
                if results:
                    return results
        except Exception:
            pass

        # 2. Resilient HTML fallback
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            r = self.client.get(url, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for res in soup.select(".result")[:max_results]:
                    a = res.select_one(".result__title a, a.result__url, a")
                    if not a or not a.get("href"):
                        continue
                    raw_href = a["href"]
                    href = _clean_ddg_url(raw_href)
                    title = a.get_text(strip=True)
                    sn_el = res.select_one(".result__snippet")
                    sn = sn_el.get_text(strip=True) if sn_el else ""
                    results.append(
                        SearchResult(
                            url=href,
                            title=title,
                            snippet=sn,
                            source_engine=self.name,
                            rank=len(results) + 1,
                            source_type=classify_source(href),
                        )
                    )
        except Exception as e:
            logger.debug("DuckDuckGo HTML fallback failed: %s", e)

        return results

    def search_images(self, query: str, max_results: int) -> list[ImageResult]:
        images: list[ImageResult] = []
        try:
            with DDGS() as ddgs:
                for hit in ddgs.images(
                    query,
                    max_results=max_results,
                    safesearch=self._safesearch(),
                ):
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
            logger.debug("DuckDuckGo image search failed for '%s': %s", query, e)
        return images