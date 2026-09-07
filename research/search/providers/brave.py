"""Brave Search provider — scrapes search.brave.com HTML results with resilience."""

from __future__ import annotations

import logging
import random
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://search.brave.com/search?q={query}&source=web"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


class BraveProvider(SearchProvider):
    """Search via Brave's public HTML results (no API key needed)."""

    name = "brave"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = _SEARCH_URL.format(query=quote_plus(query))
        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        try:
            r = self.client.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for item in soup.select(".snippet, .result, div[data-type='web']")[:max_results]:
                    a = item.select_one("a.result-header, a[href^='http'], a")
                    if not a or not a.get("href"):
                        continue
                    href = a["href"]
                    if href.startswith("/"):
                        href = "https://search.brave.com" + href
                    if "search.brave.com" in href:
                        continue

                    title_el = a.select_one(".title") or a.select_one("span") or a
                    title = title_el.get_text(strip=True) if title_el else ""

                    desc_el = (
                        item.select_one(".snippet-description")
                        or item.select_one(".snippet-snippet-content")
                        or item.select_one(".snippet-content")
                        or item.select_one("p")
                    )
                    desc = desc_el.get_text(strip=True) if desc_el else ""

                    results.append(
                        SearchResult(
                            url=href,
                            title=title,
                            snippet=desc,
                            source_engine=self.name,
                            rank=len(results) + 1,
                            source_type=classify_source(href),
                        )
                    )
        except Exception as e:
            logger.debug("Brave request failed for '%s': %s", query, e)
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