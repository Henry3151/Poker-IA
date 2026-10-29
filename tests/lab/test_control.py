"""Session control: autonomy, pause/resume, emergency, finish, discards, races (P9-C)."""

from __future__ import annotations

import random
import threading
import time

import pytest

from poker_lab.agents.base import Agent
from poker_lab.domain.actions import Action, ActionKind, LegalActions
from poker_lab.lab.control import SessionAbort, SessionController, State, TransitionRefused
from poker_lab.lab.controlled_agent import ControlledAgent

OK = lambda: (True, "estado consistente")  # noqa: E731


class GatedAgent(Agent):
    """Inner policy whose computation blocks until released (to place controls mid-computation)."""

    algorithm = "gated"

    def __init__(self) -> None:
        super().__init__("hero", "t", 0)
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def act(self, obs):  # noqa: ANN001
        self.calls += 1
        self.started.set()
        self.release.wait(5)
        return Action.call() if obs.legal.can_call else Action.check()


class FastAgent(Agent):
    algorithm = "fast"

    def act(self, obs):  # noqa: ANN001
        return Action.call() if obs.legal.can_call else Action.check()


class Obs:
    legal = LegalActions(True, False, 20, ActionKind.RAISE, 40, 1000)


def run_decision(agent, out):
    try:
        out["action"] = agent.act(Obs())
    except SessionAbort as exc:
        out["abort"] = str(exc)


def start_thread(agent):
    out: dict = {}
    t = threading.Thread(target=run_decision, args=(agent, out), daemon=True)
    t.start()
    return t, out


def test_autonomous_decision_commits_without_approval():
    c = SessionController()
    c.start()
    a = ControlledAgent(FastAgent("h"), c)
    assert a.act(Obs()).kind is ActionKind.CALL and c.in_flight
    c.end_commit()
    assert c.committed == 1 and c.state is State.RUNNING


def test_pause_before_decision_blocks_and_nothing_is_committed():
    c = SessionController()
    c.start()
    c.pause()
    assert c.state is State.PAUSED  # confirmed immediately: nothing in flight
    a = ControlledAgent(FastAgent("h"), c)
    t, out = start_thread(a)
    t.join(0.3)
    assert t.is_alive() and "action" not in out and c.committed == 0
    c.resume(OK)
    t.join(2)
    assert out["action"].kind is ActionKind.CALL


def test_pause_during_computation_discards_the_result():
    c = SessionController()
    c.start()
    inner = GatedAgent()
    a = ControlledAgent(inner, c)
    t, out = start_thread(a)
    assert inner.started.wait(2)
    c.pause()
    assert c.state is State.PAUSED
    inner.release.set()  # the computation finishes AFTER the pause
    t.join(0.5)
    assert t.is_alive() and "action" not in out and c.in_flight is False
    c.resume(OK)
    t.join(3)
    assert out["action"].kind is ActionKind.CALL and inner.calls == 2  # recomputed after resume
    assert c.discarded >= 1 and a.discard_log


def test_pause_between_result_and_commit_is_refused_by_epoch():
    c = SessionController()
    c.start()
    epoch = c.begin_decision()
    c.pause()  # result is ready but not yet committed
    assert c.try_commit(epoch) is False and c.discarded == 1 and c.committed == 0


def test_pause_while_commit_in_flight_waits_for_confirmation():
    c = SessionController()
    c.start()
    epoch = c.begin_decision()
    assert c.try_commit(epoch)
    assert c.pause() is State.PAUSING  # not yet confirmed: an action is being applied
    assert not c.wait_paused(0.1)
    c.end_commit()
    assert c.wait_paused(1) and c.state is State.PAUSED
    assert c.try_commit(c.epoch) is False  # nothing can be committed after confirmation


def test_repeated_clicks_are_idempotent():
    c = SessionController()
    c.start()
    for _ in range(5):
        c.pause()
    assert [t.command for t in c.history].count("pause") == 1
    for _ in range(3):
        c.resume(OK)
    assert c.state is State.RUNNING and [t.command for t in c.history].count("resume") == 1
    c.emergency()
    c.emergency()
    assert [t.command for t in c.history].count("emergency") == 1


def test_resume_requires_successful_sync():
    c = SessionController()
    c.start()
    c.pause()
    assert c.resume(lambda: (False, "estado divergente")) is State.PAUSED
    assert c.resume(OK) is State.RUNNING


def test_emergency_during_computation_aborts_and_discards():
    c = SessionController()
    c.start()
    inner = GatedAgent()
    a = ControlledAgent(inner, c)
    t, out = start_thread(a)
    assert inner.started.wait(2)
    t0 = time.perf_counter()
    c.emergency()
    t.join(2)
    assert out.get("abort") == State.EMERGENCY.value and "action" not in out
    assert time.perf_counter() - t0 < 1.0  # emergency takes effect in under a second
    inner.release.set()
    assert c.committed == 0


def test_result_arriving_after_finish_is_discarded():
    c = SessionController()
    c.start()
    inner = GatedAgent()
    a = ControlledAgent(inner, c)
    t, out = start_thread(a)
    assert inner.started.wait(2)
    c.finish("now")
    inner.release.set()
    t.join(2)
    assert "abort" in out and c.committed == 0 and c.state is State.FINISHED


def test_finish_after_hand_keeps_playing_until_boundary():
    c = SessionController()
    c.start()
    c.finish("after_hand")
    a = ControlledAgent(FastAgent("h"), c)
    assert a.act(Obs()).kind is ActionKind.CALL  # still autonomous during the current hand
    c.end_commit()
    assert c.at_hand_boundary() and c.state is State.FINISHED


def test_quality_stop_requires_explicit_human_confirmation():
    c = SessionController()
    c.start()
    c.quality_stop("qualidade: erro acima do limite")
    assert c.state is State.QUALITY_STOP
    with pytest.raises(TransitionRefused):
        c.resume(OK)
    with pytest.raises(TransitionRefused):
        c.acknowledge_quality_and_resume(False, "ok", OK)
    with pytest.raises(TransitionRefused):
        c.acknowledge_quality_and_resume(True, "   ", OK)
    assert c.acknowledge_quality_and_resume(True, "relatório revisado", OK) is State.RUNNING


def test_decision_timeout_uses_safe_default_and_is_flagged():
    c = SessionController()
    c.start()
    inner = GatedAgent()
    a = ControlledAgent(inner, c, decision_timeout_s=0.1)
    act = a.act(Obs())
    assert act.kind is ActionKind.FOLD and a.last_info.get("issue") == "timeout"
    inner.release.set()


def test_every_transition_is_recorded_with_epoch_and_actor():
    events = []
    c = SessionController(sink=events.append)
    c.start()
    c.pause()
    c.resume(OK)
    c.finish("now")
    assert [e.to_state for e in events] == ["autonomo", "pausando", "supervisionado", "sincronizando", "autonomo", "encerrado"]
    assert all(e.actor and e.at for e in events) and events[1].epoch == 1


def test_random_interleavings_never_commit_while_gate_closed():
    """Stress: random control commands vs. a decision loop; a commit must never happen unless the
    state allowed it at that instant, and never after a confirmed pause before the next resume."""
    rng = random.Random(5)
    for trial in range(30):
        c = SessionController()
        c.start()
        violations: list[str] = []
        stop = threading.Event()

        def decider(c=c, stop=stop, violations=violations) -> None:  # noqa: ANN001
            while not stop.is_set():
                try:
                    e = c.begin_decision()
                except SessionAbort:
                    return
                time.sleep(rng.random() * 0.002)
                if c.try_commit(e):
                    with c._cond:  # noqa: SLF001 - test inspects the invariant atomically
                        if c.state not in (State.RUNNING, State.STOPPING_AFTER_HAND, State.PAUSING):
                            violations.append(c.state.value)
                    c.end_commit()

        th = threading.Thread(target=decider, daemon=True)
        th.start()
        for _ in range(40):
            cmd = rng.choice(["pause", "resume", "pause", "resume", "noop"])
            if cmd == "pause":
                c.pause()
                assert c.wait_paused(1)
                n = c.committed
                time.sleep(0.003)
                assert c.committed == n, "commit after confirmed pause"
            elif cmd == "resume":
                c.resume(OK)
            time.sleep(rng.random() * 0.002)
        c.emergency()
        stop.set()
        th.join(2)
        assert not violations and not th.is_alive(), trial
