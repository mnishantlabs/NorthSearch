"""Online reverse image search multi-provider engine."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from research.models import ImageResult, SearchResult, SourceType

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class OnlineReverseImageSearcher:
    """Searches online visual search engines with an uploaded image or image URL."""

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        )

    def search(self, image_path: Path, max_results: int = 15) -> list[dict[str, Any]]:
        """Run reverse search across available online providers."""
        results: list[dict[str, Any]] = []

        # 1. Yandex Visual Search
        try:
            y_results = self._search_yandex_visual(image_path, max_results)
            results.extend(y_results)
        except Exception as e:
            logger.debug("Yandex visual search failed: %s", e)

        # 2. Bing Visual / Lens direct link generation
        results.extend(self._generate_direct_engine_links(image_path))

        return results[:max_results]

    def _search_yandex_visual(self, image_path: Path, max_results: int) -> list[dict[str, Any]]:
        """Upload image to Yandex Images visual search endpoint."""
        results: list[dict[str, Any]] = []
        url = "https://yandex.com/images/search"

        with open(image_path, "rb") as f:
            files = {"upfile": ("image.jpg", f.read(), "image/jpeg")}

        params = {"rpt": "imageview", "format": "json"}
        r = self.client.post(url, params=params, files=files)
        if r.status_code == 200:
            try:
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup.select(".CbirSites-Item, .other-sites__item")[:max_results]:
                    a = tag.select_one("a[href]")
                    if not a or not a.get("href"):
                        continue
                    href = a["href"]
                    title = tag.select_one(".CbirSites-ItemTitle, .other-sites__title")
                    title_text = title.get_text(strip=True) if title else href
                    desc = tag.select_one(".CbirSites-ItemDescription, .other-sites__desc")
                    desc_text = desc.get_text(strip=True) if desc else ""
                    thumb = tag.select_one("img[src]")
                    thumb_url = thumb["src"] if thumb else ""
                    if thumb_url.startswith("//"):
                        thumb_url = "https:" + thumb_url

                    results.append({
                        "engine": "Yandex Visual",
                        "title": title_text,
                        "url": href,
                        "snippet": desc_text,
                        "thumbnail": thumb_url,
                    })
            except Exception as e:
                logger.debug("Failed parsing Yandex visual HTML: %s", e)

        return results

    def _generate_direct_engine_links(self, image_path: Path) -> list[dict[str, Any]]:
        """Generate direct links to one-click online visual engines for user convenience."""
        return [
            {
                "engine": "Google Lens",
                "title": "Search image on Google Lens",
                "url": "https://lens.google.com/upload",
                "snippet": "Opens Google Lens visual discovery portal for full entity recognition",
                "thumbnail": "",
            },
            {
                "engine": "TinEye",
                "title": "Search image on TinEye Reverse Engine",
                "url": "https://tineye.com/",
                "snippet": "Exact matching and historical image appearance search",
                "thumbnail": "",
            },
            {
                "engine": "Bing Visual",
                "title": "Search image on Bing Visual Search",
                "url": "https://www.bing.com/visualsearch",
                "snippet": "Multi-category visual similarity and web appearance lookup",
                "thumbnail": "",
            },
        ]

    def close(self) -> None:
        self.client.close()
