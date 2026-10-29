"""Wraps the session's (frozen) policy so every decision goes through the controller's gate."""

from __future__ import annotations

import concurrent.futures as cf
import contextlib
import time
from typing import Any

from poker_lab.agents.base import Agent
from poker_lab.domain.actions import Action
from poker_lab.domain.observation import Observation
from poker_lab.lab.control import SessionAbort, SessionController


class ControlledAgent(Agent):
    """Decision = begin (blocks while paused) -> compute in a worker -> commit only if the epoch is
    still current. Results that arrive after a pause/emergency/finish are discarded. The inner
    policy object is never modified; a stale computation is awaited (not run concurrently) before
    the next one starts, so the policy's internal state is never used by two decisions at once."""

    algorithm = "controlled"

    def __init__(self, inner: Agent, controller: SessionController, decision_timeout_s: float = 10.0,
                 poll_s: float = 0.02) -> None:
        super().__init__(inner.name, inner.version_label, inner.seed)
        self.inner = inner
        self.ctrl = controller
        self.timeout = decision_timeout_s
        self.poll = poll_s
        self._pool = cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="decision")
        self._stale: cf.Future[Action] | None = None
        self.last_issue: str | None = None
        self.discard_log: list[dict[str, Any]] = []
        self.last_obs: Observation | None = None  # decision-time observation of the last committed action

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def act(self, obs: Observation) -> Action:
        while True:
            epoch = self.ctrl.begin_decision()
            if self._stale is not None:  # finish the abandoned computation before reusing the policy
                with contextlib.suppress(Exception):  # its result is discarded anyway
                    self._stale.result(timeout=max(self.timeout, 1.0))
                self._stale = None
            t0 = time.perf_counter()
            fut = self._pool.submit(self.inner.act, obs)
            self.last_issue = None
            action: Action | None = None
            while True:
                try:
                    action = fut.result(timeout=self.poll)
                    break
                except cf.TimeoutError:
                    if not self.ctrl.is_current(epoch):
                        break
                    if time.perf_counter() - t0 > self.timeout:
                        self.last_issue = "timeout"
                        break
            if action is None and self.last_issue == "timeout":
                self._stale = fut
                action = obs.legal.safe_default()
            elif action is None:  # control changed during the computation: discard and wait
                self._stale = fut
                self.discard_log.append({"at": time.time(), "epoch": epoch, "reason": "controle mudou durante o cálculo"})
                self.ctrl.try_commit(epoch)  # counts the discard (returns False)
                continue
            if self.ctrl.try_commit(epoch):
                self.last_obs = obs
                self.last_info = dict(getattr(self.inner, "last_info", {}) or {})
                if self.last_issue:
                    self.last_info["issue"] = self.last_issue
                return action
            self.discard_log.append({"at": time.time(), "epoch": epoch, "reason": "resultado chegou após pausa/parada"})
            # loop: begin_decision blocks while paused or raises on terminal states

    def raise_if_terminal(self) -> None:
        self.ctrl.begin_decision()


__all__ = ["ControlledAgent", "SessionAbort"]
