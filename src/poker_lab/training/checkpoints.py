"""Versioned JSON checkpoints (never pickle: loading a checkpoint cannot execute code).

A checkpoint is ``<name>.json`` plus a ``<name>.json.meta.json`` sidecar holding its
sha256. Loading verifies the checksum and validates the structure before use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from poker_lab.util import code_version, file_sha256, now_iso

FORMAT = "poker_lab.checkpoint.v1"
SCHEMA_VERSION = 1


class PushFoldPolicy(BaseModel):
    """Per stack depth: probability to shove (SB) and to call a shove (BB) per class."""

    stacks_bb: list[float]
    sb_push: dict[str, dict[str, float]]  # str(stack) -> class -> prob
    bb_call: dict[str, dict[str, float]]

    @field_validator("sb_push", "bb_call")
    @classmethod
    def _probs(cls, v: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        for table in v.values():
            if len(table) != 169:
                raise ValueError("each stack needs 169 classes")
            if any(not 0.0 <= p <= 1.0 for p in table.values()):
                raise ValueError("probabilities must be within [0, 1]")
        return v


class Checkpoint(BaseModel):
    format: str = FORMAT
    schema_version: int = SCHEMA_VERSION
    algorithm: str
    game: str
    seed: int
    iterations: dict[str, int]
    config: dict[str, Any] = Field(default_factory=dict)
    code_version: str = Field(default_factory=code_version)
    created_at: str = Field(default_factory=now_iso)
    metrics: dict[str, Any] = Field(default_factory=dict)
    policy: PushFoldPolicy
    solver_state: dict[str, Any] = Field(default_factory=dict)  # regrets/strategy sums for resume
    parent_sha256: str | None = None

    @field_validator("format")
    @classmethod
    def _fmt(cls, v: str) -> str:
        if v != FORMAT:
            raise ValueError(f"unsupported checkpoint format {v!r}")
        return v


def save_checkpoint(ckpt: Checkpoint, path: str | Path) -> dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(ckpt.model_dump_json())
    tmp.replace(p)  # atomic on POSIX
    meta = {"sha256": file_sha256(p), "size_bytes": p.stat().st_size, "format": FORMAT, "saved_at": now_iso()}
    Path(str(p) + ".meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def load_checkpoint_meta(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    meta_p = Path(str(p) + ".meta.json")
    if not meta_p.exists():
        raise FileNotFoundError(f"missing checkpoint metadata {meta_p}")
    meta: dict[str, Any] = json.loads(meta_p.read_text())
    actual = file_sha256(p)
    if actual != meta.get("sha256"):
        raise ValueError(f"checkpoint checksum mismatch for {p}")
    return meta


def load_checkpoint(path: str | Path) -> Checkpoint:
    load_checkpoint_meta(path)
    return Checkpoint.model_validate_json(Path(path).read_text())
