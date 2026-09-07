"""Wikipedia & encyclopedic search provider."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)


class WikipediaProvider(SearchProvider):
    name = "wikipedia"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote_plus(query)}&limit={max_results}&namespace=0&format=json"
        data = None

        if cffi_requests is not None:
            try:
                r = cffi_requests.get(url, impersonate="chrome124", timeout=5)
                if r.status_code == 200:
                    data = r.json()
            except Exception as e:
                logger.debug("Wikipedia curl_cffi failed: %s", e)

        if not data:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                r = self.client.get(url, headers=headers, timeout=5)
                if r.status_code == 200:
                    data = r.json()
            except Exception as e:
                logger.debug("Wikipedia httpx failed: %s", e)

        if data and isinstance(data, list) and len(data) >= 4:
            titles = data[1]
            descriptions = data[2]
            links = data[3]

            for i, (t, d, u) in enumerate(zip(titles, descriptions, links)):
                if not u:
                    continue
                results.append(
                    SearchResult(
                        url=u,
                        title=f"{t} — Wikipedia",
                        snippet=d or f"Encyclopedic overview and verified documentation on {t}.",
                        source_engine=self.name,
                        rank=i + 1,
                        source_type="academic",
                    )
                )

        return results
