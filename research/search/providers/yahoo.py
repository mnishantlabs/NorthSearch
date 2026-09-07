"""Yahoo Search provider with clean URL decoding and TLS impersonation."""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

from research.models import SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)


def _clean_yahoo_url(url: str) -> str:
    m = re.search(r"/RU=(.*?)/RK=", url)
    if m:
        try:
            return urllib.parse.unquote(m.group(1))
        except Exception:
            pass
    return url


class YahooProvider(SearchProvider):
    name = "yahoo"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = f"https://search.yahoo.com/search?p={urllib.parse.quote_plus(query)}"
        html = ""

        if cffi_requests is not None:
            try:
                r = cffi_requests.get(url, impersonate="chrome124", timeout=6)
                if r.status_code == 200:
                    html = r.text
            except Exception as e:
                logger.debug("Yahoo curl_cffi request failed: %s", e)

        if not html:
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                r = self.client.get(url, headers=headers, timeout=6)
                if r.status_code == 200:
                    html = r.text
            except Exception as e:
                logger.debug("Yahoo httpx request failed: %s", e)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        for div in soup.select("div.algo, div.searchCenterMiddle li"):
            a = div.select_one("h3.title a, a.d-ib")
            p = div.select_one("div.compText p, p")
            if not a or not a.get("href"):
                continue

            raw_href = a["href"]
            clean_href = _clean_yahoo_url(raw_href)
            if "search.yahoo.com" in clean_href:
                continue

            raw_title = a.get_text(strip=True)
            # Remove breadcrumb noise from Yahoo titles
            title = re.sub(r"^https?://[^\s]+\s+", "", raw_title) or raw_title
            snippet = p.get_text(strip=True) if p else ""

            results.append(
                SearchResult(
                    url=clean_href,
                    title=title,
                    snippet=snippet,
                    source_engine=self.name,
                    rank=len(results) + 1,
                    source_type=classify_source(clean_href),
                )
            )
            if len(results) >= max_results:
                break

        return results
