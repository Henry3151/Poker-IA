"""Open Poker session runner (virtual chips only).

Responsibilities: official WebSocket protocol, Bearer auth from OPEN_POKER_API_KEY (never
logged), translation to internal observations, legal-only actions, idempotent sends
(stable client_action_id per turn_token), duplicate/regressed message handling, bounded
reconnect + resync, internal decision budget with safe fallback, rate limiting, kill
switch, hand limit, and recording.

Safety model for actions (P11 criteria 4-5):
- every action is bound to exactly one ``turn_token`` and one ``client_action_id``
  (uuid5 of hand_id + token); a token is used for at most one decision;
- a token dies on ack, on any rejection, on hand_result / a new hand, on table change;
  dead tokens are never reused;
- a pending (sent, not acked) action is resent only when the server repeats the SAME token
  for the SAME hand with no newer table event and no different ``state_hash``; otherwise it
  is dropped and a resync is requested;
- after a disconnect, ``state_hash`` mismatch, impossible local state (pot/hand/hero
  divergence) or an unexpected rejection, the session is PAUSED: no action is sent (the server's documented
  45 s auto check/fold applies) until a resync snapshot is installed; if that does not
  happen within ``resync_timeout_s`` / ``max_resync_attempts`` the session stops.
  ``table_seq`` gaps are documented as normal and only counted (no resync on gaps alone). It never calls wallet/deposit/credit/Pro endpoints and
never automates a graphical interface.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from poker_lab.agents.base import Agent
from poker_lab.domain.actions import Action
from poker_lab.integrations.openpoker import protocol as P
from poker_lab.integrations.openpoker.config import OpenPokerConfig, RedactingFilter
from poker_lab.integrations.openpoker.recorder import OnlineRecorder
from poker_lab.integrations.openpoker.state import (
    StateDivergence,
    TableTracker,
    UnsupportedState,
    state_hash_ok,
    to_platform,
)

log = logging.getLogger("poker_lab.openpoker")


class Transport(Protocol):
    async def send(self, text: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


Connector = Callable[[], Awaitable[Transport]]


class TransportClosed(Exception):
    pass


async def websocket_connector(cfg: OpenPokerConfig) -> Transport:  # pragma: no cover - needs network
    import websockets

    ws = await websockets.connect(cfg.ws_url, additional_headers=cfg.api_key.bearer_header(), open_timeout=15)

    class _WS:
        async def send(self, text: str) -> None:
            await ws.send(text)

        async def recv(self) -> str:
            try:
                msg = await ws.recv()
            except websockets.ConnectionClosed as exc:
                raise TransportClosed(str(exc.code)) from exc
            return msg if isinstance(msg, str) else msg.decode()

        async def close(self) -> None:
            await ws.close()

    return _WS()


@dataclass
class SessionStats:
    hands_completed: int = 0
    decisions: int = 0
    actions_sent: int = 0
    resends: int = 0
    acks: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    fallbacks: int = 0
    timeouts: int = 0
    unsupported_states: int = 0
    divergences: int = 0
    hash_mismatches: int = 0
    gaps: int = 0
    pauses: int = 0
    turns_skipped_paused: int = 0
    pending_dropped: int = 0
    resyncs_requested: int = 0
    reconnects: int = 0
    duplicates_ignored: int = 0
    start_balance_stack: int | None = None
    end_stack: int | None = None
    stop_reason: str = ""


class RateLimiter:
    def __init__(self, per_second: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.interval = 1.0 / per_second
        self.clock = clock
        self.next_at = 0.0

    async def wait(self) -> None:
        now = self.clock()
        if now < self.next_at:
            await asyncio.sleep(self.next_at - now)
        self.next_at = max(now, self.next_at) + self.interval


@dataclass
class PendingAction:
    turn_token: str
    hand_id: str
    payload: dict[str, Any]
    event_seq_at_send: int
    state_hash: str | None


TURN_GONE_CODES = {"stale_turn_token", "not_your_turn", "stale_hand_action", "no_hand_in_progress"}
PROTOCOL_BUG_CODES = {"action_id_conflict", "legacy_action_protocol", "missing_action_id"}
STATE_EVENTS_EXCLUDED = {"your_turn", "action_ack", "action_rejected", "error", "connected", "lobby_joined"}


class OpenPokerSession:
    def __init__(
        self,
        cfg: OpenPokerConfig,
        agent: Agent,
        connector: Connector,
        recorder: OnlineRecorder | None = None,
        agent_label: str = "cash6max-v0",
    ) -> None:
        self.cfg = cfg
        self.agent = agent
        self.connector = connector
        self.recorder = recorder
        self.agent_label = agent_label
        self.tracker = TableTracker()
        self.stats = SessionStats()
        self.rate = RateLimiter(cfg.messages_per_second)
        self.pending: PendingAction | None = None
        self.dead_tokens: set[str] = set()
        self.decided_tokens: set[str] = set()
        self.last_event_seq = 0  # table_seq of the last accepted state-changing event
        self.paused: str | None = None
        self.paused_since = 0.0
        self.resync_attempts = 0
        self.stopping = False
        self.left = False
        self._ws: Transport | None = None
        self._redactor = RedactingFilter(cfg.api_key)
        log.addFilter(self._redactor)

    # ------------------------------------------------------------ io
    async def _send(self, payload: dict[str, Any]) -> None:
        assert self._ws is not None
        await self.rate.wait()
        text = json.dumps(payload, separators=(",", ":"))
        if self.cfg.api_key.matches(text):  # defence in depth: never send the key in a message body
            raise RuntimeError("refusing to send a payload containing the API key")
        await self._ws.send(text)

    async def run(self) -> SessionStats:
        reconnect_deadline: float | None = None
        backoff = 1.0
        while not self.left:
            try:
                self._ws = await self.connector()
            except Exception as exc:  # connection failure
                log.warning("connect failed: %s", type(exc).__name__)
                if reconnect_deadline is None:
                    reconnect_deadline = time.monotonic() + self.cfg.max_reconnect_seconds
                if time.monotonic() + backoff > reconnect_deadline:
                    self.stats.stop_reason = "reconnect_window_exceeded"
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)
                continue
            if reconnect_deadline is not None:
                self.stats.reconnects += 1
            reconnect_deadline, backoff = None, 1.0
            try:
                await self._loop()
            except TransportClosed:
                log.warning("transport closed; pausing actions and reconnecting")
                self._pause("disconnected")
                self.resync_attempts = 0
                reconnect_deadline = time.monotonic() + self.cfg.max_reconnect_seconds
                continue
            finally:
                with contextlib.suppress(Exception):  # closing is best effort
                    await self._ws.close()
        self.stats.duplicates_ignored = self.tracker.duplicates_ignored
        if self.recorder:
            self.recorder.close_session(self.stats)
        log.removeFilter(self._redactor)
        return self.stats

    async def _loop(self) -> None:
        while True:
            if self.cfg.kill_switch.exists() and not self.stopping:
                self.stats.stop_reason = "kill_switch"
                self.stopping = True
                await self._leave()
                return
            if self.paused and self.paused != "disconnected" and time.monotonic() - self.paused_since > self.cfg.resync_timeout_s:
                if self.resync_attempts >= self.cfg.max_resync_attempts:
                    self.stats.stop_reason = "reconciliation_failed"
                    self.stopping = True
                    await self._leave()
                    return
                await self._request_resync()
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=min(1.0, self.cfg.resync_timeout_s))  # type: ignore[union-attr]
            except TimeoutError:
                continue
            try:
                data = json.loads(raw)
                msg = P.parse(raw)
            except Exception:  # malformed -> ignore, never crash the session
                log.warning("malformed message ignored")
                continue
            if not self.tracker.accept(msg):
                continue
            if not state_hash_ok(data):
                self.stats.hash_mismatches += 1
                log.warning("state_hash mismatch on %s", msg.type)
                self._pause("state_hash_mismatch")
                await self._request_resync()
                continue
            if self.tracker.gap_pending:  # documented as normal (private messages consume seq): count only
                self.tracker.gap_pending = False
                self.stats.gaps += 1
            if msg.table_seq is not None and msg.type not in STATE_EVENTS_EXCLUDED:
                self.last_event_seq = msg.table_seq
            done = await self._handle(msg)
            if done:
                return

    async def _leave(self) -> None:
        if not self.left:
            await self._send(P.leave_table())
            self.left = True

    # ------------------------------------------------------------ pause / resync
    def _pause(self, reason: str) -> None:
        if self.paused is None:
            self.stats.pauses += 1
            self.paused_since = time.monotonic()
        self.paused = reason
        log.warning("actions paused: %s", reason)

    def _resume(self) -> None:
        if self.paused is not None:
            log.info("actions resumed after %s", self.paused)
        self.paused = None
        self.resync_attempts = 0

    async def _request_resync(self) -> None:
        if not self.tracker.table_id:
            return
        self.resync_attempts += 1
        self.paused_since = time.monotonic()
        self.stats.resyncs_requested += 1
        await self._send(P.resync_request(self.tracker.table_id, self.tracker.last_table_seq))

    def _kill_token(self, token: str | None) -> None:
        if token:
            self.dead_tokens.add(token)
        if self.pending is not None and (token is None or self.pending.turn_token == token):
            self.pending = None

    def _drop_pending(self, reason: str) -> None:
        if self.pending is not None:
            log.info("pending action dropped (%s)", reason)
            self.stats.pending_dropped += 1
            self.dead_tokens.add(self.pending.turn_token)
            self.pending = None

    # ------------------------------------------------------------ dispatch
    async def _handle(self, msg: P._Msg) -> bool:
        t = msg.type
        if t == "connected":
            log.info("connected as %s", getattr(msg, "name", "?"))
            if self.tracker.table_id:  # warm restart: resync instead of re-joining
                self._pause("awaiting_resync")
                await self._request_resync()
            else:
                await self._send(P.join_lobby(self.cfg.buy_in))
                await self._send(P.set_auto_rebuy(self.cfg.auto_rebuy))
            return False
        if t == "error":
            code = getattr(msg, "code", "")
            if code in ("auth_failed", "flood_kick"):
                self.stats.stop_reason = code
                self.left = True
                return True
            return False
        if t == "resync_response":
            await self._on_resync(msg)
            return False
        if t in ("table_closed", "season_ended"):
            self._drop_pending("table_closed")
            self.dead_tokens.clear()
            if self.stopping:
                self.left = True
                return True
            self.tracker = TableTracker()
            self.last_event_seq = 0
            self._resume()
            await self._send(P.join_lobby(self.cfg.buy_in))
            return False
        if t == "busted":
            if not self.cfg.auto_rebuy:
                self.stats.stop_reason = "busted"
                self.stopping = True
                await self._leave()
                return True
            return False
        if isinstance(msg, P.HandStart | P.HandResult):
            self._drop_pending(t)  # a token never survives its hand
        try:
            self.tracker.apply(msg)
        except UnsupportedState as exc:
            self.stats.unsupported_states += 1
            log.warning("unsupported state: %s", exc)
        if isinstance(msg, P.HandStart) and self.recorder:
            self.recorder.hand_started(msg, self.tracker)
        if isinstance(msg, P.YourTurn):
            await self._on_turn(msg)
        elif isinstance(msg, P.ActionAck):
            self.stats.acks += 1
            if self.pending is not None and self.pending.payload["client_action_id"] == msg.client_action_id:
                self._kill_token(self.pending.turn_token)
            if self.recorder:
                self.recorder.ack(msg.client_action_id, msg.status)
        elif isinstance(msg, P.ActionRejected):
            await self._on_rejected(msg)
        elif isinstance(msg, P.HandResult):
            self.stats.hands_completed += 1
            if self.tracker.my_seat is not None:
                self.stats.end_stack = msg.final_stacks.get(str(self.tracker.my_seat), self.stats.end_stack)
            if self.recorder:
                self.recorder.hand_finished(msg, self.tracker)
            if self.stats.hands_completed >= self.cfg.max_hands and not self.stopping:
                self.stopping = True
                self.stats.stop_reason = "max_hands"
                await self._leave()
                return True
        return False

    async def _on_resync(self, msg: P._Msg) -> None:
        extra = msg.model_extra or {}
        events = extra.get("replayed_events", []) or []
        before = self.tracker.last_table_seq
        for ev in events:
            try:
                m = P.parse(json.dumps(ev))
            except Exception:  # noqa: BLE001
                continue
            if not state_hash_ok(ev):
                self.stats.hash_mismatches += 1
                return  # stay paused; the timeout loop retries
            if self.tracker.accept(m) and m.type not in ("your_turn",):
                if m.table_seq is not None and m.type not in STATE_EVENTS_EXCLUDED:
                    self.last_event_seq = m.table_seq
                with contextlib.suppress(UnsupportedState):
                    if isinstance(m, P.HandStart | P.HandResult):
                        self._drop_pending(m.type)
                    self.tracker.apply(m)
        self.tracker.gap_pending = False
        snap = extra.get("snapshot") or {}
        to_seq = extra.get("to_table_seq")
        if snap:
            self.tracker.install_snapshot(snap, snap.get("hand_id") or self.tracker.hand_id)
            if to_seq is not None:
                self.tracker.last_table_seq = max(self.tracker.last_table_seq, int(to_seq))
        elif to_seq is None or int(to_seq) != self.tracker.last_table_seq:
            log.warning("resync without snapshot did not reach the server sequence (%s -> %s)", before, to_seq)
            return  # stay paused
        self._resume()
        hero = snap.get("hero") or {}
        token = hero.get("turn_token")
        if self.pending is not None and token != self.pending.turn_token:
            self._drop_pending("snapshot_token_changed")
        if token and hero.get("valid_actions") and self.tracker.hand_id and token not in self.dead_tokens:
            if self.pending is not None and token == self.pending.turn_token:
                await self._resend_pending()  # same token, same client_action_id: dedupe-safe
                return
            if token in self.decided_tokens:
                return
            turn = P.YourTurn.model_validate(
                {
                    "type": "your_turn",
                    "hand_id": self.tracker.hand_id,
                    "valid_actions": hero["valid_actions"],
                    "pot": snap.get("pot", 0),
                    "community_cards": snap.get("board", []),
                    "players": [{"seat": s["seat"], "name": s.get("name"), "stack": s.get("stack", 0)} for s in snap.get("seats", [])],
                    "min_raise": snap.get("min_raise_to"),
                    "max_raise": snap.get("max_raise_to"),
                    "turn_token": token,
                }
            )
            await self._on_turn(turn)

    async def _resend_pending(self) -> None:
        assert self.pending is not None
        self.stats.resends += 1
        await self._send(self.pending.payload)

    async def _on_turn(self, turn: P.YourTurn) -> None:
        token = turn.turn_token
        if token in self.dead_tokens:
            log.info("your_turn with a dead token ignored")
            return
        if self.paused is not None:
            self.stats.turns_skipped_paused += 1  # server auto-acts at its deadline
            return
        if self.pending is not None and self.pending.turn_token == token:
            h = (turn.model_extra or {}).get("state_hash")
            compatible = (
                turn.hand_id in (None, self.pending.hand_id)
                and self.last_event_seq <= self.pending.event_seq_at_send
                and (h is None or self.pending.state_hash is None or h == self.pending.state_hash)
            )
            if compatible:
                await self._resend_pending()
            else:
                self._drop_pending("incompatible_state_change")
                self._pause("pending_incompatible")
                await self._request_resync()
            return
        if token in self.decided_tokens:
            return
        if self.pending is not None:  # a new token supersedes an unacked one: never resend the old
            self._drop_pending("superseded")
        self.decided_tokens.add(token)
        self.stats.decisions += 1
        t0 = time.perf_counter()
        status = "ok"
        requested: Action | None = None
        try:
            obs, ctx = self.tracker.observation(turn)
        except StateDivergence as exc:
            self.stats.divergences += 1
            self.decided_tokens.discard(token)  # may be answered after a consistent snapshot
            log.warning("state divergence at decision: %s", exc)
            self._pause("divergence")
            await self._request_resync()
            return
        except UnsupportedState as exc:
            self.stats.unsupported_states += 1
            log.warning("unsupported state at decision: %s", exc)
            kind = "check" if any(v.action == "check" for v in turn.valid_actions) else "fold"
            await self._send_action(turn, kind, None, "unsupported_state_fallback", None, None, t0)
            return
        try:
            requested = await asyncio.wait_for(asyncio.to_thread(self.agent.act, obs), timeout=self.cfg.decision_budget_s)
        except TimeoutError:
            self.stats.timeouts += 1
            status = "timeout_fallback"
        except Exception as exc:  # noqa: BLE001 - agent bugs never crash the session
            status = f"agent_exception_fallback:{type(exc).__name__}"
        chosen = requested if status == "ok" and isinstance(requested, Action) else obs.legal.safe_default()
        try:
            kind, amount = to_platform(chosen, obs.legal, ctx)
        except ValueError:
            status = "invalid_internal_action_fallback"
            kind, amount = to_platform(obs.legal.safe_default(), obs.legal, ctx)
        if status != "ok":
            self.stats.fallbacks += 1
        if self.paused is not None or token in self.dead_tokens:
            self.stats.turns_skipped_paused += 1  # state changed while thinking: do not act
            return
        await self._send_action(turn, kind, amount, status, obs, requested, t0)

    async def _send_action(
        self, turn: P.YourTurn, kind: str, amount: int | None, status: str, obs: Any, requested: Action | None, t0: float
    ) -> None:
        cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"openpoker/{turn.hand_id}/{turn.turn_token}"))
        payload = P.action(turn.hand_id or "", kind, amount, cid, turn.turn_token)
        self.pending = PendingAction(
            turn.turn_token, turn.hand_id or "", payload, self.last_event_seq, (turn.model_extra or {}).get("state_hash")
        )
        await self._send(payload)
        self.stats.actions_sent += 1
        if self.recorder:
            self.recorder.decision(
                turn, obs, payload, status, (time.perf_counter() - t0) * 1000, requested, getattr(self.agent, "last_info", {})
            )

    async def _on_rejected(self, msg: P.ActionRejected) -> None:
        self.stats.rejected[msg.code] = self.stats.rejected.get(msg.code, 0) + 1
        if self.recorder:
            self.recorder.rejected(msg.code, msg.reason)
        # any rejection kills the pending token: never retry it, never re-decide it
        self._kill_token(self.pending.turn_token if self.pending else None)
        code = msg.code
        if code == "invalid_action":
            if self.stats.rejected.get("invalid_action", 0) >= self.cfg.max_invalid_actions:
                self.stats.stop_reason = "too_many_invalid_actions"
                self.stopping = True
                await self._leave()
        elif code in TURN_GONE_CODES:
            pass  # the turn no longer exists; the server already acted or moved on
        elif code in PROTOCOL_BUG_CODES:
            self.stats.stop_reason = f"protocol_error:{code}"  # our bug: stop rather than guess
            self.stopping = True
            await self._leave()
        else:  # not_at_table / table_not_found / unknown future codes: our state is wrong
            self._pause(f"rejected:{code}")
            await self._request_resync()
