"""Read-only view of the Open Poker integration for the local app (P9-E).

The app NEVER starts an online session, never reads the API key and never opens a socket.
Online sessions are started only by the user, by hand, with ``run_openpoker.ps1`` (virtual chips,
key typed without echo and kept only in that process). Here we only report whether the
integration is installed, whether the kill switch is set, and list recorded online sessions
read-only from ``artifacts/openpoker/online.db``.
"""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path
from typing import Any

ONLINE_DB = "artifacts/openpoker/online.db"
KILL_SWITCH = "artifacts/openpoker/STOP"


def online_status(root: Path) -> dict[str, Any]:
    installed = importlib.util.find_spec("poker_lab.integrations.openpoker") is not None
    ws = importlib.util.find_spec("websockets") is not None
    return {
        "enabled": False,  # the app never enables or starts it
        "status": "desativada na aplicação",
        "integration_installed": installed,
        "websockets_installed": ws,
        "kill_switch_set": (root / KILL_SWITCH).exists(),
        "money": "somente fichas virtuais",
        "how_to_start": "manual, pelo usuário: .\\run_openpoker.ps1 -MaxHands 30 -BuyIn 2000 (a chave é digitada sem eco "
                        "e nunca é gravada). Parar: .\\stop_openpoker.bat ou Ctrl+C.",
        "doc": "docs/P11_OPENPOKER.md",
    }


def list_online_sessions(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    db = root / ONLINE_DB
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT s.session_id, s.agent_label, s.money, s.started_at, s.ended_at, s.stop_reason,"
            " (SELECT COUNT(*) FROM online_hands h WHERE h.session_id = s.session_id) AS hands,"
            " (SELECT COALESCE(SUM(net_chips), 0) FROM online_hands h WHERE h.session_id = s.session_id) AS net_chips"
            " FROM online_sessions s ORDER BY s.started_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []
    finally:
        conn.close()
