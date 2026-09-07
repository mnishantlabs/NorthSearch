"""Unified visual and face similarity search engine for the local database."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

from research.performers.database import PerformerDatabase

logger = logging.getLogger(__name__)


def compute_dhash(image_path: Path, hash_size: int = 8) -> int:
    """Compute difference hash (dHash) using pure PIL or fallback without heavy deps."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            diff = []
            for row in range(hash_size):
                for col in range(hash_size):
                    left = pixels[row * (hash_size + 1) + col]
                    right = pixels[row * (hash_size + 1) + col + 1]
                    diff.append(left > right)
            decimal_val = 0
            for index, val in enumerate(diff):
                if val:
                    decimal_val |= 1 << index
            return decimal_val
    except Exception:
        return 0


def hamming_distance(hash1: int, hash2: int) -> int:
    """Hamming distance between two integer hashes."""
    x = (hash1 ^ hash2) & ((1 << 64) - 1)
    return bin(x).count("1")


class LocalVisualSearchEngine:
    """Searches local database by face similarity and visual image hashing."""

    def __init__(self, db: PerformerDatabase) -> None:
        self.db = db
        self._face_engine: Any = None
        self._photo_hashes: dict[str, int] = {}
        self._hashes_loaded = False

    @property
    def face_engine(self) -> Any:
        if self._face_engine is None:
            from research.performers.faces import FaceSimilarityEngine
            self._face_engine = FaceSimilarityEngine(self.db)
        return self._face_engine

    def _ensure_photo_hashes(self) -> None:
        if self._hashes_loaded:
            return
        for rec in self.db.all_records():
            if rec.photo:
                p = self.db.photo_path(rec.photo)
                if p and p.exists():
                    h = compute_dhash(p)
                    if h:
                        self._photo_hashes[rec.name] = h
        self._hashes_loaded = True

    def search_image(
        self,
        image_path: Path,
        top_k: int = 8,
        search_type: str = "auto",  # auto, face, visual
    ) -> list[dict[str, Any]]:
        """Search local DB for matches using face similarity or perceptual image hash."""
        results: list[dict[str, Any]] = []

        # 1. Try Face Search first if auto or face
        if search_type in ("auto", "face"):
            try:
                if self.face_engine.requires_build():
                    self.face_engine.build_index()
                face_matches = self.face_engine.search(image_path, top_k=top_k)
                if face_matches:
                    for m in face_matches:
                        results.append({
                            "name": m.get("name", ""),
                            "similarity": m.get("similarity", 0.0),
                            "similarity_pct": int(round(m.get("similarity", 0.0) * 100)),
                            "match_type": "face",
                            "photo": m.get("photo", ""),
                            "videos": m.get("videos", 0),
                            "views": m.get("views", 0),
                            "url": m.get("url", ""),
                            "gender": m.get("gender", ""),
                        })
                    return results[:top_k]
            except Exception as e:
                logger.debug("Face similarity engine unavailable or no face: %s", e)

        # 2. Fallback to perceptual visual hashing (dHash similarity)
        self._ensure_photo_hashes()
        query_hash = compute_dhash(image_path)
        if query_hash and self._photo_hashes:
            scores: list[tuple[str, float]] = []
            for name, phash in self._photo_hashes.items():
                dist = hamming_distance(query_hash, phash)
                # 64-bit hash, distance 0 is 100% match, distance 64 is 0%
                sim = max(0.0, 1.0 - (dist / 64.0))
                scores.append((name, sim))

            scores.sort(key=lambda s: s[1], reverse=True)
            for name, sim in scores[:top_k]:
                rec = self.db.get(name)
                if rec:
                    results.append({
                        "name": rec.name,
                        "similarity": round(sim, 3),
                        "similarity_pct": int(round(sim * 100)),
                        "match_type": "visual_hash",
                        "photo": rec.photo or "",
                        "videos": rec.videos,
                        "views": rec.views,
                        "url": rec.url or "",
                        "gender": rec.gender or "",
                    })

        return results[:top_k]
