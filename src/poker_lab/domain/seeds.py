"""Deterministic seed derivation: every random stream is derived from one root seed."""

from __future__ import annotations

import hashlib

MAX_SEED = 2**63 - 1  # fits a signed SQLite INTEGER


def derive_seed(root: int, *keys: object) -> int:
    h = hashlib.sha256(repr((int(root), *keys)).encode()).digest()
    return int.from_bytes(h[:8], "big") & MAX_SEED


def validate_seed(seed: int) -> int:
    if not 0 <= int(seed) <= MAX_SEED:
        raise ValueError(f"seed must be in [0, {MAX_SEED}]")
    return int(seed)
