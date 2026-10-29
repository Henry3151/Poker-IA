"""Minimal background job runner for long read-only tasks (stage B: integrity verification).

One job at a time (``concurrent_jobs`` = 1). Jobs record progress messages and a result; they
never touch frozen artifacts (the only job kinds in stage B are read-only verifications).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class JobBusy(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    kind: str
    params: dict[str, Any]
    status: str = "queued"  # queued | running | done | failed
    started_at: float = 0.0
    finished_at: float = 0.0
    progress: list[str] = field(default_factory=list)
    result: Any = None
    error: str | None = None

    def view(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "params": self.params, "status": self.status,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "progress": self.progress[-20:], "result": self.result, "error": self.error}


class JobManager:
    def __init__(self, max_history: int = 20) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._max = max_history

    def active(self) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j.status in ("queued", "running")), None)

    def submit(self, kind: str, params: dict[str, Any], fn: Callable[[Callable[[str], None]], Any]) -> Job:
        with self._lock:
            if any(j.status in ("queued", "running") for j in self._jobs.values()):
                raise JobBusy("já existe uma tarefa em andamento")
            job = Job(uuid.uuid4().hex[:12], kind, params)
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self._max:
                self._jobs.pop(self._order.pop(0), None)

        def say(msg: str) -> None:
            job.progress.append(f"{time.strftime('%H:%M:%S')} {msg}")

        def run() -> None:
            job.status, job.started_at = "running", time.time()
            try:
                job.result = fn(say)
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 - reported to the UI, never crashes the server
                job.status, job.error = "failed", f"{type(exc).__name__}: {exc}"
            finally:
                job.finished_at = time.time()

        threading.Thread(target=run, name=f"job-{job.id}", daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._jobs[i].view() for i in reversed(self._order) if i in self._jobs]
