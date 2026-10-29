"""Lab settings: limits and parameters, validated, stored WITHOUT secrets.

Stored in ``artifacts/lab/config.json`` (git-ignored). Any key that looks like a secret is
rejected, so an API key can never end up in this file. The online integration flag is
read-only in this stage and always reported as disabled.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SECRET_HINT = re.compile(r"(key|token|secret|password|passwd|senha|credential|bearer|auth)", re.I)


class SimulationLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_tournaments_per_job: int = Field(default=200, ge=1, le=2000)
    max_hands_per_session: int = Field(default=2000, ge=10, le=100_000)
    max_job_minutes: int = Field(default=120, ge=1, le=1440)
    concurrent_jobs: int = Field(default=1, ge=1, le=1)  # one heavy job at a time (keeps the PC usable)
    low_priority: bool = True


class OnlineLimits(BaseModel):
    """Prepared for stage E; NOT active. No connection is possible in stage B."""

    model_config = ConfigDict(extra="forbid")
    max_hands: int = Field(default=30, ge=1, le=1000)
    max_minutes: int = Field(default=30, ge=1, le=480)
    buy_in: int = Field(default=2000, ge=1000, le=5000)
    decision_budget_s: float = Field(default=10.0, gt=0, lt=40)
    resume_safety_margin_s: float = Field(default=5.0, ge=1, le=30)


class LabSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulation: SimulationLimits = SimulationLimits()
    online: OnlineLimits = OnlineLimits()
    default_run: str = Field(default="P7c", pattern=r"^[A-Za-z0-9_-]{1,32}$")


def _reject_secrets(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if SECRET_HINT.search(str(k)):
                raise ValueError(f"campo não permitido (parece um segredo): {path}{k}")
            _reject_secrets(v, f"{path}{k}.")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _reject_secrets(v, f"{path}{i}.")


def settings_path(root: Path) -> Path:
    return root / "artifacts/lab/config.json"


def load_settings(root: Path) -> LabSettings:
    p = settings_path(root)
    if not p.is_file():
        return LabSettings()
    data = json.loads(p.read_text(encoding="utf-8"))
    _reject_secrets(data)
    return LabSettings.model_validate(data)


def save_settings(root: Path, data: dict[str, Any]) -> LabSettings:
    _reject_secrets(data)
    s = LabSettings.model_validate(data)
    p = settings_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s.model_dump(), indent=1), encoding="utf-8")
    tmp.replace(p)
    return s
