"""Mojeek search provider — independent, crawler-based search engine."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.mojeek.com/search?q={query}"


class MojeekProvider(SearchProvider):
    """Search via Mojeek search engine."""

    name = "mojeek"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = _SEARCH_URL.format(query=quote_plus(query))

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            r = self.client.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for li in soup.select("ul.results-standard > li, div.result, li")[:max_results]:
                    a = li.select_one("a.ob, a.title, a[href^='http']")
                    if not a or not a.get("href") or "mojeek.com" in a["href"]:
                        continue
                    href = a["href"]
                    title = a.get_text(strip=True)
                    s_el = li.select_one("p.s, p.snippet, p")
                    snippet = s_el.get_text(strip=True) if s_el else ""

                    results.append(
                        SearchResult(
                            url=href,
                            title=title,
                            snippet=snippet,
                            source_engine=self.name,
                            rank=len(results) + 1,
                            source_type=classify_source(href),
                        )
                    )
        except Exception as e:
            logger.debug("Mojeek search failed for '%s': %s", query, e)

        # Fallback via DDGS if Mojeek returns 0 results
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
