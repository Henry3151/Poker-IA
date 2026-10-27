"""SQLite connection management and a small, checksum-verified migration runner."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from poker_lab.util import code_version, dumps, file_sha256, now_iso

__all__ = ["code_version", "dumps", "file_sha256", "now_iso"]


def connect(path: str | Path) -> sqlite3.Connection:
    p = str(path)
    if p != ":memory:":
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, isolation_level=None, check_same_thread=False)  # autocommit; explicit transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if p != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _migration_files() -> list[tuple[int, str, str]]:
    root = resources.files("poker_lab.persistence").joinpath("migrations")
    out = []
    for f in root.iterdir():
        if f.name.endswith(".sql"):
            version = int(f.name.split("_", 1)[0])
            out.append((version, f.name, f.read_text(encoding="utf-8")))
    return sorted(out)


class MigrationError(RuntimeError):
    pass


def pending_migrations(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    return [name for version, name, _ in _migration_files() if version not in applied]


def migrate(conn: sqlite3.Connection, target: int | None = None) -> list[str]:
    """Apply pending migrations up to ``target`` (default: all); verify checksums of applied ones."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {r["version"]: r for r in conn.execute("SELECT * FROM schema_migrations")}
    done: list[str] = []
    for version, name, sql in _migration_files():
        if target is not None and version > target:
            break
        checksum = hashlib.sha256(sql.encode()).hexdigest()
        if version in applied:
            if applied[version]["checksum"] != checksum:
                raise MigrationError(f"migration {name} changed after being applied")
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            for stmt in _split_sql(sql):
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?,?,?,?)",
                (version, name, checksum, now_iso()),
            )
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        done.append(name)
    return done


def _split_sql(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(row["v"] or 0)


def open_db(path: str | Path) -> sqlite3.Connection:
    conn = connect(path)
    migrate(conn)
    return conn


def backup(conn: sqlite3.Connection, dest: str | Path) -> Path:
    d = Path(dest)
    d.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(str(d))
    with target:
        conn.backup(target)
    target.close()
    return d
