"""Safe migration procedure: verified backup -> migrate -> verify -> automatic restore on failure.

Steps (see docs/MIGRATIONS.md):
1. Pre-checks on the live DB: ``PRAGMA integrity_check`` == ok, ``foreign_key_check`` empty.
2. Online backup with the SQLite backup API to ``<backup_dir>/<db>.v<old>.<timestamp>.db``.
3. Verify the backup: integrity ok and identical row counts for every table; write a
   manifest JSON with counts, schema version and the backup file sha256.
4. Apply pending migrations (each in its own transaction).
5. Post-checks: integrity ok, FK check empty, and every pre-existing table still has at
   least the same number of rows (migrations are additive; backfills may only add).
6. On any failure: restore the backup file over the database and verify the restore
   against the manifest, then raise :class:`MigrationFailed`.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poker_lab.persistence.db import connect, file_sha256, migrate, pending_migrations, schema_version


class MigrationFailed(RuntimeError):
    def __init__(self, message: str, restored: bool, backup_path: Path | None) -> None:
        super().__init__(message)
        self.restored = restored
        self.backup_path = backup_path


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    ]
    return {n: int(conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]) for n in names}  # noqa: S608


def check_health(conn: sqlite3.Connection) -> list[str]:
    problems = []
    ic = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if ic != "ok":
        problems.append(f"integrity_check: {ic}")
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"foreign_key_check: {len(fk)} violations")
    return problems


def make_verified_backup(conn: sqlite3.Connection, db_path: Path, backup_dir: Path) -> tuple[Path, dict[str, Any]]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ver = schema_version(conn) if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='schema_migrations'"
    ).fetchone() else 0
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    dest = backup_dir / f"{db_path.stem}.v{ver}.{ts}.db"
    target = sqlite3.connect(str(dest))
    with target:
        conn.backup(target)
    target.close()
    src_counts = table_counts(conn)
    b = sqlite3.connect(str(dest))
    try:
        if b.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("backup integrity check failed")
        b_counts = table_counts(b)
    finally:
        b.close()
    if b_counts != src_counts:
        raise RuntimeError(f"backup row counts differ: {b_counts} != {src_counts}")
    manifest = {
        "database": str(db_path),
        "backup": str(dest),
        "schema_version": ver,
        "sha256": file_sha256(dest),
        "table_counts": src_counts,
        "created_at": ts,
    }
    Path(str(dest) + ".manifest.json").write_text(json.dumps(manifest, indent=1))
    return dest, manifest


def restore_backup(backup_path: Path, db_path: Path) -> None:
    """Recovery procedure: verify the backup against its manifest and copy it over the DB."""
    manifest = json.loads(Path(str(backup_path) + ".manifest.json").read_text())
    if file_sha256(backup_path) != manifest["sha256"]:
        raise RuntimeError("backup checksum does not match its manifest; refusing to restore")
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()
    shutil.copyfile(backup_path, db_path)
    c = sqlite3.connect(str(db_path))
    try:
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or table_counts(c) != manifest["table_counts"]:
            raise RuntimeError("restored database does not match the backup manifest")
    finally:
        c.close()


def safe_migrate(db_path: str | Path, backup_dir: str | Path | None = None, target: int | None = None) -> dict[str, Any]:
    db_path = Path(db_path)
    backup_dir = Path(backup_dir) if backup_dir else db_path.parent / "backups"
    fresh = not db_path.exists()
    conn = connect(db_path)
    pending = pending_migrations(conn)
    if target is not None:
        pending = [p for p in pending if int(p.split("_", 1)[0]) <= target]
    if not pending:
        conn.close()
        return {"applied": [], "backup": None, "fresh": fresh}
    if fresh or table_counts(conn).keys() <= {"schema_migrations"}:
        applied = migrate(conn, target)
        problems = check_health(conn)
        conn.close()
        if problems:
            raise MigrationFailed("; ".join(problems), restored=False, backup_path=None)
        return {"applied": applied, "backup": None, "fresh": True}
    problems = check_health(conn)
    if problems:
        conn.close()
        raise MigrationFailed("pre-migration health check failed: " + "; ".join(problems), restored=False, backup_path=None)
    backup_path, manifest = make_verified_backup(conn, db_path, backup_dir)
    before = manifest["table_counts"]
    try:
        applied = migrate(conn, target)
        problems = check_health(conn)
        after = table_counts(conn)
        shrunk = {t: (n, after.get(t)) for t, n in before.items() if after.get(t, -1) < n}
        if shrunk:
            problems.append(f"rows lost in {shrunk}")
        if problems:
            raise RuntimeError("; ".join(problems))
    except Exception as exc:
        conn.close()
        restore_backup(backup_path, db_path)
        raise MigrationFailed(f"migration failed and backup was restored: {exc}", restored=True, backup_path=backup_path) from exc
    conn.close()
    return {"applied": applied, "backup": str(backup_path), "manifest": manifest, "fresh": False}
