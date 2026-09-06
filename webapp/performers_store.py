"""Web-facing helpers for the performer directory.

These are long-running singletons (database + ONNX face models) shared across
HTTP requests. Model loading and the embedding index are built lazily on the
first face search, so the server starts fast.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from research.config import load_config
from research.performers.database import build_performer_database

logger = logging.getLogger(__name__)

_db = None
_db_lock = threading.Lock()
_crawl_lock = threading.Lock()
_crawl_status: dict[str, Any] = {"state": "idle", "collected": 0, "error": None}


def get_db():
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                cfg = load_config().performers
                _db = build_performer_database()
    return _db


def get_engine():
    from research.performers.faces import get_face_engine

    return get_face_engine(get_db())


def performer_status() -> dict[str, Any]:
    db = get_db()
    from research.performers.faces import get_face_engine

    engine = get_engine()
    index = Path(db.config.data_dir) / "embedding_index.npz"
    return {
        "count": db.count(),
        "photos": len(db.names_with_photos()),
        "face_index": index.exists(),
        "index_building": engine._emb is None and not index.exists(),
        "crawl": _crawl_status.copy(),
    }


def performer_browse(
    query: str = "",
    gender: str | None = None,
    sort_by: str = "views",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    db = get_db()
    rows = db.search(query=query, gender=gender, sort_by=sort_by, limit=limit, offset=offset)
    return {
        "total": db.count(),
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "name": r.name,
                "videos": r.videos,
                "views": r.views,
                "photo": r.photo,
                "url": r.url,
                "gender": r.gender,
            }
            for r in rows
        ],
    }


def performer_face_search(path: Path, top_k: int | None = None) -> dict[str, Any]:
    engine = get_engine()
    if engine.requires_build():
        engine.build_index()
    results = engine.search(path, top_k=top_k)
    return {
        "input": path.name,
        "results": results,
    }


def performer_crawl(
    max_performers: int = 100,
    pages: int = 6,
    gender: str = "female",
) -> dict[str, Any]:
    """Start a background crawl; returns the job summary."""
    def _run() -> None:
        cfg = load_config().performers
        from research.performers.crawler import PerformerCrawler
        from research.performers.database import build_performer_database
        from research.performers.faces import FaceSimilarityEngine

        crawler = PerformerCrawler(
            cfg.data_dir,
            gender=gender,
            max_performers=max_performers,
            pages=pages,
        )
        try:
            result = crawler.run()
            _crawl_status["state"] = "done"
            _crawl_status["collected"] = result["collected"]
            # refresh DB + face index with new photos
            db = build_performer_database(force=True)
            db.save()
            try:
                FaceSimilarityEngine(db).build_index(force=True)
            except Exception:  # noqa: BLE001
                logger.warning("Face index rebuild failed after crawl", exc_info=True)
        except Exception as e:  # noqa: BLE001
            _crawl_status["state"] = "error"
            _crawl_status["error"] = str(e)
        finally:
            crawler.close()
            _crawl_status["state"] = "idle" if _crawl_status["state"] == "error" else "done"

    acquired = _crawl_lock.acquire(blocking=False)
    if not acquired:
        return {"error": "A crawl is already running"}
    _crawl_status.update({"state": "running", "collected": 0, "error": None})
    threading.Thread(target=_run, daemon=True, name="performer-crawl").start()
    return {"state": "running"}