"""Retention policy.

Raw, high-volume rows (``action_events`` and ``offline_hole_cards``) of hands older than
``older_than_days`` are deleted unless a note references the hand or one of its decisions.
Hands, per-seat results, decisions, explanations and aggregates are kept, so KPIs and the
Power BI model stay reproducible; only the detailed replay is lost.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from poker_lab.persistence.db import transaction

_PROTECTED = """
    SELECT h.hand_id FROM hands h
    WHERE h.completed_at < :cutoff
      AND NOT EXISTS (SELECT 1 FROM notes n WHERE n.hand_id = h.hand_id)
      AND NOT EXISTS (SELECT 1 FROM notes n JOIN decisions d ON d.decision_id = n.decision_id WHERE d.hand_id = h.hand_id)
"""


def prune(conn: sqlite3.Connection, older_than_days: int, now: datetime | None = None) -> dict[str, int]:
    if older_than_days < 0:
        raise ValueError("older_than_days must be >= 0")
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=older_than_days)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with transaction(conn):
        ev = conn.execute(f"DELETE FROM action_events WHERE hand_id IN ({_PROTECTED})", {"cutoff": cutoff}).rowcount  # noqa: S608
        hc = conn.execute(f"DELETE FROM offline_hole_cards WHERE hand_id IN ({_PROTECTED})", {"cutoff": cutoff}).rowcount  # noqa: S608
    return {"action_events_deleted": ev, "offline_hole_cards_deleted": hc}
