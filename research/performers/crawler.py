"""Performer metadata + photo crawler.

Crawls public porn-star directory pages and downloads performer **photos and
names** into the local performer database, so the face-similarity engine can
search a growing set of performers offline.

The scraper architecture mirrors Andrei199991/Hotcrawler (rank/name/age/gender/
url per performer) plus the photo collection approach of volom/PornStarSimilarity.

Notes
-----
* The seed directory this toolbox ships with is downloaded once via
  ``research performers crawl`` from the public index pages; photos are
  stored verbatim under ``data/performers/photos/<Name>_b800.png``.
* Directory endpoints may rate-limit (HTTP 429). This is expected; the crawler
  backs off and keeps whatever it already collected.
* Face matching is restricted to the *local* performer database only.
"""

from __future__ import annotations

import html as html_module
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

DEFAULT_DIRECTORY_URL = "https://www.pornhub.com/pornstars"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PHOTO_SUFFIX = "_b800.png"
_AVATAR_CLASS_RE = re.compile(r'class="[^"]*avatar[^"]*"[^>]*src="([^"]+)"')
_NAME_RE = re.compile(r"<title>([^<]+)")
_BIRTH_RE = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})")
_RANK_RE = re.compile(r"#?\s*([\d,]+)")


class PerformerCrawler:
    """Best-effort performer image+metadata downloader for the local DB."""

    def __init__(
        self,
        data_dir: Path,
        gender: str = "female",
        max_performers: int = 200,
        pages: int = 6,
        directory_url: str = DEFAULT_DIRECTORY_URL,
        concurrency: int = 4,
    ) -> None:
        self.data_dir = data_dir
        self.gender = gender
        self.max_performers = max_performers
        self.pages = pages
        self.directory_url = directory_url
        self.concurrency = concurrency
        self.client = httpx.Client(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
            timeout=20,
        )
        self.photos_dir = data_dir / "photos"

    def close(self) -> None:
        self.client.close()

    # ------------------------------------------------------------------

    def run(self, progress=None) -> dict[str, Any]:
        """Crawl the directory, download photos and return results summary."""
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        performers: list[dict[str, Any]] = []
        skip = 0

        for crt in self._iter_directory_entries():
            if len(performers) >= self.max_performers:
                break
            slug = crt.get("url_path", "")
            name = crt.get("name", "")
            if not name:
                continue
            try:
                rec = self._crawl_profile(urljoin(self.directory_url, slug))
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.info("Rate-limited (429); stopping early at %d performers", len(performers))
                    break
                skip += 1
                continue
            except Exception:  # noqa: BLE001
                logger.debug("Profile crawl error for %s", name, exc_info=True)
                skip += 1
                continue

            if not rec.get("photo_url"):
                skip += 1
                continue

            # download + save the photo
            saved = self._save_photo(name, rec["photo_url"])
            if not saved:
                skip += 1
                continue
            rec["name"] = name
            rec["photo"] = Path(saved).name
            performers.append(rec)
            if progress:
                progress(len(performers), name)

        result = {
            "gender": self.gender,
            "collected": len(performers),
            "skipped": skip,
            "performers": performers,
        }
        if performers:
            self._save_json(result)
        return result

    # ------------------------------------------------------------------
    # directory listing
    # ------------------------------------------------------------------

    def _iter_directory_entries(self) -> Any:
        """Yield {name, url_path} for every performer link found on the pages."""
        seen: set[str] = set()
        for page in range(1, self.pages + 1):
            url = f"{self.directory_url}?gender={self.gender}&page={page}"
            logger.debug("Crawling directory page %d", page)
            try:
                resp = self.client.get(url)
                resp.raise_for_status()
            except Exception:  # noqa: BLE001
                logger.warning("Directory page %d failed", page, exc_info=True)
                break
            links = re.findall(r'href="(/pornstar/[^"]+)"', resp.text)
            for link in links:
                slug = link.split("?", 1)[0]
                if slug in seen:
                    continue
                seen.add(slug)
                name = html_module.unescape(slug.rsplit("/", 1)[-1].replace("-", " ").strip())
                yield {"name": _TitleCase(name), "url_path": link}
            if not links:
                break
            time.sleep(0.4)

    # ------------------------------------------------------------------
    # profile extraction
    # ------------------------------------------------------------------

    def _crawl_profile(self, url: str) -> dict[str, Any]:
        resp = self.client.get(url)
        resp.raise_for_status()
        html = resp.text

        name = self._extract_name(html)
        rank = self._extract_rank(html)
        birthdate = self._extract_birthdate(html)
        photo_url = self._extract_photo(html)

        return {
            "name": name,
            "rank": rank,
            "birthdate": birthdate,
            "gender": self.gender,
            "url": url,
            "photo_url": photo_url,
            "photo": None,
        }

    def _extract_name(self, html: str) -> str:
        m = _NAME_RE.search(html)
        if not m:
            return "Unknown"
        title = m.group(1)
        title = title.split(" Porn Videos", 1)[0].split(" - ", 1)[0].strip()
        return _TitleCase(title)

    @staticmethod
    def _extract_rank(html: str) -> str | None:
        # in profile page: the "5" rank is inside a span.big; look for the
        # parent container text like "Pornstar rank 5 Out of..."
        m = re.search(r"rank[^0-9]*([\d,]{1,6})\b", html[: 200_000])
        return m.group(1).replace(",", "") if m else None

    @staticmethod
    def _extract_birthdate(html: str) -> str | None:
        m = _BIRTH_RE.search(html)
        return m.group(1) if m else None

    def _extract_photo(self, html: str) -> str | None:
        # The page escapes quotes/backslashes; flatten to real markup first.
        flat = html.replace('\\"', '"').replace("\\/", "/")
        m = _AVATAR_CLASS_RE.search(flat)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # saving
    # ------------------------------------------------------------------

    def _save_photo(self, name: str, photo_url: str) -> Path | None:
        filename = f"{name}{PHOTO_SUFFIX}"
        dest = self.photos_dir / filename
        if dest.exists():
            return dest
        try:
            resp = self.client.get(photo_url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            logger.info("Saved %s (%d bytes)", dest.name, len(resp.content))
            return dest
        except Exception:  # noqa: BLE001
            logger.debug("Photo download failed for %s", name, exc_info=True)
            return None

    def _save_json(self, result: dict[str, Any]) -> Path:
        out = self.data_dir / f"crawl_{int(time.time())}.json"
        with out.open("w", encoding="utf-8") as f:
            json_dump(result, f)
        return out


def json_dump(data, f) -> None:
    import json

    json.dump(data, f, ensure_ascii=False, indent=1)


def _TitleCase(name: str) -> str:
    """Convert a slug like 'abella-danger' or 'Mia Khalifa' to 'Abella Danger'."""
    return " ".join(w.capitalize() for w in name.split())