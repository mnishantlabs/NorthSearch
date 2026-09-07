"""Background research job manager for the web UI."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from research.pipeline import ResearchPipeline
from webapp.progress import bus

logger = logging.getLogger(__name__)

# Jobs are persisted here so history survives server restarts.
HISTORY_DIR = Path(__file__).parent.parent / "output" / "_web_history"
HISTORY_FILE = HISTORY_DIR / "jobs.json"


@dataclass
class Job:
    """A single research job."""

    id: str
    query: str
    darkweb: bool
    max_sources: int
    max_sub_queries: int
    model: str
    mode: str = "research"  # research | images
    search_mode: str = "normal"  # normal | adult
    darkweb_mode: str = "normal"  # normal | darknet_only | all
    engines: list[str] = field(default_factory=list)
    deep: bool = False
    status: str = "queued"  # queued | running | done | error
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    images: list[dict[str, Any]] = field(default_factory=list)
    thread: threading.Thread | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "darkweb": self.darkweb,
            "max_sources": self.max_sources,
            "max_sub_queries": self.max_sub_queries,
            "model": self.model,
            "mode": self.mode,
            "search_mode": self.search_mode,
            "darkweb_mode": self.darkweb_mode,
            "engines": self.engines,
            "deep": self.deep,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "images": self.images,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], thread: threading.Thread | None = None) -> "Job":
        return cls(
            id=d["id"],
            query=d["query"],
            darkweb=d.get("darkweb", False),
            max_sources=d.get("max_sources", 10),
            max_sub_queries=d.get("max_sub_queries", 3),
            model=d.get("model", "dolphin3:8b"),
            mode=d.get("mode", "research"),
            search_mode=d.get("search_mode", "normal"),
            darkweb_mode=d.get("darkweb_mode", "normal"),
            engines=d.get("engines", []),
            deep=d.get("deep", False),
            status=d.get("status", "done"),
            error=d.get("error"),
            created_at=d.get("created_at", time.time()),
            finished_at=d.get("finished_at"),
            result=d.get("result"),
            images=d.get("images", []),
            thread=thread,
        )


class JobManager:
    """Owns the set of active jobs and executes them on background threads.

    Completed jobs are persisted to ``output/_web_history/jobs.json`` so
    the history page survives restarts. Running/queued jobs are not
    persisted (they die with the process).
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._load_history()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def create(
        self,
        query: str,
        darkweb: bool = False,
        darkweb_mode: str = "normal",
        engines: list[str] | None = None,
        max_sources: int = 10,
        max_sub_queries: int = 3,
        model: str = "dolphin3:8b",
        mode: str = "research",
        search_mode: str = "normal",
        deep: bool = False,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = Job(
            id=job_id,
            query=query,
            darkweb=darkweb or (darkweb_mode in ("darknet_only", "all", "hybrid")),
            darkweb_mode=darkweb_mode,
            engines=engines or [],
            max_sources=max_sources,
            max_sub_queries=max_sub_queries,
            model=model,
            mode=mode,
            search_mode=search_mode,
            deep=deep,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        """Remove a job from memory; also tries to remove its output folder."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        # Best-effort cleanup of the output folder for this topic.
        slug = self._slugify(job.query)
        topic_dir = Path(__file__).parent.parent / "output" / slug
        try:
            if topic_dir.exists():
                import shutil

                shutil.rmtree(topic_dir, ignore_errors=True)
        except Exception:
            logger.debug("Failed to remove output dir for %s", job_id, exc_info=True)
        self._persist()
        return True

    def run(self, job_id: str) -> None:
        """Start a job's research in a background thread."""
        job = self.get(job_id)
        if job is None:
            return
        job.status = "running"
        job.thread = threading.Thread(
            target=self._worker,
            args=(job,),
            daemon=True,
            name=f"research-{job_id}",
        )
        job.thread.start()

    def _worker(self, job: Job) -> None:
        """Execute the pipeline and broadcast events."""
        from research.config import load_config

        is_darknet = job.darkweb or (job.darkweb_mode in ("darknet_only", "all", "hybrid"))
        cfg = load_config(
            darkweb_enabled=is_darknet,
            max_sources=job.max_sources,
        )
        if job.engines:
            cfg.search.engines = [e for e in job.engines if e.lower() != "tor"]
        cfg.search.darkweb_mode = job.darkweb_mode
        cfg.search.max_sub_queries = job.max_sub_queries
        cfg.search.mode = job.search_mode
        cfg.search.deep = job.deep
        cfg.ollama.model = job.model

        pipeline = ResearchPipeline(cfg)

        def on_event(event: dict) -> None:
            bus.publish(job.id, dict(event))

        pipeline.on_event = on_event

        try:
            if job.mode == "images":
                images = pipeline.run_images(job.query)
                job.status = "done"
                job.finished_at = time.time()
                job.images = [img.model_dump(mode="json") for img in images]
                bus.publish(job.id, {"type": "done", "status": "done"})
                self._persist()
                return

            report = pipeline.run(job.query)
            job.status = "done"
            job.finished_at = time.time()
            job.result = {
                "query": report.query,
                "summary": report.summary,
                "sections": [
                    {"title": s.title, "content": s.content, "citations": s.citations}
                    for s in report.sections
                ],
                "findings": [
                    {
                        "topic": f.topic,
                        "content": f.content,
                        "source_url": f.source_url,
                        "source_title": f.source_title,
                        "source_type": f.source_type.value,
                        "confidence": f.confidence,
                        "contradictions": f.contradictions,
                    }
                    for f in report.findings
                ],
                "sources": [
                    {
                        "url": s.url,
                        "title": s.title,
                        "text": (s.text[:2000] + "…" if len(s.text or "") > 2000 else s.text),
                        "source_type": s.source_type.value,
                        "quality_score": s.quality_score,
                        "error": s.error,
                    }
                    for s in report.sources
                ],
                "contradictions": report.contradictions,
                "model_used": report.model_used,
                "total_sources": report.total_sources,
                "darkweb_sources": report.darkweb_sources,
                "generated_at": report.generated_at.isoformat(),
            }
            bus.publish(job.id, {"type": "done", "status": "done"})
            self._persist()
        except Exception as e:  # noqa: BLE001
            logger.exception("Research job %s failed", job.id)
            job.status = "error"
            job.error = str(e)
            job.finished_at = time.time()
            bus.publish(job.id, {"type": "error", "error": str(e)})
            self._persist()
        finally:
            try:
                pipeline.close()
            except Exception:
                logger.debug("Error closing pipeline", exc_info=True)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Save finished jobs to disk."""
        from research.config import load_config

        try:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            with self._lock:
                finished = [
                    j.to_dict()
                    for j in self._jobs.values()
                    if j.status in ("done", "error")
                ]
            tmp = HISTORY_FILE.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(finished, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            tmp.replace(HISTORY_FILE)
        except Exception:
            logger.debug("Failed to persist history", exc_info=True)

    def _load_history(self) -> None:
        """Load finished jobs from disk on startup."""
        try:
            if not HISTORY_FILE.exists():
                return
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            with self._lock:
                for item in data:
                    job = Job.from_dict(item)
                    self._jobs[job.id] = job
            logger.info("Loaded %d jobs from history", len(data))
        except Exception:
            logger.debug("Failed to load history", exc_info=True)

    @staticmethod
    def _slugify(text: str) -> str:
        import re

        safe = re.sub(r"[^\w\s-]", "", text.lower())
        safe = re.sub(r"\s+", "_", safe.strip())
        return safe[:60] or "research"


manager = JobManager()