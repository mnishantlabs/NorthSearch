"""FastAPI server for the Deep Research web interface."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import sse_starlette
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from webapp.jobs import manager
from webapp.performers_store import performer_face_search, performer_browse, performer_crawl, performer_status
from webapp.progress import bus

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).parent
app = FastAPI(title="Deep Research")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _datetime_filter(value) -> str:
    """Format a unix timestamp for the history table."""
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


@app.post("/api/research")
async def start_research(
    query: str = Form(...),
    darkweb: bool = Form(False),
    max_sources: int = Form(10),
    max_sub_queries: int = Form(3),
    model: str = Form("dolphin3:8b"),
    mode: str = Form("research"),
):
    if not query.strip():
        return JSONResponse({"error": "Query cannot be empty"}, status_code=400)

    job_id = manager.create(
        query=query.strip(),
        darkweb=darkweb,
        max_sources=max_sources,
        max_sub_queries=max_sub_queries,
        model=model,
        mode=mode,
    )
    manager.run(job_id)
    return JSONResponse({"job_id": job_id, "query": query.strip(), "mode": mode})


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
    """Server-Sent Events stream of live research progress."""
    job = manager.get(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    q = await bus.subscribe(job_id)
    status = status_value = "running"

    async def event_generator():
        try:
            # If job already finished, send the final state right away
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
    """HTMX poll target for the finished result JSON."""
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
    """Delete a job from history (and its output folder)."""
    deleted = manager.delete(job_id)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_id}/images")
def get_images(job_id: str):
    """Return image results for an image-search job."""
    job = manager.get(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"status": job.status, "images": job.images})


@app.get("/api/models")
def list_models():
    """List models currently available in Ollama."""
    try:
        import httpx

        from research.config import load_config

        cfg = load_config()
        r = httpx.get(f"{cfg.ollama.url}/api/tags", timeout=5)
        models = r.json().get("models", [])
        names = [m.get("name", "") for m in models]
        return {"models": names, "current": cfg.ollama.model}
    except Exception as e:  # noqa: BLE001
        return {"models": [], "current": "dolphin3:8b", "error": str(e)}


# ----------------------------------------------------------------------
# Performer directory (face similarity + browse + crawl)
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
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/performers/browse")
def api_performer_browse(
    q: str = Query("", description="Name substring"),
    gender: str = Query(None),
    sort: str = Query("views", description="views|videos|name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        return performer_browse(
            query=q, gender=gender or None, sort_by=sort, limit=limit, offset=offset
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/performers/face")
async def api_performer_face(file: UploadFile = File(...), top_k: int = Form(8)):
    import tempfile

    suffix = Path(file.filename or "").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = Path(tmp.name)
    try:
        return performer_face_search(path, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


@app.post("/api/performers/crawl")
async def api_performer_crawl(
    max_performers: int = Form(100, ge=1, le=5000),
    pages: int = Form(6, ge=1, le=100),
    gender: str = Form("female"),
):
    try:
        return performer_crawl(max_performers=max_performers, pages=pages, gender=gender)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/performers/photo/{photo}")
def performer_photo(photo: str):
    db = performer_db_for_photo()
    p = db.photo_path(photo)
    if p is None or not p.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(p)


def performer_db_for_photo():
    from webapp.performers_store import get_db

    return get_db()
