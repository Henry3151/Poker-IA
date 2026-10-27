"""Simple range model: the 169 preflop classes ordered by equity vs. a random hand
(measured table in ``data/preflop_equity_vs_random.json``), weighted by combos.

``class_rank_fraction(c)`` is the fraction of all 1326 combos that are at least as strong
as class ``c`` under that ordering. It is an approximation used for opponent modelling
("opponent who raised is in the top 20%"), not a solver range.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from poker_lab.domain.cards import RANK_CHARS, make_card


def combos_of(cls: str) -> int:
    if len(cls) == 2:
        return 6
    return 4 if cls.endswith("s") else 12


def representative_cards(cls: str) -> tuple[int, int]:
    hi = RANK_CHARS.index(cls[0])
    lo = RANK_CHARS.index(cls[1])
    if len(cls) == 2:
        return make_card(hi, 0), make_card(lo, 1)
    if cls.endswith("s"):
        return make_card(hi, 0), make_card(lo, 0)
    return make_card(hi, 0), make_card(lo, 1)


@lru_cache(maxsize=1)
def preflop_equity_table() -> dict[str, float]:
    raw = resources.files("poker_lab.strategy.data").joinpath("preflop_equity_vs_random.json").read_text()
    return {k: float(v["equity"]) for k, v in json.loads(raw)["classes"].items()}


@lru_cache(maxsize=1)
def _ordering() -> dict[str, float]:
    eq = preflop_equity_table()
    scored = sorted(eq, key=lambda c: (-eq[c], c))
    out: dict[str, float] = {}
    cum = 0
    for c in scored:
        cum += combos_of(c)
        out[c] = cum / 1326
    return out


def class_rank_fraction(cls: str) -> float:
    return _ordering()[cls]


def top_classes(fraction: float) -> list[str]:
    return [c for c, f in _ordering().items() if f <= fraction]
