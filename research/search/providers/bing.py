"""Bing Search provider — scrapes www.bing.com HTML results with clean target URLs."""

from __future__ import annotations

import base64
import logging
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from research.models import ImageResult, SearchResult
from research.search.classification import classify_source
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.bing.com/search?q={query}&count={count}"
_IMAGES_URL = "https://www.bing.com/images/search?q={query}&count={count}"


def _clean_bing_url(url: str) -> str:
    """Decode Bing redirect URL `https://www.bing.com/ck/a?!...&u=a1<base64>...` to target URL."""
    if "bing.com/ck/a" not in url:
        return url
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        u_param = qs.get("u", [""])[0]
        if u_param.startswith("a1"):
            # Bing uses `a1` prefix followed by standard base64 of the real target URL
            b64_str = u_param[2:]
            # Add padding if needed
            pad = len(b64_str) % 4
            if pad:
                b64_str += "=" * (4 - pad)
            decoded = base64.urlsafe_b64decode(b64_str).decode("utf-8", errors="ignore")
            if decoded.startswith("http"):
                return decoded
    except Exception:
        pass
    return url


class BingProvider(SearchProvider):
    """Search via Bing's public HTML results."""

    name = "bing"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        url = _SEARCH_URL.format(query=quote_plus(query), count=max_results)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            r = self.client.get(url, headers=headers)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            logger.warning("Bing request failed for '%s': %s", query, e)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("li.b_algo")[:max_results]:
            a = item.select_one("h2 a")
            if not a or not a.get("href"):
                continue
            raw_href = a["href"]
            href = _clean_bing_url(raw_href)
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