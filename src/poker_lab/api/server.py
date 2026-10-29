"""Local web application server (P9 stage B).

Security model (local app, single user):
- binds ONLY to 127.0.0.1 (``launch.py`` refuses anything else);
- every /api/* request needs the per-launch random token (header ``X-Lab-Token``), compared in
  constant time; the token is generated at start, kept in memory, never written to disk/logs;
- ``Host`` must be 127.0.0.1:<port> or localhost:<port> (blocks DNS rebinding); a present
  ``Origin`` must be the same origin (blocks cross-site requests); no CORS is enabled;
- request body size and request rate are limited; strict security headers (CSP 'self' only);
- stage B exposes read-only views, settings without secrets and read-only verification jobs.
  Simulation (stage C) and online sessions (stage E) are NOT available and say so.
"""

from __future__ import annotations

import hmac
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from poker_lab.lab import config as cfg
from poker_lab.lab.frozen import verify_manifest
from poker_lab.lab.health import check_all
from poker_lab.lab.integrity import verify_run
from poker_lab.lab.jobs import JobBusy, JobManager
from poker_lab.lab.registry import (
    KNOWN_RUNS,
    discover_databases,
    get_run,
    load_report,
    project_root,
    run_overview,
)
from poker_lab.lab.summary import compare_table, run_summary, scenario_table

STATIC = Path(__file__).parent / "static"
MAX_BODY = 32 * 1024
APP_VERSION = "p9-b"

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.hits: deque[float] = deque()
        self.lock = threading.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self.lock:
            while self.hits and now - self.hits[0] > 60:
                self.hits.popleft()
            if len(self.hits) >= self.per_minute:
                return False
            self.hits.append(now)
            return True


def _err(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status, headers=SECURITY_HEADERS)


def create_app(token: str, port: int, root: Path | None = None, rate_per_minute: int = 600) -> FastAPI:
    if len(token) < 32:
        raise ValueError("token too short")
    root = root or project_root()
    app = FastAPI(title="Poker AI Tournament Lab", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://{h}" for h in allowed_hosts}
    limiter = RateLimiter(rate_per_minute)
    jobs = JobManager()
    state: dict[str, Any] = {"agent_state": "desconectado", "started_at": time.time()}

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        if request.headers.get("host", "") not in allowed_hosts:
            return _err(421, "host não permitido")
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return _err(403, "origem não permitida")
        if int(request.headers.get("content-length") or 0) > MAX_BODY:
            return _err(413, "requisição grande demais")
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("x-lab-token", "")
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return _err(401, "token ausente ou inválido")
            if not limiter.allow():
                return _err(429, "muitas requisições; aguarde")
            if request.method not in ("GET", "POST", "PUT"):
                return _err(405, "método não permitido")
        response: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    # ------------------------------------------------------------------ pages
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", media_type="text/html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    # ------------------------------------------------------------------ api
    @app.get("/api/status")
    def status() -> dict[str, Any]:
        active = jobs.active()
        return {
            "app_version": APP_VERSION,
            "agent_state": state["agent_state"],
            "online": {"enabled": False, "status": "desativada", "stage": "E"},
            "simulation": {"available": False, "stage": "C"},
            "active_job": active.view() if active else None,
            "uptime_s": round(time.time() - state["started_at"]),
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return check_all(root)

    @app.get("/api/runs")
    def runs() -> dict[str, Any]:
        return {"known": [run_overview(r, root) for r in KNOWN_RUNS], "databases": discover_databases(root)}

    def _report(key: str) -> dict[str, Any]:
        try:
            run = get_run(key)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if not run.report_path(root).is_file():
            raise HTTPException(404, "relatório congelado ausente")
        return load_report(run, root)

    @app.get("/api/runs/{key}")
    def run_detail(key: str) -> dict[str, Any]:
        rep = _report(key)
        return {"key": get_run(key).key, **run_summary(rep)}

    @app.get("/api/runs/{key}/scenario/{scenario}")
    def run_scenario(key: str, scenario: str) -> dict[str, Any]:
        rep = _report(key)
        if scenario not in rep["scenarios"]:
            raise HTTPException(404, "cenário inexistente nesta execução")
        return {"scenario": scenario, "table": scenario_table(rep, scenario), "compare": compare_table(rep, scenario)}

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        return cfg.load_settings(root).model_dump()

    @app.put("/api/config")
    async def put_config(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, "JSON inválido") from exc
        if not isinstance(body, dict):
            raise HTTPException(400, "esperado um objeto JSON")
        try:
            return cfg.save_settings(root, body).model_dump()
        except ValueError as exc:
            raise HTTPException(422, str(exc).splitlines()[0][:300]) from exc

    @app.post("/api/verify/frozen")
    def verify_frozen() -> dict[str, Any]:
        return verify_manifest(root).as_dict()

    @app.post("/api/verify/run/{key}")
    def verify_run_job(key: str) -> dict[str, Any]:
        run = get_run(key) if key in {r.key for r in KNOWN_RUNS} else None
        if run is None:
            raise HTTPException(404, "execução desconhecida")
        if not run.db_path(root).is_file():
            raise HTTPException(409, "banco desta execução não está presente nesta máquina")
        rep = load_report(run, root)
        try:
            job = jobs.submit("verify", {"run": run.key}, lambda say: verify_run(run.db_path(root), rep, progress=say))
        except JobBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        return job.view()

    @app.get("/api/jobs")
    def list_jobs() -> list[dict[str, Any]]:
        return jobs.list()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "tarefa inexistente")
        return job.view()

    @app.post("/api/simulation/start")
    def sim_start() -> JSONResponse:
        return _err(501, "simulação local disponível na etapa C")

    @app.post("/api/online/start")
    def online_start() -> JSONResponse:
        return _err(403, "integração online desativada (etapa E, após aprovação e testes)")

    app.state.jobs = jobs
    return app
