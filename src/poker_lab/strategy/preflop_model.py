"""Preflop range model built on the 169x169 class equity table (P7b).

- ``eq_vs_range(i, R)``: equity of class ``i`` against a weighted range ``R`` (card-removal
  weights from the table). Exact given the table; the table itself is Monte Carlo.
- ``open_fraction(players_behind)``: share of combos opened first-in, by number of players
  still to act. **Heuristic** values (documented in docs/P7B_REPORT.md), chosen from the
  development-set finding that open-raises were the most profitable line for every agent
  while the field folds its blinds to steals 77-98% of the time.
- ``shove_ev``: chip EV (in big blinds, relative to folding) of an all-in first-in against
  remaining players who each call with a given range. Ignores multiway calls (documented).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from poker_lab.strategy.ranges import class_rank_fraction

# fraction of all combos opened first-in, by players left to act behind (incl. blinds)
OPEN_FRACTION = {1: 0.60, 2: 0.48, 3: 0.32, 4: 0.24, 5: 0.18, 6: 0.15, 7: 0.13, 8: 0.12, 9: 0.11}

Range = Mapping[str, float]


def open_fraction(players_behind: int) -> float:
    return OPEN_FRACTION.get(players_behind, 0.11 if players_behind > 9 else 0.60)


def top_range(fraction: float) -> dict[str, float]:
    """Range of all classes whose cumulative combo rank is within ``fraction`` (weight 1)."""
    return {c: 1.0 for c in _classes() if class_rank_fraction(c) <= fraction + 1e-12}


@lru_cache(maxsize=1)
def _classes() -> tuple[str, ...]:
    from poker_lab.domain.cards import all_hand_classes

    return tuple(all_hand_classes())


@dataclass
class ClassEquity:
    classes: list[str]
    equity: list[list[float]]
    weights: list[list[float]]

    def __post_init__(self) -> None:
        self.index = {c: k for k, c in enumerate(self.classes)}

    @staticmethod
    def from_table(table: dict[str, Any]) -> ClassEquity:
        return ClassEquity(table["classes"], table["equity"], table["weights"])

    def eq_vs_range(self, cls: str, rng: Range) -> tuple[float, float]:
        """(equity, probability mass of the range given our card removal)."""
        i = self.index[cls]
        w_row = self.weights[i]
        e_row = self.equity[i]
        num = 0.0
        den = 0.0
        total = 0.0
        for j, c in enumerate(self.classes):
            w = w_row[j]
            total += w
            p = rng.get(c, 0.0)
            if p > 0 and w > 0:
                num += w * p * e_row[j]
                den += w * p
        return (num / den if den > 0 else 0.5), (den / total if total > 0 else 0.0)

    def shove_ev(
        self,
        cls: str,
        *,
        pot_bb: float,
        my_posted_bb: float,
        my_total_bb: float,
        callers: Sequence[tuple[float, float, Range]],
    ) -> float:
        """Chip EV of shoving vs folding, in bb.

        ``callers``: for each remaining player in acting order, (their total stack in bb,
        what they already posted in bb, their calling range). If one calls, later players
        are assumed to fold (multiway all-ins ignored).
        """
        reach = 1.0
        ev = 0.0
        for total_j, posted_j, rng_j in callers:
            eq, q = self.eq_vs_range(cls, rng_j)
            r = min(my_total_bb, total_j)
            dead = pot_bb - my_posted_bb - posted_j
            win = r + dead + my_posted_bb
            lose = my_posted_bb - r
            ev += reach * q * (eq * win + (1 - eq) * lose)
            reach *= 1 - q
        ev += reach * pot_bb
        return ev


def range_fraction_combos(rng: Range) -> float:
    from poker_lab.strategy.ranges import combos_of

    return sum(combos_of(c) * p for c, p in rng.items()) / 1326
