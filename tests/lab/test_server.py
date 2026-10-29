"""P9-B local server: token, Host/Origin checks, limits, headers, disabled stages, no secrets."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poker_lab.api import launch
from poker_lab.api.server import STATIC, create_app

TOKEN = "t" * 43
PORT = 8765
HOST = {"Host": f"127.0.0.1:{PORT}"}
AUTH = {**HOST, "X-Lab-Token": TOKEN}


@pytest.fixture()
def client(lab_root):
    app = create_app(TOKEN, PORT, root=lab_root)
    return TestClient(app, base_url=f"http://127.0.0.1:{PORT}")


def test_page_is_served_without_data_and_api_requires_token(client):
    r = client.get("/", headers=HOST)
    assert r.status_code == 200 and "Poker AI Tournament Lab" in r.text
    assert client.get("/api/status", headers=HOST).status_code == 401
    assert client.get("/api/status", headers={**HOST, "X-Lab-Token": "x" * 43}).status_code == 401
    s = client.get("/api/status", headers=AUTH).json()
    assert s["agent_state"] == "desconectado" and s["online"]["enabled"] is False


@pytest.mark.parametrize("host", ["evil.example:8765", "127.0.0.1:9999", "192.168.0.10:8765", "localhost.evil.com"])
def test_host_header_is_checked_against_dns_rebinding(client, host):
    assert client.get("/api/status", headers={"Host": host, "X-Lab-Token": TOKEN}).status_code == 421
    assert client.get("/", headers={"Host": host}).status_code == 421


def test_cross_origin_requests_are_refused(client):
    assert client.get("/api/status", headers={**AUTH, "Origin": "http://evil.example"}).status_code == 403
    assert client.put("/api/config", headers={**AUTH, "Origin": "null"}, json={}).status_code == 403
    assert client.get("/api/status", headers={**AUTH, "Origin": f"http://127.0.0.1:{PORT}"}).status_code == 200
    assert "access-control-allow-origin" not in client.get("/api/status", headers=AUTH).headers


def test_security_headers_and_methods(client):
    r = client.get("/api/status", headers=AUTH)
    assert "default-src 'self'" in r.headers["content-security-policy"] and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert client.delete("/api/config", headers=AUTH).status_code == 405


def test_body_size_limit(client):
    r = client.put("/api/config", headers={**AUTH, "Content-Type": "application/json"}, content=b"{" + b" " * 40000 + b"}")
    assert r.status_code == 413


def test_rate_limit(lab_root):
    c = TestClient(create_app(TOKEN, PORT, root=lab_root, rate_per_minute=3), base_url=f"http://127.0.0.1:{PORT}")
    codes = [c.get("/api/status", headers=AUTH).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]


def test_online_is_not_available(client):
    r = client.post("/api/online/start", headers=AUTH)
    assert r.status_code == 403 and "desativada" in r.json()["error"]


def test_config_validation_and_secret_rejection(client, lab_root):
    cfg = client.get("/api/config", headers=AUTH).json()
    cfg["simulation"]["max_tournaments_per_job"] = 77
    assert client.put("/api/config", headers=AUTH, json=cfg).json()["simulation"]["max_tournaments_per_job"] == 77
    cfg["online"]["api_key"] = "opk_live_SECRET"
    r = client.put("/api/config", headers=AUTH, json=cfg)
    assert r.status_code == 422
    assert "SECRET" not in (lab_root / "artifacts/lab/config.json").read_text()
    assert client.put("/api/config", headers=AUTH, json=[1, 2]).status_code == 400


def test_runs_health_and_verification_job(client, lab_root):
    db = lab_root / "artifacts/p7c/final.db"
    before = db.read_bytes()
    runs = client.get("/api/runs", headers=AUTH).json()
    p7c = next(r for r in runs["known"] if r["key"] == "P7c")
    assert p7c["db_present"] and p7c["tournaments"] == p7c["expected_tournaments"] == 10
    assert not next(r for r in runs["known"] if r["key"] == "P7")["db_present"]
    d = client.get("/api/runs/P7c", headers=AUTH).json()
    assert d["baseline"] == "heuristic" and d["primary_scenario"] == "base"
    assert client.get("/api/runs/P7c/scenario/nope", headers=AUTH).status_code == 404
    assert client.get("/api/runs/XYZ", headers=AUTH).status_code == 404
    h = client.get("/api/health", headers=AUTH).json()
    assert h["frozen"]["passed"] and h["online"]["enabled"] is False
    job = client.post("/api/verify/run/P7c", headers=AUTH).json()
    for _ in range(300):
        job = client.get(f"/api/jobs/{job['id']}", headers=AUTH).json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.02)
    assert job["status"] == "done" and job["result"]["ok"]
    assert client.post("/api/verify/run/P7", headers=AUTH).status_code == 409  # db absent
    assert db.read_bytes() == before


def test_launcher_binds_only_loopback_and_keeps_token_out_of_requests(monkeypatch):
    calls = {}

    def fake_run(app, **kw):
        calls.update(kw)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr(launch.webbrowser, "open", lambda url: calls.setdefault("url", url))
    assert launch.main(["--port", "8770"]) == 0
    assert calls["host"] == "127.0.0.1" and calls["access_log"] is False
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+/#t=[A-Za-z0-9_-]{43}", calls["url"])  # token only in the fragment
    with pytest.raises(ValueError):
        create_app("short", 8770)


def test_static_ui_has_no_external_resources_or_html_injection():
    for f in ("index.html", "app.js", "app.css"):
        text = (Path(STATIC) / f).read_text(encoding="utf-8")
        assert not re.search(r"""(src|href)=["']https?://""", text), f
        assert "innerHTML" not in text and "eval(" not in text, f
    assert "<script>" not in (Path(STATIC) / "index.html").read_text() and " style=" not in (Path(STATIC) / "index.html").read_text()
