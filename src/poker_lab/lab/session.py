"""Autonomous local-simulation sessions (P9-C).

A session is a sequence of 6-max hands with fixed starting stacks (reset every hand, button
rotating). The hero is the frozen champion policy wrapped in ``ControlledAgent``; the other seats
are simulated opponent profiles. After a confirmed start the hero plays on its own until the hand
target, the time limit, a user command or a quality/technical stop.

Every hero decision is stored with its decision-time observation, graded by ``assessment.py``
(which only sees that observation; the hand's outcome is never used) and fed to the quality
monitor. Cards revealed at the end of the hand are stored separately, after the hand.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from poker_lab.agents.base import Agent
from poker_lab.agents.registry import OPPONENT_PROFILES, AgentSpec, create_agent
from poker_lab.application.hand_runner import DecisionRecord, HandRecord, play_hand
from poker_lab.domain.actions import Action
from poker_lab.domain.cards import cards_to_str
from poker_lab.domain.seeds import derive_seed
from poker_lab.engine.hand import HandEngine
from poker_lab.lab.assessment import PushFoldReference, technical
from poker_lab.lab.control import SessionAbort, SessionController, State, Transition
from poker_lab.lab.controlled_agent import ControlledAgent
from poker_lab.lab.quality import INCONCLUSIVE, QualityMonitor
from poker_lab.lab.store import SessionStore, dumps

FIELD_PROFILES = tuple(OPPONENT_PROFILES)
POLICY_LABEL = "hybrid-v1"
BIG_BLIND = 100
CHECKPOINT = "artifacts/checkpoints/pushfold-v2-ante.json"
TABLE = "artifacts/tables/hu_class_equity_s200_seed20261026.json"


def champion_spec(root: Path) -> AgentSpec:
    """The frozen champion, with the same parameters used in the P7c evaluation."""
    return AgentSpec(
        algorithm="policy", version_label=POLICY_LABEL, checkpoint_path=str(root / CHECKPOINT),
        params={"hybrid": True, "table_path": str(root / TABLE), "samples": 150, "bluff_rate": 0.0, "icm": True},
    )


def policy_fingerprint(root: Path, spec: AgentSpec) -> str:
    """sha256 over the policy files and parameters: proves the policy did not change during a session."""
    h = hashlib.sha256()
    for rel in (CHECKPOINT, TABLE):
        h.update((root / rel).read_bytes())
    params = {k: v for k, v in spec.params.items() if k != "table_path"}
    h.update(json.dumps({"label": spec.version_label, "params": params}, sort_keys=True).encode())
    return h.hexdigest()


class SimConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hands: int = Field(default=200, ge=1, le=100_000)
    seed: int = Field(default=1, ge=0, le=2**31 - 1)
    stack_bb: float = Field(default=15.0, ge=5, le=200)
    ante_bb: float = Field(default=0.0, ge=0, le=0.5)
    opponents: list[str] = Field(default_factory=lambda: ["tag", "lag", "nit", "station", "adaptive_tag"], min_length=1, max_length=5)
    max_minutes: int = Field(default=60, ge=1, le=1440)
    decision_timeout_s: float = Field(default=10.0, gt=0, le=60)

    @field_validator("opponents")
    @classmethod
    def _profiles(cls, v: list[str]) -> list[str]:
        bad = [p for p in v if p not in OPPONENT_PROFILES]
        if bad:
            raise ValueError(f"perfis desconhecidos: {bad}")
        return v


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def mean_ci(xs: list[float], min_n: int = 30) -> dict[str, Any]:
    """Mean with a normal 95% interval; ``enough`` flags samples too small to read."""
    n = len(xs)
    if n == 0:
        return {"n": 0, "mean": None, "low": None, "high": None, "enough": False}
    m = sum(xs) / n
    if n < 2:
        return {"n": n, "mean": round(m, 4), "low": None, "high": None, "enough": False}
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = 1.959963984540054 * sd / math.sqrt(n)
    return {"n": n, "mean": round(m, 4), "low": round(m - h, 4), "high": round(m + h, 4), "enough": n >= min_n}


def per100(ci: dict[str, Any]) -> dict[str, Any]:
    out = dict(ci)
    for k in ("mean", "low", "high"):
        if out.get(k) is not None:
            out[k] = round(out[k] * 100, 2)
    return out


def vpip_seats(rec: HandRecord) -> set[int]:
    """Seats that voluntarily put chips in the pot (call/bet/raise; blinds do not count)."""
    return {d.seat for d in rec.decisions if d.applied.get("kind") in ("call", "bet", "raise")}


class SimulationSession:
    def __init__(self, root: Path, store: SessionStore, cfg: SimConfig, hand_limit: int | None = None) -> None:
        self.root = root
        self.store = store
        self.cfg = cfg
        self.hands_target = min(cfg.hands, hand_limit) if hand_limit else cfg.hands
        self.session_id = uuid.uuid4().hex[:16]
        self.ctrl = SessionController(sink=self._on_transition)
        self.quality = QualityMonitor()
        self.reference = PushFoldReference.load(root)
        self.spec = champion_spec(root)
        self.policy_sha = policy_fingerprint(root, self.spec)
        inner = create_agent(self.spec, "hero", derive_seed(cfg.seed, "hero"))
        self.hero = ControlledAgent(inner, self.ctrl, cfg.decision_timeout_s)
        self.opponents: list[Agent] = [
            create_agent(OPPONENT_PROFILES[p], f"{p}#{i}", derive_seed(cfg.seed, "opponent", i)) for i, p in enumerate(cfg.opponents)
        ]
        self._lock = threading.Lock()
        self.hands_played = 0
        self.hands_aborted = 0
        self.net_bb: list[float] = []
        self.by_position: dict[str, list[float]] = defaultdict(list)
        self.by_opponent: dict[str, list[float]] = defaultdict(list)
        self.labels: dict[str, int] = defaultdict(int)
        self.ev_gaps: list[float] = []
        self.recent: list[dict[str, Any]] = []
        self.current_hand: int | None = None
        self._hand_engine: HandEngine | None = None
        self._expected_chips: int | None = None
        self.started_at = 0.0
        self.ended_at: float | None = None
        self.error: str | None = None
        self.thread: threading.Thread | None = None
        self.store.write(
            "INSERT INTO sessions(session_id,kind,created_at,state,policy_label,policy_sha256,config_json,seed,hands_target)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (self.session_id, "simulacao", _now(), State.IDLE.value, POLICY_LABEL, self.policy_sha,
             dumps(cfg.model_dump()), cfg.seed, self.hands_target),
        )

    # ------------------------------------------------------------------ control
    def _on_transition(self, t: Transition) -> None:
        at = datetime.fromtimestamp(t.at, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.store.write(
            "INSERT INTO events(session_id,at,from_state,to_state,command,reason,epoch,actor) VALUES (?,?,?,?,?,?,?,?)",
            (self.session_id, at, t.from_state, t.to_state, t.command, t.reason, t.epoch, t.actor),
        )
        self.store.write("UPDATE sessions SET state=? WHERE session_id=?", (t.to_state, self.session_id))

    def sync_check(self) -> tuple[bool, str]:
        """In a local simulation the engine is the authority: verify chip conservation and policy."""
        e = self._hand_engine
        if e is not None and self._expected_chips is not None and e.total_chips() != self._expected_chips:
            return False, f"fichas não conferem ({e.total_chips()} != {self._expected_chips})"
        if policy_fingerprint(self.root, self.spec) != self.policy_sha:
            return False, "a política mudou durante a sessão"
        return True, "estado da mesa e política conferidos"

    def start(self, actor: str = "usuario") -> None:
        self.ctrl.start(actor)
        self.started_at = time.time()
        self.thread = threading.Thread(target=self._run, name=f"session-{self.session_id}", daemon=True)
        self.thread.start()

    def pause(self) -> State:
        return self.ctrl.pause()

    def resume(self) -> State:
        return self.ctrl.resume(self.sync_check)

    def acknowledge_quality(self, confirm: bool, note: str) -> State:
        st = self.ctrl.acknowledge_quality_and_resume(confirm, note, self.sync_check)
        if st is State.RUNNING:
            self.quality.acknowledge_and_reset_stop()
        return st

    def emergency(self) -> State:
        return self.ctrl.emergency()

    def finish(self, mode: str = "after_hand") -> State:
        return self.ctrl.finish(mode)

    def join(self, timeout: float | None = None) -> None:
        if self.thread:
            self.thread.join(timeout)

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    # ------------------------------------------------------------------ main loop
    def _run(self) -> None:
        stack = int(round(self.cfg.stack_bb * BIG_BLIND))
        ante = int(round(self.cfg.ante_bb * BIG_BLIND))
        n = 1 + len(self.opponents)
        try:
            for h in range(self.hands_target):
                if self.ctrl.at_hand_boundary():
                    break
                if time.time() - self.started_at > self.cfg.max_minutes * 60:
                    self.ctrl.complete("limite de tempo atingido")
                    break
                self.ctrl.begin_decision()  # waits here while paused between hands; aborts on terminal states
                self._play_one(h, n, stack, ante)
            if self.ctrl.state not in (State.FINISHED, State.ERROR):
                self.ctrl.complete("limite de mãos atingido")
        except SessionAbort:
            if self.ctrl.state is State.EMERGENCY:
                self.ctrl.complete("protocolo de emergência concluído: nenhuma ação após a confirmação")
        except Exception as exc:  # noqa: BLE001 - recorded; the session ends safely
            self.error = f"{type(exc).__name__}: {exc}"
            self.quality.critical(self.error)
            self.ctrl.fail(self.error)
        finally:
            self._hand_engine = None
            self.ended_at = time.time()
            self.hero.close()
            last = self.ctrl.history[-1].reason if self.ctrl.history else None
            self.store.write(
                "UPDATE sessions SET ended_at=?, stop_reason=?, hands_played=?, summary_json=? WHERE session_id=?",
                (_now(), self.ctrl.stop_reason or self.error or last, self.hands_played, dumps(self.summary()), self.session_id),
            )

    def _play_one(self, h: int, n: int, stack: int, ante: int) -> None:
        hero_seat = (h // n) % n  # hero changes seat every n hands; the button rotates every hand
        seats: list[Agent] = list(self.opponents)
        seats.insert(hero_seat, self.hero)
        profiles = {i: a.version_label for i, a in enumerate(seats) if a is not self.hero}
        hand_id = str(uuid.uuid4())
        e = HandEngine([(a.name, stack) for a in seats], button=h % n, small_blind=BIG_BLIND // 2, big_blind=BIG_BLIND,
                       ante=ante, seed=derive_seed(self.cfg.seed, "lab_hand", h), hand_id=hand_id)
        self._hand_engine, self._expected_chips = e, e.total_chips()
        self.current_hand = h + 1
        self.store.write(
            "INSERT INTO hands(hand_id,session_id,hand_no,button,hero_seat,stack_bb,big_blind,opponents_json,started_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (hand_id, self.session_id, h + 1, h % n, hero_seat, self.cfg.stack_bb, BIG_BLIND,
             dumps({str(k): v for k, v in profiles.items()}), _now()),
        )
        try:
            rec = play_hand(e, seats, latency_budget_ms=1e12, on_decision=lambda d: self._on_decision(d, hero_seat))
        except SessionAbort:
            with self._lock:
                self.hands_aborted += 1
            self.store.write("UPDATE hands SET aborted=1, ended_at=? WHERE hand_id=?", (_now(), hand_id))
            raise
        self._finish_hand(rec, hero_seat, profiles)

    def _on_decision(self, d: DecisionRecord, hero_seat: int) -> None:
        if d.seat != hero_seat:
            return
        try:
            info = dict(d.info)
            issue = d.issue or info.get("issue")
            obs = self.hero.last_obs
            if issue:
                a = technical(issue)
            elif obs is None or obs.hand_id != d.hand_id:
                a = technical("observação de decisão ausente")
            else:
                a = self.reference.assess(obs, Action.from_dict(d.applied))
            q = self.quality.record(a.label, issue)
            with self._lock:
                self.labels[a.label] += 1
                if a.ev_gap_bb is not None and a.label != INCONCLUSIVE:
                    self.ev_gaps.append(a.ev_gap_bb)
                self.recent = ([{"hand": self.current_hand, "street": d.street, "position": d.position,
                                 "action": d.applied, "label": a.label, "reason": a.reason}] + self.recent)[:15]
            self.store.write(
                "INSERT INTO decisions(decision_id,session_id,hand_id,seq,street,position,observation_json,legal_json,"
                "requested_json,applied_json,valid,issue,latency_ms,info_json,epoch,label,assessment_json,quality_json,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (d.decision_id, self.session_id, d.hand_id, d.seq_in_hand, d.street, d.position, dumps(d.observation),
                 dumps(d.legal), dumps(d.requested), dumps(d.applied), int(issue is None), issue, d.latency_ms, dumps(info),
                 self.ctrl.epoch, a.label, dumps(a.as_dict()), dumps(q.as_dict()), _now()),
            )
            if q.stop:
                self.ctrl.quality_stop(q.stop_reason or "parada por qualidade")
        finally:
            self.ctrl.end_commit()

    def _finish_hand(self, rec: HandRecord, hero_seat: int, profiles: dict[int, str]) -> None:
        r = rec.result
        net = r.net[hero_seat] / BIG_BLIND
        vp = sorted(vpip_seats(rec) - {hero_seat})
        hero_vpip = hero_seat in vpip_seats(rec)
        pos = next((d.position for d in rec.decisions if d.seat == hero_seat), None) or "sem_decisao"
        with self._lock:
            self.hands_played += 1
            self.net_bb.append(net)
            self.by_position[pos].append(net)
            if hero_vpip and len(vp) == 1:
                self.by_opponent[profiles[vp[0]]].append(net)
            elif hero_vpip and len(vp) > 1:
                self.by_opponent["multiway"].append(net)
        self.store.write(
            "UPDATE hands SET hero_position=?, net_bb=?, final_street=?, showdown=?, vpip_opponents_json=?, ended_at=?"
            " WHERE hand_id=?",
            (pos, net, r.final_street.label, int(hero_seat in r.showdown_seats), dumps([profiles[s] for s in vp]), _now(),
             rec.hand_id),
        )
        # revealed AFTER the hand: showdown cards and the hero's own cards (never fed back to decisions)
        for s in sorted(set(r.showdown_seats) | {hero_seat}):
            self.store.write(
                "INSERT OR IGNORE INTO revealed(hand_id,seat,profile,cards_json) VALUES (?,?,?,?)",
                (rec.hand_id, s, profiles.get(s, "hero"), dumps(cards_to_str(rec.engine.hole_cards_offline(s)))),
            )
        self._hand_engine = None

    # ------------------------------------------------------------------ progress / metrics
    def summary(self) -> dict[str, Any]:
        with self._lock:
            evaluable = sum(v for k, v in self.labels.items() if k != INCONCLUSIVE)
            return {
                "hands_played": self.hands_played,
                "hands_aborted": self.hands_aborted,
                "bb_per_100": per100(mean_ci(self.net_bb)),
                "net_bb_total": round(sum(self.net_bb), 2),
                "by_position": {k: per100(mean_ci(v)) for k, v in sorted(self.by_position.items())},
                "by_opponent": {k: per100(mean_ci(v)) for k, v in sorted(self.by_opponent.items())},
                "labels": dict(self.labels),
                "decisions": sum(self.labels.values()),
                "evaluable": evaluable,
                "ev_loss_bb": {"n": len(self.ev_gaps),
                               "mean": round(sum(self.ev_gaps) / len(self.ev_gaps), 4) if self.ev_gaps else None,
                               "total": round(sum(self.ev_gaps), 3)},
                "notes": [
                    "bb/100 de uma sessão curta tem variância enorme; leia o intervalo, não a média",
                    "EV estimado só existe para spots heads-up de push/fold com referência validada",
                    "a meta de 75% de decisões adequadas é operacional e experimental, não garantia de lucro",
                ],
            }

    def status(self) -> dict[str, Any]:
        elapsed = ((self.ended_at or time.time()) - self.started_at) if self.started_at else 0.0
        q = self.quality.state(evaluate=False).as_dict()
        with self._lock:
            recent = list(self.recent)
        return {
            "session_id": self.session_id, "kind": "simulacao", "policy": POLICY_LABEL, "policy_sha256": self.policy_sha,
            "control": self.ctrl.snapshot(), "hands_target": self.hands_target, "current_hand": self.current_hand,
            "elapsed_s": round(elapsed, 1), "config": self.cfg.model_dump(), "quality": q, "summary": self.summary(),
            "recent_decisions": recent, "error": self.error, "running": self.running,
            "history": [t.as_dict() for t in self.ctrl.history[-20:]],
        }
