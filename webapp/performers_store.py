"""Web-facing helpers for performer directory, visual search, and creator crawlers."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from research.config import load_config
from research.extraction.scraper import ContentScraper
from research.performers.creator_crawler import CreatorCrawler
from research.performers.database import build_performer_database
from research.performers.visual_search import LocalVisualSearchEngine
from research.search.reverse_image import OnlineReverseImageSearcher

logger = logging.getLogger(__name__)

_db = None
_db_lock = threading.Lock()
_visual_engine = None
_reverse_searcher = None
_creator_crawler = None

_scraper_lock = threading.Lock()
_crawler_stop_event = threading.Event()
_crawler_pause_event = threading.Event()

_scraper_status: dict[str, Any] = {
    "state": "idle",
    "message": "",
    "collected": 0,
    "total": 0,
    "category": "",
    "error": None,
}


def get_db():
    global _db
    if _db is None:
        with _db_lock:
            if _db is None:
                _db = build_performer_database(force=False)
    return _db


def get_visual_engine() -> LocalVisualSearchEngine:
    global _visual_engine
    if _visual_engine is None:
        _visual_engine = LocalVisualSearchEngine(get_db())
    return _visual_engine


def get_reverse_searcher() -> OnlineReverseImageSearcher:
    global _reverse_searcher
    if _reverse_searcher is None:
        _reverse_searcher = OnlineReverseImageSearcher()
    return _reverse_searcher


def get_creator_crawler() -> CreatorCrawler:
    global _creator_crawler
    if _creator_crawler is None:
        _creator_crawler = CreatorCrawler(get_db())
    return _creator_crawler


def performer_status() -> dict[str, Any]:
    db = get_db()
    index = Path(db.config.data_dir) / "embedding_index.npz"
    st = _scraper_status.copy()
    if st["total"] > 0:
        st["percent"] = min(100, int((st["collected"] / st["total"]) * 100))
    else:
        st["percent"] = 0
    return {
        "count": db.count(),
        "photos": len(db.names_with_photos()),
        "face_index": index.exists(),
        "scraper": st,
    }


def performer_browse(
    query: str = "",
    gender: str | None = None,
    has_photo: bool | None = None,
    category: str | None = None,
    country: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    sort_by: str = "has_photo",
    limit: int = 48,
    offset: int = 0,
) -> dict[str, Any]:
    db = get_db()
    rows = db.search(
        query=query,
        gender=gender,
        has_photo=has_photo,
        category=category,
        country=country,
        age_min=age_min,
        age_max=age_max,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return {
        "total": db.count(),
        "photos_total": len(db.names_with_photos()),
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "name": r.name,
                "videos": r.videos,
                "views": r.views,
                "photo": r.photo,
                "photo_url": r.photo_url,
                "url": r.url,
                "gender": r.gender,
                "age": r.age,
                "country": r.country,
                "category": r.category,
                "onlyfans_url": r.onlyfans_url,
            }
            for r in rows
        ],
    }


def dual_image_search(path: Path, top_k: int = 8) -> dict[str, Any]:
    """Runs simultaneous local DB similarity match + online reverse search."""
    local_matches: list[dict[str, Any]] = []
    online_matches: list[dict[str, Any]] = []

    try:
        v_engine = get_visual_engine()
        local_matches = v_engine.search_image(path, top_k=top_k)
    except Exception as e:
        logger.warning("Local visual search error: %s", e)

    try:
        r_searcher = get_reverse_searcher()
        online_matches = r_searcher.search(path, max_results=top_k)
    except Exception as e:
        logger.warning("Online reverse search error: %s", e)

    return {
        "image_name": path.name,
        "local_matches": local_matches,
        "online_matches": online_matches,
    }


def pause_crawler() -> dict[str, Any]:
    if _scraper_status.get("state") == "running":
        _crawler_pause_event.set()
        _scraper_status["state"] = "paused"
        _scraper_status["message"] = "Crawler paused by user."
        return {"success": True, "state": "paused", "message": "Crawler paused."}
    return {"success": False, "message": "Crawler is not currently running."}


def resume_crawler() -> dict[str, Any]:
    if _scraper_status.get("state") == "paused":
        _crawler_pause_event.clear()
        _scraper_status["state"] = "running"
        _scraper_status["message"] = "Resumed crawling..."
        return {"success": True, "state": "running", "message": "Crawler resumed."}
    return {"success": False, "message": "Crawler is not currently paused."}


def stop_crawler() -> dict[str, Any]:
    if _scraper_status.get("state") in ("running", "paused"):
        _crawler_stop_event.set()
        _crawler_pause_event.clear()
        _scraper_status["state"] = "stopped"
        _scraper_status["message"] = f"Stopping crawler... Saved {_scraper_status.get('collected', 0)} records."
        return {"success": True, "state": "stopped", "message": "Crawler stopping."}
    return {"success": False, "message": "No active crawler to stop."}


def start_creator_crawl(
    max_performers: int = 150,
    category: str = "OnlyFans Star",
) -> dict[str, Any]:
    """Start background crawler for creator/OnlyFans stars with pause & stop capability."""
    def _run() -> None:
        db = get_db()
        crawler = CreatorCrawler(db)

        def _progress(msg: str, cur: int, tot: int) -> None:
            _scraper_status.update({
                "message": msg,
                "collected": cur,
                "total": tot,
            })

        try:
            res = crawler.crawl_creators(
                max_performers=max_performers,
                category=category,
                progress_cb=_progress,
                stop_event=_crawler_stop_event,
                pause_event=_crawler_pause_event,
            )
            if _crawler_stop_event.is_set():
                _scraper_status["state"] = "stopped"
                _scraper_status["message"] = f"Stopped. Saved {res.get('collected', 0)} updated profiles."
            else:
                _scraper_status["state"] = "done"
                _scraper_status["message"] = f"Finished! Indexed & updated {res.get('collected', 0)} creator profiles."
        except Exception as e:
            _scraper_status["state"] = "error"
            _scraper_status["error"] = str(e)
            _scraper_status["message"] = f"Error: {e}"
        finally:
            crawler.close()
            try:
                _scraper_lock.release()
            except Exception:
                pass

    acquired = _scraper_lock.acquire(blocking=False)
    if not acquired:
        return {"error": "A crawl/scrape is already in progress"}

    _crawler_stop_event.clear()
    _crawler_pause_event.clear()

    _scraper_status.update({
        "state": "running",
        "message": f"Updating database with {category}...",
        "collected": 0,
        "total": max_performers,
        "category": category,
        "error": None,
    })
    threading.Thread(target=_run, daemon=True, name="creator-crawl").start()
    return {"state": "running", "message": f"Started {category} crawler for {max_performers} performers."}


def run_custom_scrape(
    url: str,
    must_include_keywords: list[str] | None = None,
    must_exclude_keywords: list[str] | None = None,
    max_items: int = 50,
    download_images: bool = True,
) -> dict[str, Any]:
    def _run() -> None:
        db = get_db()
        scraper = ContentScraper(db)

        def _progress(msg: str, current: int, total: int) -> None:
            _scraper_status.update({
                "message": msg,
                "collected": current,
                "total": total,
            })

        try:
            res = scraper.scrape_url(
                url=url,
                must_include_keywords=must_include_keywords,
                must_exclude_keywords=must_exclude_keywords,
                download_images=download_images,
                max_items=max_items,
                progress_cb=_progress,
            )
            _scraper_status["state"] = "done"
            _scraper_status["message"] = f"Finished! Scraped {res.get('items_added', 0)} matching items."
        except Exception as e:
            _scraper_status["state"] = "error"
            _scraper_status["error"] = str(e)
            _scraper_status["message"] = f"Error: {e}"
        finally:
            scraper.close()

    acquired = _scraper_lock.acquire(blocking=False)
    if not acquired:
        return {"error": "A scraping task is already running."}

    _scraper_status.update({
        "state": "running",
        "message": f"Starting scraper on {url}...",
        "collected": 0,
        "total": max_items,
        "error": None,
    })
    threading.Thread(target=_run, daemon=True, name="custom-scraper").start()
    return {"state": "running", "message": "Scraper task started."}


def auto_fetch_avatar(name: str) -> str | None:
    crawler = get_creator_crawler()
    return crawler.fetch_photo_for_name(name)


def performer_crawl(
    max_performers: int = 100,
    pages: int = 6,
    gender: str = "female",
) -> dict[str, Any]:
    return start_creator_crawl(max_performers=max_performers, category="Top Star")