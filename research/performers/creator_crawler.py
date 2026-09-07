"""Advanced Performer, Creator & OnlyFans metadata crawler and photo downloader."""

from __future__ import annotations

import concurrent.futures
import datetime
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

import httpx

from research.performers.database import Performer, PerformerDatabase

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class CreatorCrawler:
    """Crawls and enriches performer profiles with photos, age, country, and OnlyFans metadata."""

    def __init__(self, db: PerformerDatabase, timeout: int = 20) -> None:
        self.db = db
        self.timeout = timeout
        self.photos_dir = Path(db.config.data_dir) / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.session = None
        if cffi_requests is not None:
            try:
                self.session = cffi_requests.Session(impersonate="chrome124")
            except Exception:
                self.session = None
        self.httpx_client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        )

    def _get(self, url: str, params: dict | None = None, timeout: int = 15) -> str | None:
        """Robust HTTP GET using curl_cffi or fallback httpx."""
        if self.session:
            try:
                r = self.session.get(url, params=params, timeout=timeout)
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                logger.debug("curl_cffi failed on %s: %s", url, e)

        try:
            r = self.httpx_client.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            logger.debug("httpx failed on %s: %s", url, e)

        return None

    def _get_binary(self, url: str, timeout: int = 10) -> bytes | None:
        """Download binary image data."""
        if self.session:
            try:
                r = self.session.get(url, timeout=timeout)
                if r.status_code == 200 and len(r.content) > 500:
                    return r.content
            except Exception:
                pass

        try:
            r = self.httpx_client.get(url, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 500:
                return r.content
        except Exception:
            pass

        return None

    def close(self) -> None:
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        self.httpx_client.close()

    def fetch_photo_for_name(self, name: str) -> str | None:
        """Search and download a photo for a single performer by name on demand."""
        clean_name = re.sub(r'[^\w\s-]', '', name).strip()
        filename = f"{clean_name}_b800.png"
        target_path = self.photos_dir / filename
        if target_path.exists() and target_path.stat().st_size > 500:
            return filename

        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                for hit in ddgs.images(f"{name} portrait photo", max_results=4, safesearch="off"):
                    img_url = hit.get("image") or hit.get("thumbnail")
                    if not img_url:
                        continue
                    content = self._get_binary(img_url, timeout=8)
                    if content:
                        target_path.write_bytes(content)
                        rec = self.db.get(name)
                        if rec:
                            rec.photo = filename
                            self.db.save()
                        return filename
        except Exception as e:
            logger.debug("Auto-photo fetch failed for %s: %s", name, e)

        return None

    def crawl_creators(
        self,
        max_performers: int = 150,
        category: str = "OnlyFans Star",
        progress_cb: Any = None,
        stop_event: Any = None,
        pause_event: Any = None,
    ) -> dict[str, Any]:
        """Crawl performers across pages with full profile metadata (age, country, OnlyFans, videos, views)."""
        import time

        scraped_records: list[dict[str, Any]] = []
        base_url = "https://www.pornhub.com/pornstars"

        page = 1
        max_pages = (max_performers // 20) + 2

        while len(scraped_records) < max_performers and page <= max_pages:
            # Check stop condition
            if stop_event and stop_event.is_set():
                if progress_cb:
                    progress_cb(f"Stopped by user. Total indexed: {len(scraped_records)}", len(scraped_records), max_performers)
                break

            # Check pause condition
            while pause_event and pause_event.is_set():
                if stop_event and stop_event.is_set():
                    break
                time.sleep(0.2)

            params = {"gender": "female", "page": str(page)}
            if "new" in category.lower():
                params["sort"] = "rank"
            elif "top" in category.lower():
                params["sort"] = "mostviewed"

            if progress_cb:
                progress_cb(f"Scanning directory page {page}...", len(scraped_records), max_performers)

            html = self._get(base_url, params=params)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select(".pornstarItem, .performerCard, li.pornstarSection")
            if not cards:
                break

            for card in cards:
                if stop_event and stop_event.is_set():
                    break
                while pause_event and pause_event.is_set():
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(0.2)

                if len(scraped_records) >= max_performers:
                    break

                name_el = card.select_one("span.title, a.title, .nameTitle, .name")
                name = name_el.get_text(strip=True) if name_el else ""
                if not name:
                    continue

                link_el = card.select_one("a[href]")
                profile_url = urljoin(base_url, link_el["href"]) if link_el else ""

                img_el = card.select_one("img[src], img[data-src], img[data-thumb], img[data-image]")
                img_src = ""
                if img_el:
                    img_src = img_el.get("data-src") or img_el.get("data-thumb") or img_el.get("data-image") or img_el.get("src") or ""
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src

                # Extract numbers
                card_text = card.get_text(" ", strip=True)
                numbers = [int(s.replace(",", "")) for s in re.findall(r"\b\d[\d,]*\b", card_text) if len(s.replace(",", "")) < 10]
                vids = numbers[0] if len(numbers) > 0 else 0
                views = numbers[1] if len(numbers) > 1 else 0

                # Download photo
                clean_name = re.sub(r'[^\w\s-]', '', name).strip()
                photo_file = f"{clean_name}_b800.png"
                dest_photo = self.photos_dir / photo_file
                if not dest_photo.exists() and img_src:
                    content = self._get_binary(img_src, timeout=8)
                    if content:
                        dest_photo.write_bytes(content)
                    else:
                        photo_file = None
                elif not dest_photo.exists():
                    photo_file = None

                # Deep profile fetch for Age & Country & OnlyFans
                age = None
                country = None
                onlyfans_link = None
                if profile_url:
                    p_html = self._get(profile_url, timeout=8)
                    if p_html:
                        p_soup = BeautifulSoup(p_html, "html.parser")
                        p_text = p_soup.get_text(" ", strip=True)

                        # Extract Age
                        age_match = re.search(r'\b(?:Age|years old):\s*(\d{2})\b', p_text, re.IGNORECASE)
                        if age_match:
                            age = int(age_match.group(1))

                        # Extract Country/City
                        country_match = re.search(r'\b(?:From|Born in|Country|City):\s*([A-Za-z\s,]+?)(?:\s{2,}|\||\n|$)', p_text, re.IGNORECASE)
                        if country_match:
                            country = country_match.group(1).strip()[:40]

                        # Extract OnlyFans / Social
                        for a_tag in p_soup.select("a[href*='onlyfans.com'], a[href*='fansly.com']"):
                            onlyfans_link = a_tag["href"]
                            break

                # Upsert into DB
                existing = self.db.get(name)
                if existing is None:
                    new_rec = Performer(
                        name=name,
                        videos=vids,
                        views=views,
                        photo=photo_file,
                        gender="female",
                        url=profile_url,
                        age=age,
                        country=country,
                        category=category,
                        onlyfans_url=onlyfans_link,
                    )
                    self.db._records[name] = new_rec
                else:
                    if photo_file:
                        existing.photo = photo_file
                    if vids > existing.videos:
                        existing.videos = vids
                    if views > existing.views:
                        existing.views = views
                    if age:
                        existing.age = age
                    if country:
                        existing.country = country
                    if category:
                        existing.category = category
                    if onlyfans_link:
                        existing.onlyfans_url = onlyfans_link
                    if profile_url and not existing.url:
                        existing.url = profile_url

                scraped_records.append({"name": name, "age": age, "country": country, "photo": photo_file})
                if len(scraped_records) % 3 == 0:
                    self.db.save()

                if progress_cb:
                    progress_cb(f"Updated {name} ({age or 'N/A'} yrs · {country or 'Global'})", len(scraped_records), max_performers)

            page += 1

        if scraped_records:
            self.db.save()

        return {
            "success": True,
            "collected": len(scraped_records),
            "performers": scraped_records,
            "total_db": self.db.count(),
        }

