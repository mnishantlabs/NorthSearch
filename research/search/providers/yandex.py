"""Yandex search provider — scrapes the JS-free Yandex Site Search page.

``https://yandex.com/search/site/`` renders with no JavaScript and returns
real organic results (``b-serp-item`` blocks). It is far more tolerant of
automated requests than the main ``/search/`` page and is commonly used for
uncensored/adult discovery, so this provider backs "adult" search mode.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://yandex.com/search/site/"


class YandexProvider(SearchProvider):
    """Search via Yandex Site Search HTML results (no API key needed)."""

    name = "yandex"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        from bs4 import BeautifulSoup

        results: list[SearchResult] = []

        # fresh searchid per query keeps the anti-bot happy
        import random

        params = {
            "text": query,
            "web": "1",
            "searchid": f"{random.randint(1000000, 9999999)}",
        }
        try:
            r = self.client.get(_SEARCH_URL, params=params)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("Yandex request failed for '%s': %s", query, e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("li.b-serp-item")[:max_results]:
            a = item.select_one("a.b-serp-item__title-link")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            if href.startswith("/"):
                continue

            title = a.get_text(" ", strip=True)

            sn = item.select_one(".b-serp-item__text") or item.select_one(
                ".b-serp-item__annotation"
            )
            desc = sn.get_text(" ", strip=True) if sn else ""

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