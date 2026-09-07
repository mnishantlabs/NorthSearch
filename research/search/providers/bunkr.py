"""Bunkr album and media search provider with multi-domain fallback resilience."""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from research.config import SearchConfig
from research.models import ImageResult, SearchResult, SourceType
from research.search.providers.base import SearchProvider

logger = logging.getLogger(__name__)

BUNKR_DOMAINS = [
    "bunkr-albums.org",
    "bunkrsearch.com",
    "bunkr.ws",
    "bunkr.cr",
    "bunkr.bz",
    "bunkr.is",
    "bunkrr.fi",
    "bunkr.tv",
]


class BunkrProvider(SearchProvider):
    """Search engine provider for Bunkr albums, creators, and media archives."""

    name: str = "bunkr"

    def __init__(self, config: SearchConfig) -> None:
        super().__init__(config)

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Search Bunkr albums using bunkr-albums.org and bunkrsearch.com fallback."""
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # 1. Primary: bunkr-albums.org search
        try:
            url = f"https://bunkr-albums.org/?s={urllib.parse.quote_plus(query)}"
            resp = self.client.get(url, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.select("a[href*='/a/'], article a, .card a, h2 a, h3 a"):
                    href = a.get("href", "")
                    if not href or href in seen_urls:
                        continue
                    if not any(d in href for d in BUNKR_DOMAINS) and "/a/" not in href:
                        continue

                    # Extract title and snippet
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 3 or title.lower().startswith("view album"):
                        parent = a.parent
                        title = parent.get_text(" ", strip=True) if parent else title

                    # Clean "View album" prefix
                    title = re.sub(r"^(?:View\s*album\s*|\s*Open\s*|\s*\?\s*)+", "", title, flags=re.IGNORECASE).strip()
                    if not title:
                        title = f"Bunkr Album - {query.title()}"

                    file_count_match = re.search(r"(\d+)\s*files?", title, re.I)
                    snippet = f"Bunkr Album ({file_count_match.group(0) if file_count_match else 'Media Pack'}) - Direct creator cloud album archive"

                    seen_urls.add(href)
                    results.append(
                        SearchResult(
                            title=title,
                            url=href,
                            snippet=snippet,
                            engine="Bunkr Albums",
                            source_type=SourceType.CLEARNET,
                        )
                    )
                    if len(results) >= max_results:
                        break
        except Exception as e:
            logger.debug("Bunkr-albums search failed: %s", e)

        # 2. Secondary fallback: bunkrsearch.com
        if len(results) < max_results:
            try:
                url2 = f"https://bunkrsearch.com/search?q={urllib.parse.quote_plus(query)}"
                resp2 = self.client.get(url2, timeout=12)
                if resp2.status_code == 200:
                    soup2 = BeautifulSoup(resp2.text, "html.parser")
                    for a in soup2.select("a[href*='bunkr'], a[href*='/a/'], a[href*='/v/'], a[href*='/i/'], .card a"):
                        href = a.get("href", "")
                        if not href or href in seen_urls:
                            continue
                        if href.startswith("https://t.me/"):
                            continue
                        if not href.startswith("http"):
                            href = "https://bunkrsearch.com" + href

                        title = a.get_text(strip=True) or f"Bunkr Album ({query})"
                        seen_urls.add(href)
                        results.append(
                            SearchResult(
                                title=title,
                                url=href,
                                snippet=f"Bunkr Media Album for '{query}' - fast multi-part download archive",
                                engine="Bunkr Search",
                                source_type=SourceType.CLEARNET,
                            )
                        )
                        if len(results) >= max_results:
                            break
            except Exception as e:
                logger.debug("Bunkrsearch fallback failed: %s", e)

        return results[:max_results]

    def search_images(self, query: str, max_results: int) -> list[ImageResult]:
        """Extract album preview thumbnails from Bunkr albums."""
        images: list[ImageResult] = []
        try:
            url = f"https://bunkr-albums.org/?s={urllib.parse.quote_plus(query)}"
            resp = self.client.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for img in soup.select("img[src]"):
                    src = img.get("src", "")
                    if not src or not src.startswith("http"):
                        continue
                    parent_a = img.find_parent("a")
                    page_url = parent_a.get("href", url) if parent_a else url
                    alt = img.get("alt") or f"Bunkr Album - {query}"
                    images.append(
                        ImageResult(
                            url=src,
                            thumbnail_url=src,
                            title=alt,
                            source_url=page_url,
                            engine="Bunkr",
                        )
                    )
                    if len(images) >= max_results:
                        break
        except Exception as e:
            logger.debug("Bunkr search_images failed: %s", e)
        return images[:max_results]
