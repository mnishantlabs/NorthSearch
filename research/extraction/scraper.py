"""Custom website scraper and local database updater with keyword filtering."""

from __future__ import annotations

import concurrent.futures
import html
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from research.performers.database import Performer, PerformerDatabase

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class ContentScraper:
    """Configurable website scraper that extracts data matching strict keyword rules."""

    def __init__(
        self,
        db: PerformerDatabase,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 20,
    ) -> None:
        self.db = db
        self.timeout = timeout
        self.client = httpx.Client(
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            timeout=timeout,
        )
        self.photos_dir = Path(db.config.data_dir) / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self.client.close()

    def scrape_url(
        self,
        url: str,
        must_include_keywords: list[str] | None = None,
        must_exclude_keywords: list[str] | None = None,
        download_images: bool = True,
        max_items: int = 50,
        progress_cb: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Scrape a website URL and extract entities matching keyword requirements."""
        must_include = [k.strip().lower() for k in (must_include_keywords or []) if k.strip()]
        must_exclude = [k.strip().lower() for k in (must_exclude_keywords or []) if k.strip()]

        logger.info(
            "Starting scrape on %s (must include: %s, exclude: %s)",
            url,
            must_include,
            must_exclude,
        )

        if progress_cb:
            progress_cb(f"Fetching {url}...", 0, max_items)

        try:
            r = self.client.get(url)
            r.raise_for_status()
            page_html = r.text
        except Exception as e:
            return {"error": f"Failed to fetch {url}: {e}", "items_added": 0}

        soup = BeautifulSoup(page_html, "html.parser")
        items_found: list[dict[str, Any]] = []

        # Find potential entity cards or profile elements
        cards = soup.select(".performerCard, .pornstarItem, .item, .profile, .thumb, li, article")
        if not cards:
            cards = [soup]

        for card in cards:
            if len(items_found) >= max_items:
                break

            card_text = card.get_text(" ", strip=True).lower()

            # 1. Check keyword constraints
            if must_include and not all(kw in card_text for kw in must_include):
                continue
            if must_exclude and any(kw in card_text for kw in must_exclude):
                continue

            # 2. Extract entity metadata
            name_el = card.select_one("span.title, a.title, .name, h2, h3, .title")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 2:
                continue

            link_el = card.select_one("a[href]")
            item_url = urljoin(url, link_el["href"]) if link_el else url

            img_el = card.select_one("img[src], img[data-src], img[data-thumb]")
            img_src = ""
            if img_el:
                img_src = img_el.get("data-src") or img_el.get("data-thumb") or img_el.get("src") or ""
                if img_src.startswith("//"):
                    img_src = "https:" + img_src
                elif not img_src.startswith("http"):
                    img_src = urljoin(url, img_src)

            # Try to parse numbers for videos or views if present
            numbers = [int(s.replace(",", "")) for s in re.findall(r"\b\d[\d,]*\b", card_text) if len(s.replace(",", "")) < 10]
            vids = numbers[0] if len(numbers) > 0 else 0
            views = numbers[1] if len(numbers) > 1 else 0

            # Download photo if requested
            photo_file = None
            if download_images and img_src:
                clean_name = re.sub(r'[^\w\s-]', '', name).strip()
                photo_filename = f"{clean_name}_b800.png"
                dest_path = self.photos_dir / photo_filename
                if not dest_path.exists():
                    try:
                        img_res = self.client.get(img_src, timeout=10)
                        if img_res.status_code == 200 and len(img_res.content) > 500:
                            dest_path.write_bytes(img_res.content)
                            photo_file = photo_filename
                    except Exception:
                        pass
                else:
                    photo_file = photo_filename

            # Save / update performer record in DB
            existing = self.db.get(name)
            if existing is None:
                new_p = Performer(
                    name=name,
                    videos=vids,
                    views=views,
                    photo=photo_file,
                    url=item_url,
                )
                self.db._records[name] = new_p
            else:
                if photo_file:
                    existing.photo = photo_file
                if vids > existing.videos:
                    existing.videos = vids
                if views > existing.views:
                    existing.views = views
                if item_url:
                    existing.url = item_url

            items_found.append({
                "name": name,
                "url": item_url,
                "photo": photo_file,
                "videos": vids,
                "views": views,
            })

            if progress_cb:
                progress_cb(f"Scraped {name}", len(items_found), max_items)

        # Persist updated DB
        if items_found:
            self.db.save()

        return {
            "success": True,
            "items_added": len(items_found),
            "items": items_found,
            "total_db_count": self.db.count(),
        }
