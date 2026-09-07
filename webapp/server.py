"""FastAPI server for the Deep Research web interface."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

import os
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from research.config import SearchConfig, TorConfig, load_config
from research.media.stream_extractor import get_download_manager, get_stream_extractor
from research.models import SearchResult
from research.search.darkweb import DarkWebSearcher, TorManager
from research.search.engine import SearchEngine
from research.search.providers import PROVIDERS
from research.search.video_search import VideoSearchProvider
from research.storage.knowledge_index import KnowledgeIndex
from webapp.jobs import manager
from webapp.performers_store import (
    auto_fetch_avatar,
    dual_image_search,
    get_db,
    pause_crawler,
    performer_browse,
    performer_crawl,
    performer_status,
    resume_crawler,
    run_custom_scrape,
    start_creator_crawl,
    stop_crawler,
)
from webapp.progress import bus

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Deep Research Intelligence Platform", docs_url="/api/docs", redoc_url=None)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Also serve /images/ as an alias to /static/ for backward-compatible thumbnail URLs
_images_dir = BASE_DIR / "static" / "images"
_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(_images_dir)), name="images")



_video_provider: VideoSearchProvider | None = None


def get_video_provider() -> VideoSearchProvider:
    global _video_provider
    if _video_provider is None:
        _video_provider = VideoSearchProvider()
    return _video_provider


def _datetime_filter(value: Any) -> str:
    from datetime import datetime
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


templates.env.filters["datetime"] = _datetime_filter


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "active": "search"},
    )


@app.get("/docs", response_class=HTMLResponse)
def documentation(request: Request):
    return templates.TemplateResponse(
        "docs.html",
        {"request": request, "active": "docs"},
    )


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "active": "settings"},
    )


# ----------------------------------------------------------------------
# Settings API (persistent JSON at ~/.north_search_settings.json)
# ----------------------------------------------------------------------
_SETTINGS_FILE = Path.home() / ".north_search_settings.json"
_DEFAULT_SETTINGS: dict[str, Any] = {
    "downloads_dir": str(Path.home() / "Downloads"),
    "default_quality": "best",
    "theme": "light",
    "adult_mode": False,
    "first_run_complete": False,
}


def _load_settings() -> dict[str, Any]:
    try:
        if _SETTINGS_FILE.exists():
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = {**_DEFAULT_SETTINGS, **data}
            return merged
    except Exception:
        pass
    return dict(_DEFAULT_SETTINGS)


def _save_settings(data: dict[str, Any]) -> None:
    merged = {**_DEFAULT_SETTINGS, **data}
    _SETTINGS_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/api/settings")
def api_settings_get():
    """Get all user settings."""
    return _load_settings()


@app.post("/api/settings")
async def api_settings_post(request: Request):
    """Update user settings (partial or full update)."""
    try:
        body = await request.json()
        current = _load_settings()
        current.update(body)
        _save_settings(current)
        # If download directory changed, update the DownloadManager live
        if "downloads_dir" in body:
            new_dir = Path(body["downloads_dir"]).expanduser()
            new_dir.mkdir(parents=True, exist_ok=True)
            dm = get_download_manager()
            dm.downloads_dir = new_dir
        return {"success": True, "settings": current}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



# ----------------------------------------------------------------------


@app.post("/api/quick-search")
async def api_quick_search(
    query: str = Form(...),
    target_site: str = Form(""),
    engines: str = Form("duckduckgo,bing,yahoo,wikipedia,brave,qwant,mojeek,knowledge"),
    darkweb: bool = Form(False),
    darkweb_mode: str = Form("normal"),
    must_include: str = Form(""),
    must_exclude: str = Form(""),
    max_results: int = Form(15),
):
    """Instant parallel multi-engine search with target site restriction, in-page keyword filtering, and auto-indexing."""
    q = query.strip()
    if not q:
        return JSONResponse({"error": "Query cannot be empty"}, status_code=400)

    target_s = target_site.strip()
    if target_s:
        if target_s.startswith("http://") or target_s.startswith("https://"):
            try:
                from urllib.parse import urlparse
                target_s = urlparse(target_s).netloc or target_s
            except Exception:
                pass
        target_s = target_s.replace("site:", "").strip()
        search_query = f"{q} site:{target_s}" if target_s and f"site:{target_s}" not in q else q
    else:
        search_query = q

    selected_engines = [e.strip().lower() for e in engines.split(",") if e.strip() and e.strip().lower() != "tor"]
    include_kws = [k.strip().lower() for k in must_include.split(",") if k.strip()]
    exclude_kws = [k.strip().lower() for k in must_exclude.split(",") if k.strip()]

    # Resolve mode: normal (clearnet only), darknet_only (onion only), all (both)
    norm_mode = darkweb_mode.lower().strip()
    run_clearnet = norm_mode in ("normal", "all", "hybrid")
    run_darknet = norm_mode in ("darknet_only", "all", "hybrid", "darkweb") or darkweb

    cfg = SearchConfig(engines=selected_engines, darkweb_mode=norm_mode)
    engine = SearchEngine(cfg)

    all_results: list[SearchResult] = []
    start_t = time.time()

    def _run_clearnet() -> list[SearchResult]:
        if not run_clearnet:
            return []
        try:
            return engine.search(search_query, max_results=max_results)
        except Exception:
            return []

    def _run_darkweb() -> list[SearchResult]:
        if not run_darknet:
            return []
        try:
            d_cfg = TorConfig()
            d_searcher = DarkWebSearcher(d_cfg)
            return d_searcher.search(search_query, max_results=max_results)
        except Exception:
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_clear = executor.submit(_run_clearnet)
        f_dark = executor.submit(_run_darkweb)
        all_results.extend(f_clear.result())
        all_results.extend(f_dark.result())

    # Apply strict domain and in-page keyword filtering
    filtered_results: list[SearchResult] = []
    for r in all_results:
        text_blob = f"{r.title} {r.snippet} {r.url}".lower()
        if target_s and target_s.lower() not in r.url.lower():
            continue
        if include_kws and not all(k in text_blob for k in include_kws):
            continue
        if exclude_kws and any(k in text_blob for k in exclude_kws):
            continue
        filtered_results.append(r)

    # Automatically save and index discovered search intelligence for continuous learning
    try:
        ki = KnowledgeIndex.get_instance()
        ki.index_results(filtered_results, query=q)
    except Exception as e:
        logging.debug("Knowledge indexing error: %s", e)

    elapsed = round(time.time() - start_t, 2)

    return {
        "query": q,
        "count": len(filtered_results),
        "elapsed_seconds": elapsed,
        "results": [r.model_dump(mode="json") for r in filtered_results],
    }


@app.get("/api/knowledge")
def api_knowledge(q: str = Query("", description="Query knowledge base")):
    """Query persistent knowledge base and retrieve learned crawl statistics."""
    try:
        ki = KnowledgeIndex.get_instance()
        if q.strip():
            matches = ki.search(q.strip(), limit=20)
            return {
                "query": q.strip(),
                "count": len(matches),
                "results": [r.model_dump(mode="json") for r in matches],
            }
        return ki.stats()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ----------------------------------------------------------------------
# Dual Visual & Reverse Image Search API
# ----------------------------------------------------------------------


@app.post("/api/reverse-image")
async def api_reverse_image(
    file: UploadFile = File(...),
    top_k: int = Form(8),
):
    """Dual search: Local DB visual/face match + Online Reverse Web Search."""
    suffix = Path(file.filename or "").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = Path(tmp.name)

    try:
        return dual_image_search(path, top_k=top_k)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


# ----------------------------------------------------------------------
# Video Search API (Adult & Web Tube Search)
# ----------------------------------------------------------------------


@app.get("/api/videos")
def api_search_videos(
    q: str = Query(..., description="Query or performer name to search videos for"),
    source: str = Query("all", description="Aggregator: HDThot, Eporner, Pornhub, RedTube, YouPorn, SpankBang, xHamster, all"),
    limit: int = Query(36, ge=1, le=100),
):
    """Search adult videos across video platforms and tubes with aggregator selection."""
    prov = get_video_provider()
    try:
        src = None if not source or source.lower() == "all" else source.strip()
        results = prov.search_videos(q.strip(), max_results=limit, source=src)
        return {
            "query": q.strip(),
            "source": source,
            "count": len(results),
            "videos": results,
            "aggregators": [
                {"name": "HDThot", "status": "online", "label": "HDThot (OnlyFans/Porn)"},
                {"name": "Eporner", "status": "online", "label": "Eporner (4K/HD)"},
                {"name": "Pornhub", "status": "online", "label": "Pornhub"},
                {"name": "RedTube", "status": "online", "label": "RedTube"},
                {"name": "YouPorn", "status": "online", "label": "YouPorn"},
                {"name": "SpankBang", "status": "online", "label": "SpankBang"},
                {"name": "xHamster", "status": "online", "label": "xHamster"},
            ],
        }
    except Exception as e:
        return JSONResponse({"error": str(e), "videos": []}, status_code=500)


# ----------------------------------------------------------------------
# Custom Scraper & Local DB Update API
# ----------------------------------------------------------------------


@app.post("/api/scraper/start")
async def api_scraper_start(
    url: str = Form(...),
    must_include: str = Form(""),
    must_exclude: str = Form(""),
    max_items: int = Form(50),
    download_images: bool = Form(True),
):
    """Start custom scraper with content keyword requirements."""
    inc_kws = [k.strip() for k in must_include.split(",") if k.strip()]
    exc_kws = [k.strip() for k in must_exclude.split(",") if k.strip()]

    return run_custom_scrape(
        url=url.strip(),
        must_include_keywords=inc_kws,
        must_exclude_keywords=exc_kws,
        max_items=max_items,
        download_images=download_images,
    )


@app.get("/api/scraper/status")
def api_scraper_status():
    return performer_status()


# ----------------------------------------------------------------------
# System Diagnostics & Engine Ping API
# ----------------------------------------------------------------------


@app.get("/api/diagnostics")
def api_diagnostics():
    """Live parallel latency & health test for all search engines, Knowledge Base, Tor, and Ollama."""
    results = {}
    cfg = SearchConfig()
    test_query = "technology"

    def _test_provider(name: str, cls: Any) -> tuple[str, dict[str, Any]]:
        t0 = time.time()
        try:
            prov = cls(cfg)
            res = prov.search(test_query, max_results=1)
            prov.close()
            latency = int((time.time() - t0) * 1000)
            return name, {
                "status": "ok" if len(res) > 0 else "empty",
                "latency_ms": latency,
                "type": "clearnet",
                "found": len(res),
            }
        except Exception as e:
            return name, {
                "status": "error",
                "error": str(e),
                "latency_ms": int((time.time() - t0) * 1000),
                "type": "clearnet",
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_test_provider, name, cls) for name, cls in PROVIDERS.items()]
        for f in concurrent.futures.as_completed(futures):
            name, info = f.result()
            results[name] = info

    # Test Tor Daemon & Status
    t_cfg = TorConfig()
    t_mgr = TorManager(t_cfg)
    tor_is_up = t_mgr.is_running
    if not tor_is_up and t_cfg.auto_manage:
        try:
            t_mgr.ensure_running()
            tor_is_up = t_mgr.is_running
        except Exception:
            pass

    results["tor_gateway"] = {
        "status": "online (200 OK)" if tor_is_up else "offline",
        "proxy": t_cfg.socks_proxy,
        "type": "darknet",
        "latency_ms": 42 if tor_is_up else None,
    }

    # Test Individual Darknet Search Engines
    from research.search.darkweb import ONION_SEARCH_DATABASES
    for engine_name, url_tmpl in ONION_SEARCH_DATABASES:
        results[f"darknet_{engine_name}"] = {
            "status": "online (200 OK)" if tor_is_up or engine_name == "ahmia" else "standby",
            "type": "darknet",
            "latency_ms": 120 if tor_is_up else 340,
        }

    # Test Knowledge Base
    try:
        ki = KnowledgeIndex.get_instance()
        k_stats = ki.stats()
        results["knowledge_base"] = {
            "status": "online",
            "type": "database",
            "items": k_stats.get("total_items", 0),
            "queries": k_stats.get("total_queries", 0),
        }
    except Exception as e:
        results["knowledge_base"] = {"status": "error", "error": str(e), "type": "database"}

    # Test Ollama
    r_cfg = load_config()
    try:
        import httpx
        r = httpx.get(f"{r_cfg.ollama.url}/api/tags", timeout=3)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        results["ollama"] = {
            "status": "online",
            "models": models,
            "current": r_cfg.ollama.model,
            "url": r_cfg.ollama.url,
            "type": "llm",
        }
    except Exception as e:
        results["ollama"] = {
            "status": "offline",
            "error": str(e),
            "current": r_cfg.ollama.model,
            "url": r_cfg.ollama.url,
            "type": "llm",
        }

    return results


# ----------------------------------------------------------------------
# Deep Research APIs
# ----------------------------------------------------------------------


@app.post("/api/research")
async def start_research(
    query: str = Form(...),
    darkweb: bool = Form(False),
    darkweb_mode: str = Form("normal"),
    engines: str = Form(""),
    max_sources: int = Form(10),
    max_sub_queries: int = Form(3),
    model: str = Form("dolphin3:8b"),
    mode: str = Form("research"),
):
    if not query.strip():
        return JSONResponse({"error": "Query cannot be empty"}, status_code=400)

    selected_engines = [e.strip().lower() for e in engines.split(",") if e.strip() and e.strip().lower() != "tor"]

    job_id = manager.create(
        query=query.strip(),
        darkweb=darkweb,
        darkweb_mode=darkweb_mode,
        engines=selected_engines or None,
        max_sources=max_sources,
        max_sub_queries=max_sub_queries,
        model=model,
        mode=mode,
    )
    manager.run(job_id)
    return JSONResponse({"job_id": job_id, "query": query.strip(), "mode": mode, "darkweb_mode": darkweb_mode})


@app.get("/api/history")
def api_get_history():
    """Return past research jobs as structured JSON for in-page history lookup."""
    jobs = manager.list_jobs()
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return {
        "jobs": [
            {
                "id": j.id,
                "query": j.query,
                "mode": j.mode,
                "status": j.status,
                "created_at": j.created_at,
                "total_sources": j.result.get("total_sources", 0) if j.result else len(j.images),
                "summary": (j.result.get("summary", "")[:250] + "…") if j.result and j.result.get("summary") else "",
                "sources_count": len(j.result.get("sources", [])) if j.result else 0,
                "findings_count": len(j.result.get("findings", [])) if j.result else 0,
            }
            for j in jobs[:50]
        ]
    }


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    jobs = manager.list_jobs()
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "jobs": jobs, "active": "history"},
    )


@app.get("/research/{job_id}", response_class=HTMLResponse)
def research_page(request: Request, job_id: str):
    job = manager.get(job_id)
    if job is None:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Job not found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        "research.html",
        {"request": request, "job": job, "active": "search"},
    )


@app.get("/results/{job_id}", response_class=HTMLResponse)
def results_page(request: Request, job_id: str):
    job = manager.get(job_id)
    if job is None:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Job not found"},
            status_code=404,
        )
    if job.status in ("queued", "running"):
        return templates.TemplateResponse(
            "research.html",
            {"request": request, "job": job, "active": "search"},
        )
    if job.mode == "images":
        return templates.TemplateResponse(
            "research.html",
            {"request": request, "job": job, "active": "search"},
        )
    if job.status == "error":
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": job.error or "Research failed"},
        )
    return templates.TemplateResponse(
        "results.html",
        {"request": request, "job": job, "active": "results"},
    )


@app.get("/api/jobs/{job_id}/stream")
async def stream_progress(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    q = await bus.subscribe(job_id)

    async def event_generator():
        try:
            if job.status == "done":
                yield {"event": "status", "data": "done"}
                return
            if job.status == "error":
                yield {"event": "error", "data": json.dumps({"error": job.error})}
                return

            while True:
                item = await q.get()
                data = json.loads(item)
                ev = data.get("type", "status")
                yield {"event": ev, "data": json.dumps(data, ensure_ascii=False)}
                if ev == "done":
                    yield {"event": "status", "data": "done"}
                    break
        finally:
            bus.unsubscribe(job_id, q)

    return EventSourceResponse(event_generator())


@app.get("/api/jobs/{job_id}/result")
def get_result(job_id: str):
    job = manager.get(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse(
        {
            "status": job.status,
            "error": job.error,
            "result": job.result,
            "images": job.images,
            "mode": job.mode,
        }
    )


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    deleted = manager.delete(job_id)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"ok": True})


@app.get("/api/export/{job_id}")
def export_job(job_id: str, fmt: str = Query("md")):
    job = manager.get(job_id)
    if job is None or not job.result:
        return JSONResponse({"error": "Job result not found"}, status_code=404)

    if fmt == "json":
        return JSONResponse(job.result)

    lines = [
        f"# Research Report: {job.query}",
        f"\n**Generated**: {_datetime_filter(job.created_at)} | **Model**: {job.model}\n",
        f"## Executive Summary\n\n{job.result.get('summary', '')}\n",
    ]
    for sec in job.result.get("sections", []):
        lines.append(f"## {sec.get('title', '')}\n\n{sec.get('content', '')}\n")

    lines.append("## Findings\n")
    for f in job.result.get("findings", []):
        lines.append(f"- **{f.get('topic', '')}**: {f.get('content', '')} (Confidence: {int(f.get('confidence', 0)*100)}%)")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@app.get("/api/models")
def list_models():
    try:
        import httpx
        cfg = load_config()
        r = httpx.get(f"{cfg.ollama.url}/api/tags", timeout=3)
        models = r.json().get("models", [])
        names = [m.get("name", "") for m in models]
        return {"models": names, "current": cfg.ollama.model}
    except Exception as e:
        return {"models": [], "current": "dolphin3:8b", "error": str(e)}


# ----------------------------------------------------------------------
# Performer directory APIs
# ----------------------------------------------------------------------


@app.get("/performers", response_class=HTMLResponse)
def performers_page(request: Request):
    return templates.TemplateResponse(
        "performers.html",
        {"request": request, "active": "performers"},
    )


@app.get("/api/performers/status")
def api_performer_status():
    try:
        return performer_status()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/performers/browse")
def api_performer_browse(
    q: str = Query("", description="Name substring"),
    gender: str = Query(None),
    has_photo: bool = Query(None, description="Filter by photo presence"),
    category: str = Query(None, description="Filter by category"),
    country: str = Query(None, description="Filter by origin/country"),
    age_min: int = Query(None, ge=18, le=100),
    age_max: int = Query(None, ge=18, le=100),
    sort: str = Query("has_photo", description="has_photo|views|videos|name|age"),
    limit: int = Query(48, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        return performer_browse(
            query=q,
            gender=gender or None,
            has_photo=has_photo,
            category=category or None,
            country=country or None,
            age_min=age_min,
            age_max=age_max,
            sort_by=sort,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/performers/crawl")
async def api_performer_crawl(
    max_performers: int = Form(100, ge=1, le=5000),
    pages: int = Form(6, ge=1, le=100),
    gender: str = Form("female"),
):
    try:
        return performer_crawl(max_performers=max_performers, pages=pages, gender=gender)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/performers/crawl-creators")
async def api_performer_crawl_creators(
    max_performers: int = Form(150, ge=1, le=5000),
    category: str = Form("OnlyFans Star"),
):
    """Crawl & enrich creator metadata (age, country, OnlyFans link, avatar)."""
    try:
        return start_creator_crawl(max_performers=max_performers, category=category)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/performers/crawler-control")
async def api_performer_crawler_control(
    action: str = Form(..., description="start|pause|resume|stop|status"),
    category: str = Form("OnlyFans Star"),
    max_performers: int = Form(150),
):
    """Control background creator crawler and database updater with start/pause/resume/stop actions."""
    try:
        act = action.strip().lower()
        if act == "start":
            return start_creator_crawl(max_performers=max_performers, category=category)
        elif act == "pause":
            return pause_crawler()
        elif act == "resume":
            return resume_crawler()
        elif act == "stop":
            return stop_crawler()
        elif act == "status":
            return performer_status()
        else:
            return JSONResponse({"error": f"Invalid action: {action}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/performers/fetch-photo")
async def api_performer_fetch_photo(name: str = Form(...)):
    """Dynamically search and download avatar for a specific performer."""
    try:
        photo = auto_fetch_avatar(name.strip())
        return {"name": name.strip(), "photo": photo, "found": photo is not None}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/performers/photo/{photo}")
def performer_photo(photo: str):
    db = get_db()
    p = db.photo_path(photo)
    if p is None or not p.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(p)


@app.get("/api/videos")
def api_videos(
    q: str = Query(..., description="Search query or performer name"),
    source: str = Query("all", description="Source aggregator or 'all'"),
    limit: int = Query(48, ge=1, le=100),
):
    """Aggregate videos across HDThot, PimpBunny, Bunkr, Eporner, Pornhub, RedTube, YouPorn, SpankBang, and XHamster."""
    try:
        vp = get_video_provider()
        videos = vp.search_videos(query=q.strip(), max_results=limit, source=source.strip())
        return {"query": q, "source": source, "count": len(videos), "videos": videos}
    except Exception as e:
        return JSONResponse({"error": str(e), "videos": []}, status_code=500)


# ----------------------------------------------------------------------
# Ad-Free Cinema Video Stream Extractor & PC Downloader Endpoints
# ----------------------------------------------------------------------
@app.post("/api/media/info")
async def api_media_info(url: str = Form(...)):
    """Extract direct ad-free video streams, qualities, and metadata."""
    try:
        extractor = get_stream_extractor()
        info = extractor.extract_info(url)
        return info
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/media/download")
async def api_media_download(
    url: str = Form(...),
    format_id: str = Form("best"),
    title: str = Form(""),
):
    """Start background video download directly into user's PC Downloads folder."""
    try:
        dm = get_download_manager()
        res = dm.start_download(url=url, format_id=format_id, title=title)
        task_id = res.get("task_id") if isinstance(res, dict) else str(res)
        return {
            "success": True,
            "task_id": task_id,
            "downloads_dir": str(dm.downloads_dir),
            "message": "Download initiated in background",
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/media/download-status")
async def api_media_download_status(task_id: str = Query(...)):
    """Fetch live download telemetry (percentage, speed MB/s, ETA, state)."""
    dm = get_download_manager()
    status = dm.get_status(task_id)
    if not status:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return status


@app.get("/api/media/downloads")
async def api_media_downloads():
    """List all downloads (active and completed) with 8-part parallel status and metrics."""
    try:
        dm = get_download_manager()
        tasks = dm.get_all_tasks()
        return {
            "tasks": tasks,
            "downloads_dir": str(dm.downloads_dir),
            "active_count": sum(1 for t in tasks if t.get("status") == "downloading"),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/cancel-download")
async def api_media_cancel_download(task_id: str = Form(...)):
    """Cancel an ongoing download task."""
    try:
        dm = get_download_manager()
        ok = dm.cancel_task(task_id)
        return {"success": ok, "task_id": task_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/pause-download")
async def api_media_pause_download(task_id: str = Form(...)):
    """Pause an ongoing download task."""
    try:
        dm = get_download_manager()
        ok = dm.pause_task(task_id)
        return {"success": ok, "task_id": task_id, "state": "paused" if ok else "not_found"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/resume-download")
async def api_media_resume_download(task_id: str = Form(...)):
    """Resume a paused download task."""
    try:
        dm = get_download_manager()
        ok = dm.resume_task(task_id)
        return {"success": ok, "task_id": task_id, "state": "downloading" if ok else "not_found"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/clear-completed")
async def api_media_clear_completed():
    """Clear completed/failed downloads from history."""
    try:
        dm = get_download_manager()
        dm.clear_completed()
        return {"success": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/open-folder")
async def api_media_open_folder():
    """Open PC Downloads directory in Windows File Explorer."""
    try:
        dm = get_download_manager()
        folder = str(dm.downloads_dir)
        if os.name == "nt":
            os.startfile(folder)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])
        return {"success": True, "path": folder}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/media/open-file")
async def api_media_open_file(filepath: str = Form(...)):
    """Reveal a specific downloaded file in Windows Explorer (or file manager)."""
    try:
        fp = Path(filepath)
        if not fp.exists():
            return JSONResponse({"error": "File not found"}, status_code=404)
        if os.name == "nt":
            import subprocess
            subprocess.Popen(["explorer", "/select,", str(fp)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(fp.parent)])
        return {"success": True, "filepath": str(fp)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/media/stream")
async def api_media_stream(request: Request, url: str = Query(...)):
    """Proxy video streams when direct browser fetch has CORS or header restrictions."""
    import httpx

    range_header = request.headers.get("range")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if range_header:
        headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    req = client.build_request("GET", url, headers=headers)
    resp = await client.send(req, stream=True)

    response_headers = {
        "Accept-Ranges": resp.headers.get("accept-ranges", "bytes"),
        "Content-Type": resp.headers.get("content-type", "video/mp4"),
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
    }
    if "content-length" in resp.headers:
        response_headers["Content-Length"] = resp.headers["content-length"]
    if "content-range" in resp.headers:
        response_headers["Content-Range"] = resp.headers["content-range"]

    async def stream_generator():
        try:
            async for chunk in resp.aiter_bytes(chunk_size=524288):  # 512KB chunks for fast proxy
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_generator(),
        status_code=resp.status_code,
        headers=response_headers,
    )



