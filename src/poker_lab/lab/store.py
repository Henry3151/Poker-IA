"""Storage for lab sessions (P9-C): a NEW database ``artifacts/lab/sessions.db``.

It never touches the evaluation databases. Decision-time data and post-hand revelations live in
separate tables (``decisions`` vs ``revealed``) so analysis can prove which information existed
when each decision was taken. No secrets are ever stored.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('simulacao')), created_at TEXT NOT NULL,
  ended_at TEXT, state TEXT NOT NULL, stop_reason TEXT, policy_label TEXT NOT NULL, policy_sha256 TEXT NOT NULL,
  config_json TEXT NOT NULL, seed INTEGER NOT NULL, hands_target INTEGER NOT NULL, hands_played INTEGER NOT NULL DEFAULT 0,
  summary_json TEXT
);
CREATE TABLE IF NOT EXISTS hands (
  hand_id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(session_id), hand_no INTEGER NOT NULL,
  button INTEGER NOT NULL, hero_seat INTEGER NOT NULL, hero_position TEXT, stack_bb REAL NOT NULL, big_blind INTEGER NOT NULL,
  net_bb REAL, final_street TEXT, showdown INTEGER, aborted INTEGER NOT NULL DEFAULT 0,
  opponents_json TEXT NOT NULL, vpip_opponents_json TEXT, started_at TEXT NOT NULL, ended_at TEXT
);
CREATE INDEX IF NOT EXISTS hands_session ON hands(session_id, hand_no);
CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, hand_id TEXT NOT NULL, seq INTEGER NOT NULL,
  street TEXT, position TEXT, observation_json TEXT NOT NULL, legal_json TEXT NOT NULL, requested_json TEXT,
  applied_json TEXT NOT NULL, valid INTEGER NOT NULL, issue TEXT, latency_ms REAL, info_json TEXT,
  epoch INTEGER, label TEXT NOT NULL, assessment_json TEXT NOT NULL, quality_json TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS decisions_hand ON decisions(hand_id, seq);
CREATE TABLE IF NOT EXISTS revealed (
  hand_id TEXT NOT NULL, seat INTEGER NOT NULL, profile TEXT, cards_json TEXT NOT NULL,
  revealed_after_hand INTEGER NOT NULL DEFAULT 1 CHECK (revealed_after_hand = 1), PRIMARY KEY (hand_id, seat)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, at TEXT NOT NULL, from_state TEXT, to_state TEXT,
  command TEXT NOT NULL, reason TEXT, epoch INTEGER, actor TEXT
);
"""


def dumps(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"), default=str)


class SessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.execute("INSERT OR IGNORE INTO schema_version VALUES (?, datetime('now'))", (SCHEMA_VERSION,))

    def close(self) -> None:
        self.conn.close()

    def write(self, sql: str, params: tuple[Any, ...]) -> None:
        with self._lock:
            self.conn.execute(sql, params)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]


def open_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
