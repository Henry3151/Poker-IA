"""P9-E: the local app only *shows* the online integration; it never starts it or reads the key."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from poker_lab.api.server import create_app
from poker_lab.integrations.openpoker.recorder import OnlineRecorder
from poker_lab.lab.online import list_online_sessions, online_status

TOKEN = "o" * 43
PORT = 8767
AUTH = {"Host": f"127.0.0.1:{PORT}", "X-Lab-Token": TOKEN}
SECRET = "opk_live_THIS_MUST_NEVER_APPEAR_123456"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_POKER_ENABLED", "1")
    monkeypatch.setenv("OPEN_POKER_API_KEY", SECRET)
    app = create_app(TOKEN, PORT, root=tmp_path, sessions_db=tmp_path / "s.db")
    yield TestClient(app, base_url=f"http://127.0.0.1:{PORT}")
    app.state.sessions.close()


def test_app_never_enables_or_starts_online_even_with_env_set(client):
    s = client.get("/api/status", headers=AUTH)
    assert s.json()["online"]["enabled"] is False and SECRET not in s.text
    r = client.post("/api/online/start", headers=AUTH)
    assert r.status_code == 403 and "manualmente" in r.json()["error"] and SECRET not in r.text
    o = client.get("/api/online/sessions", headers=AUTH)
    assert o.status_code == 200 and o.json()["sessions"] == [] and SECRET not in o.text


def test_status_reports_kill_switch_and_never_the_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPEN_POKER_API_KEY", SECRET)
    assert online_status(tmp_path)["kill_switch_set"] is False
    (tmp_path / "artifacts/openpoker").mkdir(parents=True)
    (tmp_path / "artifacts/openpoker/STOP").write_text("stop")
    st = online_status(tmp_path)
    assert st["kill_switch_set"] is True and st["enabled"] is False and SECRET not in repr(st)


def test_online_sessions_are_listed_read_only(tmp_path):
    db = tmp_path / "artifacts/openpoker/online.db"
    db.parent.mkdir(parents=True)
    rec = OnlineRecorder(db, "cash6max-v0", {"seed": 1})
    sid = rec.session_id
    rec.close() if hasattr(rec, "close") else None
    before = db.read_bytes()
    rows = list_online_sessions(tmp_path)
    assert rows and rows[0]["session_id"] == sid and rows[0]["money"] == "virtual_chips"
    assert db.read_bytes() == before


def test_cli_online_status_never_connects(monkeypatch):
    from poker_lab.cli import app

    monkeypatch.setenv("OPEN_POKER_API_KEY", SECRET)
    r = CliRunner().invoke(app, ["online", "status"])
    assert r.exit_code == 0 and "fichas virtuais" in r.output and SECRET not in r.output
