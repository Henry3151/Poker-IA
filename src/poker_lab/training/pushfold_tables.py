"""Class-vs-class preflop all-in equity matrix (169x169) and combo weights.

Equity is Monte Carlo (sampled concrete disjoint combos + random runout), so every cell
carries sampling error (~0.5/sqrt(samples)); the matrix is symmetrised so
eq[i][j] + eq[j][i] == 1. Weights count disjoint combo pairs exactly (card removal).
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

from poker_lab.domain.cards import RANK_CHARS, all_hand_classes, make_card
from poker_lab.engine.evaluator import evaluate
from poker_lab.persistence.db import file_sha256

FORMAT = "poker_lab.hu_class_equity.v1"


def class_combos(cls: str) -> list[tuple[int, int]]:
    hi, lo = RANK_CHARS.index(cls[0]), RANK_CHARS.index(cls[1])
    out = []
    if len(cls) == 2:
        for s1 in range(4):
            for s2 in range(s1 + 1, 4):
                out.append((make_card(hi, s1), make_card(lo, s2)))
    elif cls.endswith("s"):
        out = [(make_card(hi, s), make_card(lo, s)) for s in range(4)]
    else:
        out = [(make_card(hi, s1), make_card(lo, s2)) for s1 in range(4) for s2 in range(4) if s1 != s2]
    return out


def build_table(samples: int, seed: int) -> dict[str, Any]:
    classes = all_hand_classes()
    combos = [class_combos(c) for c in classes]
    n = len(classes)
    rng = random.Random(seed)
    eq = [[0.5] * n for _ in range(n)]
    weights = [[0.0] * n for _ in range(n)]
    t0 = time.perf_counter()
    for i in range(n):
        for j in range(n):
            weights[i][j] = float(sum(1 for a in combos[i] for b in combos[j] if not (set(a) & set(b))))
    deck_all = list(range(52))
    for i in range(n):
        for j in range(i, n):
            pairs = [(a, b) for a in combos[i] for b in combos[j] if not (set(a) & set(b))]
            if not pairs:
                continue
            total = 0.0
            for _ in range(samples):
                a, b = pairs[rng.randrange(len(pairs))]
                dead = {a[0], a[1], b[0], b[1]}
                board: list[int] = []
                while len(board) < 5:
                    c = deck_all[rng.randrange(52)]
                    if c not in dead:
                        dead.add(c)
                        board.append(c)
                sa = evaluate([a[0], a[1], *board])
                sb = evaluate([b[0], b[1], *board])
                total += 1.0 if sa > sb else (0.5 if sa == sb else 0.0)
            e = total / samples
            if i == j:
                e = 0.5  # same class: symmetric by construction
            eq[i][j] = e
            eq[j][i] = 1.0 - e
    return {
        "format": FORMAT,
        "classes": classes,
        "equity": [[round(x, 5) for x in row] for row in eq],
        "weights": weights,
        "samples_per_pair": samples,
        "seed": seed,
        "method": "monte_carlo_disjoint_combos",
        "elapsed_seconds": round(time.perf_counter() - t0, 1),
    }


def save_table(table: dict[str, Any], path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(table))
    return file_sha256(p)


def load_table(path: str | Path, expected_sha256: str | None = None) -> dict[str, Any]:
    p = Path(path)
    if expected_sha256 and file_sha256(p) != expected_sha256:
        raise ValueError("equity table checksum mismatch")
    data: dict[str, Any] = json.loads(p.read_text())
    if data.get("format") != FORMAT or len(data["classes"]) != 169:
        raise ValueError("not a valid class equity table")
    for row in data["equity"]:
        if len(row) != 169 or any(not 0.0 <= x <= 1.0 for x in row):
            raise ValueError("invalid equity row")
    return data


def get_or_build(path: str | Path, samples: int = 200, seed: int = 20261026) -> dict[str, Any]:
    p = Path(path)
    if p.exists():
        data = load_table(p)
        if data["samples_per_pair"] == samples and data["seed"] == seed:
            return data
    data = build_table(samples, seed)
    save_table(data, p)
    return data
