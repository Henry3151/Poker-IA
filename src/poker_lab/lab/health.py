"""Environment and data health checks for the home screen (read-only, fast)."""

from __future__ import annotations

import importlib
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from poker_lab.lab.frozen import MANIFEST, verify_manifest
from poker_lab.lab.registry import KNOWN_RUNS, run_overview

REQUIRED = ("pydantic", "typer", "pyarrow", "fastapi", "uvicorn")
OPTIONAL = {"websockets": "integração online (etapa E)", "matplotlib": "gráficos do README"}


def _version(mod: str) -> str | None:
    try:
        m = importlib.import_module(mod)
    except Exception:  # noqa: BLE001
        return None
    return str(getattr(m, "__version__", "ok"))


def environment() -> dict[str, Any]:
    deps = {m: _version(m) for m in REQUIRED}
    opt = {m: {"version": _version(m), "used_for": why} for m, why in OPTIONAL.items()}
    return {
        "python": sys.version.split()[0], "python_ok": sys.version_info >= (3, 12),
        "platform": platform.platform(), "dependencies": deps, "dependencies_ok": all(deps.values()),
        "optional": opt,
    }


def check_all(root: Path) -> dict[str, Any]:
    env = environment()
    frozen = verify_manifest(root).as_dict() if (root / MANIFEST).is_file() else {"passed": False, "error": "manifest ausente"}
    runs = []
    for r in KNOWN_RUNS:
        try:
            ov = run_overview(r, root)
            ov["count_ok"] = ov["tournaments"] == ov.get("expected_tournaments") if ov["db_present"] else None
        except Exception as exc:  # noqa: BLE001
            ov = {"key": r.key, "error": f"{type(exc).__name__}: {exc}"}
        runs.append(ov)
    free = shutil.disk_usage(root).free
    return {
        "environment": env,
        "frozen": frozen,
        "runs": runs,
        "disk_free_gb": round(free / 1e9, 1),
        "online": {"enabled": False, "status": "desativada", "reason": "integração online só na etapa E, após aprovação"},
        "ok": bool(env["python_ok"] and env["dependencies_ok"] and frozen.get("passed")),
    }
