"""Session control: explicit state machine + action gate with epochs (P9-C).

Guarantees (tested in tests/lab/test_control.py):
- autonomy by default after a confirmed start; the agent plays without per-hand approval;
- Pause / Emergency / Finish take priority over pending decisions: they bump the *epoch* and
  close the gate atomically; a decision computed under an older epoch is DISCARDED;
- an action is committed only through ``try_commit(epoch)`` (gate open + same epoch); "paused" is
  confirmed only once no commit is in flight (``end_commit``); nothing is committed afterwards;
- resuming requires a successful synchronization check; after a quality stop it also requires an
  explicit human acknowledgement;
- every transition is recorded with time, origin, target, command, reason, epoch and actor.

The same controller is meant to drive online sessions later (stage E); in a local simulation the
table simply waits while paused (a real server would apply its own timeout action instead).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class State(StrEnum):
    IDLE = "ocioso"
    RUNNING = "autonomo"
    PAUSING = "pausando"
    PAUSED = "supervisionado"
    RESUMING = "sincronizando"
    QUALITY_STOP = "parado_qualidade"
    STOPPING_AFTER_HAND = "saindo_apos_mao"
    EMERGENCY = "emergencia"
    FINISHED = "encerrado"
    ERROR = "erro"


ACTIVE = {State.RUNNING, State.PAUSING, State.PAUSED, State.RESUMING, State.QUALITY_STOP, State.STOPPING_AFTER_HAND}
BLOCKED = {State.PAUSING, State.PAUSED, State.RESUMING, State.QUALITY_STOP}
TERMINAL = {State.EMERGENCY, State.FINISHED, State.ERROR}
COMMIT_OK = {State.RUNNING, State.STOPPING_AFTER_HAND}

# (state, command) -> next state. Anything else is refused (or a no-op when already there).
TRANSITIONS: dict[tuple[State, str], State] = {
    (State.IDLE, "start"): State.RUNNING,
    (State.RUNNING, "pause"): State.PAUSING,
    (State.STOPPING_AFTER_HAND, "pause"): State.PAUSING,
    (State.PAUSING, "confirm_pause"): State.PAUSED,
    (State.PAUSED, "resume"): State.RESUMING,
    (State.RESUMING, "synced"): State.RUNNING,
    (State.RESUMING, "sync_failed"): State.PAUSED,
    (State.RUNNING, "quality_stop"): State.QUALITY_STOP,
    (State.STOPPING_AFTER_HAND, "quality_stop"): State.QUALITY_STOP,
    (State.PAUSING, "quality_stop"): State.QUALITY_STOP,
    (State.QUALITY_STOP, "ack_resume"): State.RESUMING,
    (State.RUNNING, "finish_after_hand"): State.STOPPING_AFTER_HAND,
    (State.RUNNING, "hand_boundary_finish"): State.FINISHED,
    (State.STOPPING_AFTER_HAND, "hand_boundary_finish"): State.FINISHED,
}
for _s in ACTIVE:
    TRANSITIONS[(_s, "emergency")] = State.EMERGENCY
    TRANSITIONS[(_s, "finish_now")] = State.FINISHED
    TRANSITIONS[(_s, "fail")] = State.ERROR
    TRANSITIONS[(_s, "complete")] = State.FINISHED
TRANSITIONS[(State.EMERGENCY, "complete")] = State.FINISHED  # emergency protocol done
TRANSITIONS[(State.IDLE, "fail")] = State.ERROR


class SessionAbort(BaseException):  # noqa: N818 - BaseException on purpose: agent wrappers must not swallow it
    """Raised inside the decision path to abandon the current hand (emergency / finish now)."""


class TransitionRefused(RuntimeError):
    pass


@dataclass
class Transition:
    at: float
    from_state: str
    to_state: str
    command: str
    reason: str
    epoch: int
    actor: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


EventSink = Callable[[Transition], None]


class SessionController:
    def __init__(self, sink: EventSink | None = None, clock: Callable[[], float] = time.time) -> None:
        self._cond = threading.Condition(threading.RLock())
        self.state = State.IDLE
        self.epoch = 0
        self.in_flight = False
        self.discarded = 0
        self.committed = 0
        self.history: list[Transition] = []
        self.stop_reason: str | None = None
        self._sink = sink
        self._clock = clock

    # ------------------------------------------------------------------ transitions
    def _go(self, command: str, reason: str = "", actor: str = "sistema") -> State:
        nxt = TRANSITIONS.get((self.state, command))
        if nxt is None:
            raise TransitionRefused(f"'{command}' não permitido no estado '{self.state.value}'")
        t = Transition(self._clock(), self.state.value, nxt.value, command, reason, self.epoch, actor)
        self.state = nxt
        self.history.append(t)
        if self._sink:
            self._sink(t)
        self._cond.notify_all()
        return nxt

    def snapshot(self) -> dict[str, Any]:
        with self._cond:
            return {"state": self.state.value, "epoch": self.epoch, "in_flight": self.in_flight,
                    "discarded": self.discarded, "committed": self.committed, "stop_reason": self.stop_reason,
                    "pause_confirmed": self.state is State.PAUSED}

    # ------------------------------------------------------------------ user / system commands
    def start(self, actor: str = "usuario") -> State:
        with self._cond:
            return self._go("start", "início confirmado", actor)

    def pause(self, actor: str = "usuario") -> State:
        with self._cond:
            if self.state in (State.PAUSING, State.PAUSED, State.QUALITY_STOP):
                return self.state  # repeated click: no-op
            self.epoch += 1  # invalidates every decision computed before this instant
            self._go("pause", "pausa solicitada", actor)
            if not self.in_flight:
                self._go("confirm_pause", "nenhuma ação em andamento", "sistema")
            return self.state

    def wait_paused(self, timeout: float = 5.0) -> bool:
        """True once the pause is confirmed (no automatic action can still be committed)."""
        with self._cond:
            return self._cond.wait_for(lambda: self.state is not State.PAUSING, timeout) and self.state is not State.PAUSING

    def resume(self, sync_check: Callable[[], tuple[bool, str]], actor: str = "usuario") -> State:
        with self._cond:
            if self.state is State.RUNNING:
                return self.state  # repeated click
            if self.state is State.QUALITY_STOP:
                raise TransitionRefused("parada por qualidade: é preciso revisar o relatório e confirmar a retomada")
            self._go("resume", "retomada solicitada", actor)
            return self._sync(sync_check)

    def acknowledge_quality_and_resume(self, confirm: bool, note: str, sync_check: Callable[[], tuple[bool, str]],
                                       actor: str = "usuario") -> State:
        with self._cond:
            if self.state is not State.QUALITY_STOP:
                raise TransitionRefused("não há parada por qualidade pendente")
            if not confirm or not note.strip():
                raise TransitionRefused("confirmação explícita e uma nota da revisão são obrigatórias")
            self._go("ack_resume", f"revisão confirmada: {note.strip()[:200]}", actor)
            return self._sync(sync_check)

    def _sync(self, sync_check: Callable[[], tuple[bool, str]]) -> State:
        ok, detail = sync_check()
        self.epoch += 1
        return self._go("synced" if ok else "sync_failed", detail, "sistema")

    def quality_stop(self, reason: str) -> State:
        with self._cond:
            if self.state not in (State.RUNNING, State.STOPPING_AFTER_HAND, State.PAUSING):
                return self.state
            self.epoch += 1
            self.stop_reason = reason
            return self._go("quality_stop", reason, "monitor_qualidade")

    def emergency(self, reason: str = "parada de emergência", actor: str = "usuario") -> State:
        with self._cond:
            if self.state in TERMINAL or self.state is State.IDLE:
                return self.state
            self.epoch += 1
            self.stop_reason = reason
            return self._go("emergency", reason, actor)

    def finish(self, mode: str = "after_hand", actor: str = "usuario") -> State:
        with self._cond:
            if self.state in TERMINAL:
                return self.state
            if mode == "after_hand" and self.state is State.RUNNING:
                return self._go("finish_after_hand", "encerrar após a mão atual", actor)
            if mode == "after_hand" and self.state is State.STOPPING_AFTER_HAND:
                return self.state
            self.epoch += 1
            return self._go("finish_now", "encerrar agora", actor)

    def fail(self, reason: str) -> State:
        with self._cond:
            if self.state in TERMINAL:
                return self.state
            self.epoch += 1
            self.stop_reason = reason
            return self._go("fail", reason, "sistema")

    def complete(self, reason: str) -> State:
        with self._cond:
            if self.state in (State.FINISHED, State.ERROR):
                return self.state
            self.epoch += 1
            return self._go("complete", reason, "sistema")

    def at_hand_boundary(self) -> bool:
        """Called between hands. True when the session must end now (finish after hand)."""
        with self._cond:
            if self.state is State.STOPPING_AFTER_HAND:
                self._go("hand_boundary_finish", "mão concluída; encerrando", "sistema")
                return True
            return self.state in TERMINAL

    # ------------------------------------------------------------------ decision path (agent side)
    def begin_decision(self) -> int:
        """Block while autonomy is suspended; abort on terminal states. Returns the current epoch."""
        with self._cond:
            self._cond.wait_for(lambda: self.state not in BLOCKED)
            if self.state in TERMINAL or self.state is State.IDLE:
                raise SessionAbort(self.state.value)
            return self.epoch

    def is_current(self, epoch: int) -> bool:
        with self._cond:
            return self.state in COMMIT_OK and epoch == self.epoch

    def wait_change(self, epoch: int, timeout: float) -> None:
        with self._cond:
            self._cond.wait_for(lambda: self.epoch != epoch or self.state not in COMMIT_OK, timeout)

    def try_commit(self, epoch: int) -> bool:
        with self._cond:
            if self.state in COMMIT_OK and epoch == self.epoch and not self.in_flight:
                self.in_flight = True
                return True
            self.discarded += 1
            return False

    def end_commit(self) -> None:
        with self._cond:
            if not self.in_flight:
                return
            self.in_flight = False
            self.committed += 1
            if self.state is State.PAUSING:
                self._go("confirm_pause", "ação em andamento concluída; nenhuma nova ação será enviada", "sistema")
            self._cond.notify_all()
