"""Read-only SQLite access for frozen evaluation databases.

Never use ``persistence.db.open_db`` on a frozen database: it applies migrations and switches the
journal mode. ``connect_ro`` opens with ``mode=ro`` (no writes, no migrations, no checkpoints).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseNotFound(FileNotFoundError):
    pass


def connect_ro(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    if not p.is_file():
        raise DatabaseNotFound(str(p))
    conn = sqlite3.connect(f"file:{p.resolve().as_posix()}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    except sqlite3.DatabaseError:
        return 0
    return int(row[0] or 0)
