"""One active local simulation at a time + read access to the session history (P9-C)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from poker_lab.lab.control import State, TransitionRefused
from poker_lab.lab.session import SimConfig, SimulationSession
from poker_lab.lab.store import SessionStore

SESSIONS_DB = "artifacts/lab/sessions.db"
MAX_HANDS_PER_SESSION = 20_000


class SessionBusy(RuntimeError):
    pass


def _loads(v: str | None) -> Any:
    return json.loads(v) if v else None


class SessionManager:
    def __init__(self, root: Path, db_path: Path | None = None) -> None:
        self.root = root
        self.db_path = db_path or root / SESSIONS_DB
        self._store: SessionStore | None = None
        self.current: SimulationSession | None = None
        self._lock = threading.Lock()

    @property
    def store(self) -> SessionStore:
        if self._store is None:
            self._store = SessionStore(self.db_path)
        return self._store

    def close(self) -> None:
        if self.current and self.current.running:
            self.current.emergency()
            self.current.join(5)
        if self._store:
            self._store.close()

    # ------------------------------------------------------------------ control
    def start(self, cfg: SimConfig) -> SimulationSession:
        with self._lock:
            if self.current is not None and self.current.running:
                raise SessionBusy("já existe uma sessão em andamento")
            s = SimulationSession(self.root, self.store, cfg, hand_limit=MAX_HANDS_PER_SESSION)
            s.start()
            self.current = s
            return s

    def require(self, session_id: str | None = None) -> SimulationSession:
        s = self.current
        if s is None or (session_id and s.session_id != session_id):
            raise TransitionRefused("nenhuma sessão ativa com esse identificador")
        return s

    def command(self, cmd: str, **kw: Any) -> State:
        s = self.require(kw.pop("session_id", None))
        if cmd == "pause":
            st = s.pause()
            s.ctrl.wait_paused(5)
            return s.ctrl.state if st is State.PAUSING else st
        if cmd == "resume":
            return s.resume()
        if cmd == "emergency":
            return s.emergency()
        if cmd == "finish":
            mode = kw.get("mode", "after_hand")
            if mode not in ("after_hand", "now"):
                raise TransitionRefused("modo de encerramento inválido")
            return s.finish(mode)
        if cmd == "ack_quality":
            return s.acknowledge_quality(bool(kw.get("confirm")), str(kw.get("note", "")))
        raise TransitionRefused(f"comando desconhecido: {cmd}")

    def agent_state(self) -> str:
        s = self.current
        if s is None:
            return "desconectado"
        return s.ctrl.state.value

    # ------------------------------------------------------------------ history (read)
    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.store.query(
            "SELECT session_id,kind,created_at,ended_at,state,stop_reason,policy_label,seed,hands_target,hands_played,summary_json"
            " FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            summ = _loads(r.pop("summary_json")) or {}
            r["bb_per_100"] = summ.get("bb_per_100")
            r["labels"] = summ.get("labels")
            out.append(r)
        return out

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        live = self.current.status() if self.current and self.current.session_id == session_id else None
        rows = self.store.query("SELECT * FROM sessions WHERE session_id=?", (session_id,))
        if not rows:
            return None
        r = rows[0]
        r["config"] = _loads(r.pop("config_json"))
        r["summary"] = _loads(r.pop("summary_json"))
        r["events"] = self.store.query(
            "SELECT at,from_state,to_state,command,reason,epoch,actor FROM events WHERE session_id=? ORDER BY id", (session_id,))
        r["live"] = live
        return r

    def list_hands(self, session_id: str, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.store.query(
            "SELECT h.hand_id,h.hand_no,h.hero_position,h.net_bb,h.final_street,h.showdown,h.aborted,h.vpip_opponents_json,"
            " (SELECT COUNT(*) FROM decisions d WHERE d.hand_id=h.hand_id) AS n_decisions,"
            " (SELECT GROUP_CONCAT(d.label) FROM decisions d WHERE d.hand_id=h.hand_id) AS labels"
            " FROM hands h WHERE h.session_id=? ORDER BY h.hand_no LIMIT ? OFFSET ?",
            (session_id, max(1, min(limit, 500)), max(0, offset)))
        for r in rows:
            r["vpip_opponents"] = _loads(r.pop("vpip_opponents_json")) or []
            r["labels"] = (r["labels"] or "").split(",") if r["labels"] else []
        return rows

    def analysis(self, session_id: str) -> dict[str, Any] | None:
        from poker_lab.lab.analysis import analyze_session

        return analyze_session(self.store, session_id)

    def get_hand(self, hand_id: str) -> dict[str, Any] | None:
        rows = self.store.query("SELECT * FROM hands WHERE hand_id=?", (hand_id,))
        if not rows:
            return None
        h = rows[0]
        h["opponents"] = _loads(h.pop("opponents_json"))
        h["vpip_opponents"] = _loads(h.pop("vpip_opponents_json"))
        decisions = []
        for d in self.store.query("SELECT * FROM decisions WHERE hand_id=? ORDER BY seq", (hand_id,)):
            decisions.append({
                "seq": d["seq"], "street": d["street"], "position": d["position"], "epoch": d["epoch"],
                "observation": _loads(d["observation_json"]), "legal": _loads(d["legal_json"]),
                "requested": _loads(d["requested_json"]), "applied": _loads(d["applied_json"]), "valid": bool(d["valid"]),
                "issue": d["issue"], "latency_ms": d["latency_ms"], "label": d["label"],
                "assessment": _loads(d["assessment_json"]), "quality": _loads(d["quality_json"]),
            })
        revealed = [{"seat": r["seat"], "profile": r["profile"], "cards": _loads(r["cards_json"])}
                    for r in self.store.query("SELECT * FROM revealed WHERE hand_id=? ORDER BY seat", (hand_id,))]
        return {"hand": h, "decision_time": decisions, "revealed_after_hand": revealed,
                "note": "as cartas reveladas só ficaram conhecidas depois da mão e não foram usadas para julgar decisões"}
