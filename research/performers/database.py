"""Performer directory database with age, country, categories, and photo indexing."""

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
    """A single performer / creator entry in the directory."""

    __slots__ = (
        "name",
        "videos",
        "views",
        "photo",
        "photo_url",
        "gender",
        "url",
        "birthdate",
        "age",
        "country",
        "category",
        "onlyfans_url",
    )

    def __init__(
        self,
        name: str,
        videos: int = 0,
        views: int = 0,
        photo: str | None = None,
        photo_url: str | None = None,
        gender: str | None = None,
        url: str | None = None,
        birthdate: str | None = None,
        age: int | None = None,
        country: str | None = None,
        category: str | None = None,
        onlyfans_url: str | None = None,
    ) -> None:
        self.name = name
        self.videos = int(videos or 0)
        self.views = int(views or 0)
        self.photo = photo
        self.photo_url = photo_url
        self.gender = gender
        self.url = url
        self.birthdate = birthdate
        self.age = int(age) if age is not None else None
        self.country = country
        self.category = category
        self.onlyfans_url = onlyfans_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "videos": self.videos,
            "views": self.views,
            "photo": self.photo,
            "photo_url": self.photo_url,
            "gender": self.gender,
            "url": self.url,
            "birthdate": self.birthdate,
            "age": self.age,
            "country": self.country,
            "category": self.category,
            "onlyfans_url": self.onlyfans_url,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Performer":
        return cls(
            name=d.get("name", ""),
            videos=d.get("videos", 0),
            views=d.get("views", 0),
            photo=d.get("photo"),
            photo_url=d.get("photo_url"),
            gender=d.get("gender"),
            url=d.get("url"),
            birthdate=d.get("birthdate"),
            age=d.get("age"),
            country=d.get("country"),
            category=d.get("category"),
            onlyfans_url=d.get("onlyfans_url"),
        )


class PerformerDatabase:
    """In-memory performer directory with advanced search/filter/sort helpers."""

    def __init__(self, config: PerformerConfig | None = None) -> None:
        self.config = config or PerformerConfig()
        self._records: dict[str, Performer] = {}
        self._index_file = Path(self.config.data_dir) / "performer_index.json"

    def build(self) -> "PerformerDatabase":
        """Scan xlsx metadata + photos and normalise into records."""
        data_dir = Path(self.config.data_dir)
        stats = self._load_xlsx_stats(data_dir)
        photos = self._scan_photos(data_dir)

        # 1. Seed records from master stats list
        for name, (videos, views) in stats.items():
            self._records[name] = Performer(
                name=name,
                videos=videos,
                views=views,
            )

        # 2. Add photo-only performers and attach photos
        for name, photo in photos.items():
            if name not in self._records:
                self._records[name] = Performer(name=name, gender="female")
            self._records[name].photo = photo

        # 3. Enrich with verified seed profiles (Age, Country, OnlyFans, Categories)
        self._apply_known_profiles()

        logger.info("Built performer database: %d records (%d photos)", len(self._records), len(photos))
        return self

    def _apply_known_profiles(self) -> None:
        """Enrich existing and new records with curated seed metadata."""
        try:
            from research.performers.seed_data import KNOWN_PERFORMER_PROFILES
            for name, meta in KNOWN_PERFORMER_PROFILES.items():
                rec = self._records.get(name)
                if rec is None:
                    rec = Performer(name=name)
                    self._records[name] = rec
                
                if meta.get("age"):
                    rec.age = meta["age"]
                if meta.get("country"):
                    rec.country = meta["country"]
                if meta.get("category"):
                    rec.category = meta["category"]
                if meta.get("onlyfans_url"):
                    rec.onlyfans_url = meta["onlyfans_url"]
                if meta.get("gender"):
                    rec.gender = meta["gender"]
                if meta.get("videos") and (not rec.videos or meta["videos"] < rec.videos):
                    rec.videos = meta["videos"]
                if meta.get("views") and not rec.views:
                    rec.views = meta["views"]
        except Exception as e:
            logger.debug("Failed to enrich with seed profiles: %s", e)

    def save(self) -> None:
        """Persist normalized index JSON."""
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
        """Load previously persisted index; syncs any new photos from disk."""
        if not self._index_file.exists():
            return False
        try:
            data = json.loads(self._index_file.read_text(encoding="utf-8"))
        except Exception:
            return False
        self._records = {d["name"]: Performer.from_dict(d) for d in data}

        # Sync disk photos in case files were added
        photos = self._scan_photos(Path(self.config.data_dir))
        for name, photo in photos.items():
            if name in self._records:
                self._records[name].photo = photo
            else:
                self._records[name] = Performer(name=name, photo=photo, gender="female")

        # Re-apply verified seed metadata
        self._apply_known_profiles()

        return True

    def search(
        self,
        query: str = "",
        gender: str | None = None,
        has_photo: bool | None = None,
        category: str | None = None,
        country: str | None = None,
        age_min: int | None = None,
        age_max: int | None = None,
        sort_by: str = "has_photo",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Performer]:
        """Return performers matching rich criteria, sorted."""
        q = query.strip().lower()
        cat_q = (category or "").strip().lower()
        country_q = (country or "").strip().lower()

        results: list[Performer] = []
        for rec in self.all_records():
            if q and q not in rec.name.lower():
                continue
            if gender and gender not in ("all", "any", "") and rec.gender and rec.gender != gender:
                continue
            if has_photo is True and not rec.photo:
                continue
            if cat_q and cat_q not in ("all", "any", ""):
                if not rec.category or cat_q not in rec.category.lower():
                    continue
            if country_q and country_q not in ("all", "any", ""):
                if not rec.country or country_q not in rec.country.lower():
                    continue
            if age_min is not None and (rec.age is None or rec.age < age_min):
                continue
            if age_max is not None and (rec.age is None or rec.age > age_max):
                continue

            results.append(rec)

        # Sorting logic
        if sort_by == "name":
            results.sort(key=lambda r: r.name.lower())
        elif sort_by == "videos":
            results.sort(key=lambda r: r.videos, reverse=True)
        elif sort_by == "age_asc":
            results.sort(key=lambda r: (r.age is None, r.age or 999))
        elif sort_by == "age_desc":
            results.sort(key=lambda r: (r.age is None, -(r.age or 0)))
        elif sort_by == "has_photo":
            # Show records WITH photos first, ordered by views
            results.sort(key=lambda r: (0 if r.photo else 1, -r.views))
        else:  # default views
            results.sort(key=lambda r: r.views, reverse=True)

        return results[offset : offset + limit]

    def get(self, name: str) -> Performer | None:
        return self._records.get(name)

    def all_records(self) -> Iterator[Performer]:
        return iter(self._records.values())

    def count(self) -> int:
        return len(self._records)

    def photo_path(self, photo: str) -> Path | None:
        if not photo:
            return None
        p = Path(self.config.data_dir) / "photos" / photo
        return p if p.exists() else None

    def names_with_photos(self) -> list[str]:
        return [r.name for r in self.all_records() if r.photo]

    @staticmethod
    def _load_xlsx_stats(data_dir: Path) -> dict[str, tuple[int, int]]:
        stats: dict[str, tuple[int, int]] = {}
        try:
            import openpyxl
        except ImportError:
            return stats

        master = data_dir / "ph_starts_p_all.xlsx"
        if not master.exists():
            return stats
        try:
            wb = openpyxl.load_workbook(master, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                name = str(row[0]).strip()
                videos = int(float(row[1])) if row[1] is not None else 0
                views = int(float(row[2])) if row[2] is not None else 0
                stats[name] = (videos, views)
            wb.close()
        except Exception:
            pass
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


def build_performer_database(force: bool = False) -> PerformerDatabase:
    db = PerformerDatabase()
    if not force and db.load():
        return db
    db.build()
    db.save()
    return db