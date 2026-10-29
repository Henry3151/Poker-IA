"""Autonomous local simulation sessions (P9-C): end-to-end with the real champion policy."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from poker_lab.lab.assessment import Assessment
from poker_lab.lab.control import State, TransitionRefused
from poker_lab.lab.quality import ERROR
from poker_lab.lab.session import SimConfig, SimulationSession, policy_fingerprint
from poker_lab.lab.store import SessionStore

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def store(tmp_path):
    s = SessionStore(tmp_path / "sessions.db")
    yield s
    s.close()


def wait_for(cond, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_session_runs_autonomously_to_the_hand_limit(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=30, seed=11))
    s.start()
    s.join(60)
    st = s.status()
    assert st["control"]["state"] == "encerrado" and st["summary"]["hands_played"] == 30
    assert st["summary"]["decisions"] > 0 and st["policy_sha256"] == policy_fingerprint(ROOT, s.spec)
    row = store.query("SELECT * FROM sessions WHERE session_id=?", (s.session_id,))[0]
    assert row["hands_played"] == 30 and row["ended_at"] and json.loads(row["summary_json"])["hands_played"] == 30
    assert store.query("SELECT COUNT(*) c FROM hands WHERE session_id=?", (s.session_id,))[0]["c"] == 30
    events = [e["command"] for e in store.query("SELECT command FROM events WHERE session_id=? ORDER BY id", (s.session_id,))]
    assert events[0] == "start" and events[-1] == "complete"


def test_same_seed_reproduces_the_session(tmp_path):
    nets = []
    for i in range(2):
        st = SessionStore(tmp_path / f"s{i}.db")
        s = SimulationSession(ROOT, st, SimConfig(hands=20, seed=5))
        s.start()
        s.join(60)
        nets.append([r["net_bb"] for r in st.query("SELECT net_bb FROM hands ORDER BY hand_no")])
        st.close()
    assert nets[0] == nets[1]


def test_pause_stops_play_and_resume_continues(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=400, seed=2))
    s.start()
    assert wait_for(lambda: s.hands_played >= 3)
    s.pause()
    assert s.ctrl.wait_paused(5)
    committed, hands = s.ctrl.committed, s.hands_played
    time.sleep(0.3)
    assert s.ctrl.committed == committed and s.hands_played == hands  # no new action after the confirmed pause
    assert s.resume() is State.RUNNING
    assert wait_for(lambda: s.ctrl.committed > committed)
    s.finish("now")
    s.join(10)
    assert not s.running


def test_emergency_stops_quickly_and_nothing_is_committed_after(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=5000, seed=9))
    s.start()
    assert wait_for(lambda: s.hands_played >= 2)
    t0 = time.perf_counter()
    with s.ctrl._cond:  # noqa: SLF001 - snapshot taken atomically with the command
        s.emergency()
        allowed = s.ctrl.committed + (1 if s.ctrl.in_flight else 0)  # an action already being applied may finish
    s.join(5)
    assert not s.running and time.perf_counter() - t0 < 2.0
    assert s.ctrl.committed <= allowed  # no NEW action after the emergency is confirmed
    assert s.ctrl.history[-2].to_state == "emergencia" and s.ctrl.state is State.FINISHED
    assert s.hands_played < 5000


def test_finish_after_hand_ends_on_a_hand_boundary(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=5000, seed=4))
    s.start()
    assert wait_for(lambda: s.hands_played >= 2)
    s.finish("after_hand")
    s.join(10)
    assert s.ctrl.state is State.FINISHED and s.hands_aborted == 0
    assert store.query("SELECT COUNT(*) c FROM hands WHERE session_id=? AND net_bb IS NULL", (s.session_id,))[0]["c"] == 0


class AlwaysError:
    name = "stub"

    def assess(self, obs, chosen):  # noqa: ANN001
        return Assessment(ERROR, "stub", "referência de teste", ev_gap_bb=-1.0)


def test_quality_stop_blocks_until_human_confirmation(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=5000, seed=7))
    s.reference = AlwaysError()  # type: ignore[assignment]
    s.start()
    assert wait_for(lambda: s.ctrl.state is State.QUALITY_STOP)
    assert s.quality.state().evaluable >= 50 and "erro" in (s.ctrl.stop_reason or "")
    committed = s.ctrl.committed
    time.sleep(0.3)
    assert s.ctrl.committed == committed
    with pytest.raises(TransitionRefused):
        s.resume()
    with pytest.raises(TransitionRefused):
        s.acknowledge_quality(False, "")
    assert s.acknowledge_quality(True, "revisei as decisões") is State.RUNNING
    s.emergency()
    s.join(5)
    kinds = [e["command"] for e in store.query("SELECT command FROM events WHERE session_id=?", (s.session_id,))]
    assert "quality_stop" in kinds and "ack_resume" in kinds


def test_decisions_store_decision_time_data_and_revealed_cards_apart(store):
    s = SimulationSession(ROOT, store, SimConfig(hands=25, seed=13))
    s.start()
    s.join(60)
    decs = store.query("SELECT * FROM decisions WHERE session_id=?", (s.session_id,))
    assert decs and all(d["label"] in ("adequada", "provavel_erro_estrategico", "erro_tecnico", "inconclusiva") for d in decs)
    for d in decs:
        obs = json.loads(d["observation_json"])
        assert set(obs) >= {"hole_cards", "board", "legal", "history"}
        a = json.loads(d["assessment_json"])
        assert "reason" in a and "limitations" in a
    hands = {h["hand_id"]: h for h in store.query("SELECT * FROM hands WHERE session_id=?", (s.session_id,))}
    rev = store.query("SELECT * FROM revealed")
    assert rev and all(r["hand_id"] in hands and r["revealed_after_hand"] == 1 for r in rev)
    # revealed opponent cards never appear in the hero's decision-time observation
    for r in rev:
        if r["profile"] == "hero":
            continue
        for d in (x for x in decs if x["hand_id"] == r["hand_id"]):
            assert json.loads(d["observation_json"])["hole_cards"] != json.loads(r["cards_json"])


def test_config_is_validated():
    with pytest.raises(ValueError):
        SimConfig(opponents=["inexistente"])
    with pytest.raises(ValueError):
        SimConfig(hands=0)
    with pytest.raises(ValueError):
        SimConfig(extra_field=1)  # type: ignore[call-arg]
