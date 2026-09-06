"""In-memory event bus for broadcasting research progress to browsers via SSE."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any


class ProgressBus:
    """Fan-out broadcast hub for one job's progress events.

    The research pipeline runs in a background thread and pushes events via
    :meth:`publish`. Each connected SSE client holds its own asyncio.Queue
    and streams events out.
    """

    def __init__(self) -> None:
        # job_id -> list of asyncio queues (one per connected client)
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = threading.Lock()

    def _queues(self, job_id: str) -> list[asyncio.Queue]:
        return self._subscribers.setdefault(job_id, [])

    def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers of a job. Thread-safe.

        Runs in the research worker thread (not the event loop), so it uses
        loop.call_soon_threadsafe to enqueue on each subscriber's loop.
        """
        payload = json.dumps(event, ensure_ascii=False, default=str)
        with self._lock:
            queues = list(self._subscribers.get(job_id, []))

        for q in queues:
            loop = q._loop
            if loop is None:
                continue
            try:
                loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                pass

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        """Register a new subscriber and return its queue."""
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._queues(job_id).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            queues = self._subscribers.get(job_id, [])
            if q in queues:
                queues.remove(q)
            if not queues:
                self._subscribers.pop(job_id, None)


bus = ProgressBus()
