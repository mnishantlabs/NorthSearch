"""Bing Search provider — scrapes www.bing.com HTML results."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.bing.com/search?q={query}&count={count}"


class BingProvider(SearchProvider):
    """Search via Bing's public HTML results."""

    name = "bing"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        from bs4 import BeautifulSoup

        results: list[SearchResult] = []
        url = _SEARCH_URL.format(query=quote_plus(query), count=max_results)

        try:
            r = self.client.get(url)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("Bing request failed for '%s': %s", query, e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        # Bing wraps results in <li class="b_algo">
        for item in soup.select("li.b_algo")[:max_results]:
            a = item.select_one("h2 a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            desc_el = item.select_one(".b_caption p") or item.select_one("p")
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