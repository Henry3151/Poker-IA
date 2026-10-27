"""Dependency-free helpers shared by all layers (time, versions, hashing, JSON)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poker_lab import __version__


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def code_version() -> str:
    """Package version plus git commit when available (never fails)."""
    try:
        here = Path(__file__).resolve().parent
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=2, cwd=here).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, timeout=2, cwd=here
        ).stdout.strip()
        if sha:
            return f"{__version__}+g{sha}{'.dirty' if dirty else ''}"
    except (OSError, subprocess.SubprocessError):
        pass
    return __version__


def dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str)


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
