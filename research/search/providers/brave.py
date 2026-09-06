"""Brave Search provider — scrapes search.brave.com HTML results."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://search.brave.com/search?q={query}&source=web"


class BraveProvider(SearchProvider):
    """Search via Brave's public HTML results (no API key needed)."""

    name = "brave"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        from bs4 import BeautifulSoup

        results: list[SearchResult] = []
        url = _SEARCH_URL.format(query=quote_plus(query))

        try:
            r = self.client.get(url)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("Brave request failed for '%s': %s", query, e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        # Brave wraps results in <div class="snippet">
        for item in soup.select(".snippet")[:max_results]:
            a = item.select_one("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            if href.startswith("/"):
                href = "https://search.brave.com" + href

            title_el = a.select_one(".title") or a.select_one("span") or a
            title = title_el.get_text(strip=True) if title_el else ""

            desc_el = item.select_one(".snippet-description") or item.select_one(
                ".snippet-snippet-content"
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

        return results