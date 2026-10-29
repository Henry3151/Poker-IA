"""P9-C API: local simulation sessions (start needs confirmation, controls, history, hand viewer)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poker_lab.api.server import create_app

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "s" * 43
PORT = 8766
AUTH = {"Host": f"127.0.0.1:{PORT}", "X-Lab-Token": TOKEN}


@pytest.fixture()
def client(tmp_path):
    app = create_app(TOKEN, PORT, root=ROOT, sessions_db=tmp_path / "sessions.db")
    c = TestClient(app, base_url=f"http://127.0.0.1:{PORT}")
    yield c
    app.state.sessions.close()


def wait(c, pred, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = c.get("/api/simulation/current", headers=AUTH).json()["session"]
        if s and pred(s):
            return s
        time.sleep(0.05)
    raise AssertionError("timeout")


def test_start_requires_confirmation_and_valid_config(client):
    assert client.post("/api/simulation/start", headers=AUTH, json={"hands": 5}).status_code == 400
    assert client.post("/api/simulation/start", headers=AUTH, json={"confirm": True, "hands": 0}).status_code == 422
    assert client.post("/api/simulation/start", headers=AUTH, json={"confirm": True, "opponents": ["x"]}).status_code == 422
    assert client.post("/api/simulation/start", json={"confirm": True}).status_code == 401  # no token


def test_full_session_cycle_and_history(client):
    r = client.post("/api/simulation/start", headers=AUTH, json={"confirm": True, "hands": 3000, "seed": 21})
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert client.post("/api/simulation/start", headers=AUTH, json={"confirm": True}).status_code == 409  # one at a time
    wait(client, lambda s: s["summary"]["hands_played"] >= 3)
    assert client.get("/api/status", headers=AUTH).json()["agent_state"] == "autonomo"
    p = client.post("/api/simulation/pause", headers=AUTH)
    assert p.json()["state"] == "supervisionado" and p.json()["session"]["control"]["pause_confirmed"]
    assert client.post("/api/simulation/ack-quality", headers=AUTH, json={"confirm": True, "note": "x"}).status_code == 409
    assert client.post("/api/simulation/resume", headers=AUTH).json()["state"] == "autonomo"
    assert client.post("/api/simulation/finish", headers=AUTH, json={"mode": "after_hand"}).status_code == 200
    wait(client, lambda s: not s["running"])
    sessions = client.get("/api/sessions", headers=AUTH).json()["sessions"]
    assert sessions[0]["session_id"] == sid and sessions[0]["state"] == "encerrado"
    detail = client.get(f"/api/sessions/{sid}", headers=AUTH).json()
    assert [e["command"] for e in detail["events"]][:2] == ["start", "pause"]
    hands = client.get(f"/api/sessions/{sid}/hands", headers=AUTH).json()["hands"]
    assert hands and hands[0]["hand_no"] == 1
    with_dec = next(h for h in hands if h["n_decisions"])
    hd = client.get(f"/api/hands/{with_dec['hand_id']}", headers=AUTH).json()
    assert hd["decision_time"] and "revealed_after_hand" in hd
    assert client.get("/api/hands/inexistente", headers=AUTH).status_code == 404


def test_emergency_via_api(client):
    client.post("/api/simulation/start", headers=AUTH, json={"confirm": True, "hands": 5000, "seed": 3})
    wait(client, lambda s: s["summary"]["hands_played"] >= 1)
    r = client.post("/api/simulation/emergency", headers=AUTH)
    assert r.status_code == 200 and r.json()["state"] in ("emergencia", "encerrado")
    s = wait(client, lambda s: not s["running"], 5)
    assert s["control"]["state"] == "encerrado"
    assert any(h["to_state"] == "emergencia" for h in s["history"])
    assert client.post("/api/simulation/unknown", headers=AUTH).status_code == 404
