"""Performer directory database built from local metadata and photos.

The directory combines:

* ``ph_starts_p_all.xlsx`` / ``ph_starts_f.xlsx`` – the master list of
  performer names with published video and view counts scraped from public
  porn-star index pages.
* ``photos/*_b800.png`` – face photos of professional performers, named
  ``<Real Name>_b800.png``.

The database exposes lookup, filtering, sorting and a small persisted JSON
index so the web UI can browse the directory without re-parsing the
spreadsheets on every request.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator

from research.config import PerformerConfig

logger = logging.getLogger(__name__)

PHOTO_SUFFIX = "_b800.png"
_PHOTO_RE = re.compile(r"^(.*?)%s$" % re.escape(PHOTO_SUFFIX), re.IGNORECASE)


class Performer:
    """A single performer entry in the directory."""

    __slots__ = ("name", "videos", "views", "photo", "gender", "url", "birthdate")

    def __init__(
        self,
        name: str,
        videos: int = 0,
        views: int = 0,
        photo: str | None = None,
        gender: str | None = None,
        url: str | None = None,
        birthdate: str | None = None,
    ) -> None:
        self.name = name
        self.videos = int(videos or 0)
        self.views = int(views or 0)
        self.photo = photo
        self.gender = gender
        self.url = url
        self.birthdate = birthdate

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "videos": self.videos,
            "views": self.views,
            "photo": self.photo,
            "gender": self.gender,
            "url": self.url,
            "birthdate": self.birthdate,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Performer":
        return cls(
            name=d.get("name", ""),
            videos=d.get("videos", 0),
            views=d.get("views", 0),
            photo=d.get("photo"),
            gender=d.get("gender"),
            url=d.get("url"),
            birthdate=d.get("birthdate"),
        )


class PerformerDatabase:
    """In-memory performer directory with search/filter/sort helpers."""

    def __init__(self, config: PerformerConfig | None = None) -> None:
        self.config = config or PerformerConfig()
        self._records: dict[str, Performer] = {}
        self._index_file = Path(self.config.data_dir) / "performer_index.json"

    # ------------------------------------------------------------------
    # build / load
    # ------------------------------------------------------------------

    def build(self) -> "PerformerDatabase":
        """Scan xlsx metadata + photos and normalise into records."""
        data_dir = Path(self.config.data_dir)
        stats = self._load_xlsx_stats(data_dir)
        photos = self._scan_photos(data_dir)

        # seed records from the master stats list
        for name, (videos, views) in stats.items():
            self._records[name] = Performer(
                name=name,
                videos=videos,
                views=views,
                gender=self._guess_gender(name, stats),
            )

        # add photo-only performers that are missing from the stats list
        for name, photo in photos.items():
            if name not in self._records:
                self._records[name] = Performer(name=name, gender="female")

        # attach photo filenames
        for name, photo in photos.items():
            rec = self._records.get(name)
            if rec is not None:
                rec.photo = photo

        logger.info("Built performer database: %d records", len(self._records))
        return self

    def attach_crawled(self, crawled: list[dict[str, Any]]) -> int:
        """Merge crawled records (gender/url/birthdate/rank) by name."""
        updated = 0
        for item in crawled:
            name = str(item.get("name", "")).strip()
            if not name.lower():
                continue
            rec = self._records.get(name)
            if rec is None:
                rec = Performer(name=name)
                self._records[name] = rec
                updated += 1
            if item.get("gender"):
                rec.gender = str(item["gender"])
            if item.get("url"):
                rec.url = str(item["url"])
            if item.get("birthdate"):
                rec.birthdate = str(item["birthdate"])
            if not updated and (item.get("gender") or item.get("url") or item.get("birthdate")):
                updated += 1
        return updated

    def save(self) -> None:
        """Persist the normalized index JSON next to the source data."""
        try:
            self._index_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._index_file.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(
                    [r.to_dict() for r in self.all_records()],
                    f,
                    ensure_ascii=False,
                    indent=1,
                )
            tmp.replace(self._index_file)
        except Exception:
            logger.debug("Failed to persist performer index", exc_info=True)

    def load(self) -> bool:
        """Load a previously persisted index; returns False if none exists."""
        if not self._index_file.exists():
            return False
        try:
            data = json.loads(self._index_file.read_text(encoding="utf-8"))
        except Exception:
            logger.debug("Failed to read performer index", exc_info=True)
            return False
        self._records = {d["name"]: Performer.from_dict(d) for d in data}
        logger.info("Loaded %d performers from index", len(self._records))
        return True

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        gender: str | None = None,
        sort_by: str = "views",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Performer]:
        """Return performers matching the filter, sorted."""
        q = query.strip().lower()
        results = []
        for rec in self.all_records():
            if q and q not in rec.name.lower():
                continue
            if gender and gender not in ("all", "any", "") and rec.gender != gender:
                continue
            results.append(rec)

        if sort_by == "name":
            results.sort(key=lambda r: r.name.lower())
        elif sort_by == "videos":
            results.sort(key=lambda r: r.videos, reverse=True)
        elif sort_by == "similarity":
            pass  # similarity results are pre-ordered by the face engine
        else:
            results.sort(key=lambda r: r.views, reverse=True)
        return results[offset : offset + limit]

    def get(self, name: str) -> Performer | None:
        return self._records.get(name)

    def all_records(self) -> Iterator[Performer]:
        return iter(self._records.values())

    def count(self) -> int:
        return len(self._records)

    def photo_path(self, photo: str) -> Path | None:
        """Resolve a photo filename to a filesystem path, if present."""
        if not photo:
            return None
        p = Path(self.config.data_dir) / "photos" / photo
        return p if p.exists() else None

    def names_with_photos(self) -> list[str]:
        return [r.name for r in self.all_records() if r.photo]

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _load_xlsx_stats(data_dir: Path) -> dict[str, tuple[int, int]]:
        """Read name -> (videos, views) from the master spreadsheet."""
        stats: dict[str, tuple[int, int]] = {}
        try:
            import openpyxl
        except ImportError:
            logger.warning("openpyxl not installed; performer stats will be empty")
            return stats

        master = data_dir / "ph_starts_p_all.xlsx"
        if not master.exists():
            return stats
        try:
            wb = openpyxl.load_workbook(master, read_only=True)
        except Exception:
            logger.debug("Failed to read spreadsheet", exc_info=True)
            return stats
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            name = str(row[0]).strip()
            videos = int(float(row[1])) if row[1] is not None else 0
            views = int(float(row[2])) if row[2] is not None else 0
            stats[name] = (videos, views)
        wb.close()
        return stats

    @staticmethod
    def _scan_photos(data_dir: Path) -> dict[str, str]:
        photos: dict[str, str] = {}
        folder = data_dir / "photos"
        if not folder.exists():
            return photos
        for p in folder.iterdir():
            m = _PHOTO_RE.match(p.name)
            if m:
                photos[m.group(1).strip()] = p.name
        return photos

    @staticmethod
    def _guess_gender(name: str, stats: dict[str, tuple[int, int]]) -> str | None:
        """Heuristic: names in the *_f* spreadsheet rows are female-leaning."""
        # ph_starts_f.xlsx contains the publicly listed female directory,
        # but we only load the master file here; keep it null unless known.
        return None


def build_performer_database(force: bool = False) -> PerformerDatabase:
    """Build (and cache) the performer database for the config."""
    db = PerformerDatabase()
    if not force and db.load():
        return db
    db.build()
    db.save()
    return db