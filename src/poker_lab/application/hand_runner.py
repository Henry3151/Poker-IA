"""Runs one hand between agents. Every action is validated by the engine.

Invalid actions, agent exceptions and decisions over the latency budget are recorded as
execution issues and replaced by the safe default (check, else fold), which is what a
real table would do on a timeout. The agent only ever receives an ``Observation``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from poker_lab.agents.base import Agent
from poker_lab.domain.actions import Action
from poker_lab.engine.hand import HandEngine, HandResult


@dataclass(slots=True)
class DecisionRecord:
    decision_id: str
    hand_id: str
    seq_in_hand: int
    seat: int
    player_id: str
    street: str
    position: str
    observation: dict[str, Any]
    legal: dict[str, Any]
    requested: dict[str, Any] | None
    applied: dict[str, Any]
    valid: bool
    fallback_applied: bool
    issue: str | None  # None | invalid_action | agent_exception | timeout
    error: str | None
    latency_ms: float
    info: dict[str, Any]
    pot_before: int
    to_call: int
    stack_before: int
    effective_stack: int
    big_blind: int
    chips_added: int = 0


@dataclass(slots=True)
class HandRecord:
    hand_id: str
    engine: HandEngine
    result: HandResult
    decisions: list[DecisionRecord] = field(default_factory=list)
    seat_agents: list[Agent] = field(default_factory=list)


DecisionHook = Callable[[DecisionRecord], None]


def play_hand(
    engine: HandEngine,
    seat_agents: Sequence[Agent],
    *,
    latency_budget_ms: float = 2000.0,
    on_decision: DecisionHook | None = None,
) -> HandRecord:
    if len(seat_agents) != engine.n:
        raise ValueError("one agent per seat required")
    decisions: list[DecisionRecord] = []
    seq = 0
    while not engine.is_finished:
        seat = engine.to_act
        assert seat is not None
        obs = engine.observation(seat)
        agent = seat_agents[seat]
        requested: Action | None = None
        issue: str | None = None
        error: str | None = None
        t0 = time.perf_counter()
        try:
            requested = agent.act(obs)
        except Exception as exc:  # agent bugs must never crash the table
            issue, error = "agent_exception", f"{type(exc).__name__}: {exc}"
        latency = (time.perf_counter() - t0) * 1000.0
        applied: Action
        if issue is None and latency > latency_budget_ms:
            issue, error = "timeout", f"{latency:.1f}ms > {latency_budget_ms}ms"
        if issue is None:
            assert requested is not None
            why = obs.legal.why_illegal(requested) if isinstance(requested, Action) else "not an Action"
            if why is not None:
                issue, error = "invalid_action", why
        applied = obs.legal.safe_default() if issue else requested  # type: ignore[assignment]
        stack_before = obs.stack
        engine.apply(seat, applied)  # engine re-validates
        added = next(int(e.payload["added"]) for e in reversed(engine.events) if e.type == "action_applied")
        rec = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            hand_id=engine.hand_id,
            seq_in_hand=seq,
            seat=seat,
            player_id=obs.player_id,
            street=obs.street.label,
            position=obs.position,
            observation=obs.to_dict(),
            legal=obs.legal.to_dict(),
            requested=requested.to_dict() if isinstance(requested, Action) else None,
            applied=applied.to_dict(),
            valid=issue is None,
            fallback_applied=issue is not None,
            issue=issue,
            error=error,
            latency_ms=round(latency, 3),
            info=dict(agent.last_info),
            pot_before=obs.pot,
            to_call=obs.to_call,
            stack_before=stack_before,
            effective_stack=obs.effective_stack,
            big_blind=obs.big_blind,
            chips_added=added,
        )
        decisions.append(rec)
        if on_decision:
            on_decision(rec)
        seq += 1
    return HandRecord(engine.hand_id, engine, engine.result(), decisions, list(seat_agents))


@dataclass(slots=True)
class SessionResult:
    hands: int
    net_by_agent: dict[str, int]
    invalid_actions: int
    decisions: int


def play_session(
    agents: Sequence[Agent],
    n_hands: int,
    *,
    starting_stack: int = 10_000,
    small_blind: int = 50,
    big_blind: int = 100,
    seed: int = 0,
    on_hand: Callable[[HandRecord], None] | None = None,
) -> SessionResult:
    """Cash-style session: stacks reset every hand, button rotates. Used for smoke tests."""
    from poker_lab.domain.seeds import derive_seed

    n = len(agents)
    net = {a.name: 0 for a in agents}
    if len(net) != n:
        raise ValueError("agent names must be unique in a session")
    invalid = 0
    n_dec = 0
    for h in range(n_hands):
        e = HandEngine(
            [(a.name, starting_stack) for a in agents],
            button=h % n,
            small_blind=small_blind,
            big_blind=big_blind,
            seed=derive_seed(seed, "session_hand", h),
            hand_id=str(uuid.uuid4()),
        )
        rec = play_hand(e, agents)
        for i, a in enumerate(agents):
            net[a.name] += rec.result.net[i]
        invalid += sum(1 for d in rec.decisions if not d.valid)
        n_dec += len(rec.decisions)
        if on_hand:
            on_hand(rec)
    return SessionResult(n_hands, net, invalid, n_dec)
