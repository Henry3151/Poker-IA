"""Records online sessions in a SEPARATE SQLite file (default artifacts/openpoker/online.db).

The main lab database and its migrations are untouched. No secret is ever stored: only the
agent label, checkpoint hashes, public events, own decisions and platform responses.
Export: :func:`export_jsonl` writes hands/decisions for the existing analysis tooling.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from poker_lab.util import code_version, dumps, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS online_sessions (
    session_id TEXT PRIMARY KEY, platform TEXT NOT NULL, agent_label TEXT NOT NULL, agent_config_json TEXT NOT NULL,
    code_version TEXT NOT NULL, money TEXT NOT NULL CHECK (money = 'virtual_chips'), started_at TEXT NOT NULL,
    ended_at TEXT, stats_json TEXT, stop_reason TEXT
);
CREATE TABLE IF NOT EXISTS online_hands (
    session_id TEXT NOT NULL REFERENCES online_sessions(session_id), hand_id TEXT NOT NULL, table_id TEXT,
    my_seat INTEGER, dealer_seat INTEGER, small_blind INTEGER, big_blind INTEGER, players INTEGER,
    start_stack INTEGER, end_stack INTEGER, net_chips INTEGER, result_json TEXT, started_at TEXT, ended_at TEXT,
    PRIMARY KEY (session_id, hand_id)
);
CREATE TABLE IF NOT EXISTS online_decisions (
    decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES online_sessions(session_id), hand_id TEXT,
    turn_token_hash TEXT, observation_json TEXT, valid_actions_json TEXT NOT NULL, requested_json TEXT,
    sent_json TEXT NOT NULL, status TEXT NOT NULL, ack_status TEXT, latency_ms REAL, agent_info_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS online_rejections (
    session_id TEXT NOT NULL, code TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS online_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, note TEXT);
"""
ONLINE_SCHEMA_VERSION = 1


def token_digest(token: str) -> str:
    """One-way digest of a single-use turn_token (the raw token is never stored)."""
    return "sha256:" + hashlib.sha256(token.encode()).hexdigest()[:32]


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if "turn_token" in out:
        out["turn_token"] = token_digest(str(out["turn_token"]))
    return out


class OnlineRecorder:
    def __init__(self, db_path: str | Path, agent_label: str, agent_config: dict[str, Any]) -> None:
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(p), isolation_level=None)
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT OR IGNORE INTO online_schema_version(version,applied_at,note) VALUES (?,?,?)",
            (ONLINE_SCHEMA_VERSION, now_iso(), "P11 online DB, separate from the simulator DB; no auth tokens stored"),
        )
        self.session_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO online_sessions(session_id,platform,agent_label,agent_config_json,code_version,money,started_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.session_id, "openpoker", agent_label, dumps(agent_config), code_version(), "virtual_chips", now_iso()),
        )
        self._hand_start: dict[str, int] = {}
        self._cid_to_decision: dict[str, str] = {}

    def hand_started(self, msg: Any, tracker: Any) -> None:
        me = tracker.seats.get(tracker.my_seat)
        start = (me.stack + me.total_commit) if me else None
        self._hand_start[msg.hand_id] = start or 0
        self.conn.execute(
            "INSERT OR IGNORE INTO online_hands(session_id,hand_id,table_id,my_seat,dealer_seat,small_blind,big_blind,players,"
            "start_stack,started_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.session_id, msg.hand_id, tracker.table_id, tracker.my_seat, tracker.dealer, tracker.sb, tracker.bb,
             len(tracker.seats), start, now_iso()),
        )

    def hand_finished(self, msg: Any, tracker: Any) -> None:
        hid = msg.hand_id
        end = msg.final_stacks.get(str(tracker.my_seat))
        start = self._hand_start.get(hid or "")
        public = {"winners": msg.winners, "pot": msg.pot, "final_stacks": msg.final_stacks, "shown_cards": msg.shown_cards}
        self.conn.execute(
            "UPDATE online_hands SET end_stack=?, net_chips=?, result_json=?, ended_at=? WHERE session_id=? AND hand_id=?",
            (end, (end - start) if end is not None and start is not None else None, dumps(public), now_iso(), self.session_id, hid),
        )

    def decision(self, turn: Any, obs: Any, payload: dict[str, Any], status: str, latency_ms: float, requested: Any, info: Any) -> None:
        did = str(uuid.uuid4())
        self._cid_to_decision[payload["client_action_id"]] = did
        self.conn.execute(
            "INSERT INTO online_decisions(decision_id,session_id,hand_id,turn_token_hash,observation_json,valid_actions_json,"
            "requested_json,sent_json,status,latency_ms,agent_info_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                did, self.session_id, turn.hand_id, token_digest(turn.turn_token),
                dumps(obs.to_dict()) if obs is not None else None,
                dumps([v.model_dump() for v in turn.valid_actions]),
                dumps(requested.to_dict()) if requested is not None and hasattr(requested, "to_dict") else None,
                dumps(redact_payload(payload)), status, round(latency_ms, 3), dumps(info or {}), now_iso(),
            ),
        )

    def ack(self, client_action_id: str, status: str) -> None:
        did = self._cid_to_decision.get(client_action_id)
        if did:
            self.conn.execute("UPDATE online_decisions SET ack_status=? WHERE decision_id=?", (status, did))

    def rejected(self, code: str, reason: str) -> None:
        self.conn.execute(
            "INSERT INTO online_rejections(session_id,code,reason,created_at) VALUES (?,?,?,?)", (self.session_id, code, reason, now_iso())
        )

    def close_session(self, stats: Any) -> None:
        self.conn.execute(
            "UPDATE online_sessions SET ended_at=?, stats_json=?, stop_reason=? WHERE session_id=?",
            (now_iso(), dumps(stats.__dict__), stats.stop_reason, self.session_id),
        )


def export_jsonl(db_path: str | Path, out_dir: str | Path) -> dict[str, int]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    counts = {}
    for table in ("online_sessions", "online_hands", "online_decisions", "online_rejections"):
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]  # noqa: S608
        (out / f"{table}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        counts[table] = len(rows)
    return counts
