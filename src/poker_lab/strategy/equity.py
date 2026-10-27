"""Equity estimation.

Equity = expected share of the pot at showdown if no one folds (ties count fractionally).
It is *not* EV: EV also depends on future betting and fold equity. Every estimate records
its method, sample count and standard error so analytics can show the uncertainty.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations

from poker_lab.domain.cards import hand_class
from poker_lab.engine.evaluator import evaluate

HandFilter = Callable[[tuple[int, int]], bool]


@dataclass(frozen=True, slots=True)
class EquityEstimate:
    equity: float
    stderr: float
    samples: int
    method: str  # monte_carlo | enumeration
    opponents: int

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "equity": round(self.equity, 5),
            "stderr": round(self.stderr, 5),
            "samples": self.samples,
            "method": self.method,
            "opponents": self.opponents,
        }


def _share(my: int, opp_scores: Sequence[int]) -> float:
    best = max(opp_scores)
    if my > best:
        return 1.0
    if my < best:
        return 0.0
    ties = sum(1 for s in opp_scores if s == my)
    return 1.0 / (ties + 1)


def monte_carlo_equity(
    hole: Sequence[int],
    board: Sequence[int],
    n_opponents: int,
    samples: int,
    rng: random.Random,
    opponent_filter: HandFilter | None = None,
    max_rejections: int = 50,
) -> EquityEstimate:
    if n_opponents < 1:
        return EquityEstimate(1.0, 0.0, 0, "trivial", 0)
    dead = set(hole) | set(board)
    deck = [c for c in range(52) if c not in dead]
    need_board = 5 - len(board)
    total = 0.0
    total_sq = 0.0
    hole_t = list(hole)
    board_t = list(board)
    for _ in range(samples):
        rng.shuffle(deck)
        pos = 0
        opps: list[list[int]] = []
        for _o in range(n_opponents):
            # rejection sampling for ranged opponents, bounded so it always terminates
            for _try in range(max_rejections):
                cand = (deck[pos], deck[pos + 1])
                if opponent_filter is None or opponent_filter(cand):
                    break
                # swap the rejected cards to the end region and retry with fresh ones
                j = rng.randrange(pos, len(deck) - 1)
                deck[pos], deck[j] = deck[j], deck[pos]
                k = rng.randrange(pos + 1, len(deck))
                deck[pos + 1], deck[k] = deck[k], deck[pos + 1]
            opps.append([deck[pos], deck[pos + 1]])
            pos += 2
        runout = board_t + deck[pos : pos + need_board]
        my = evaluate(hole_t + runout)
        share = _share(my, [evaluate(o + runout) for o in opps])
        total += share
        total_sq += share * share
    mean = total / samples
    var = max(0.0, total_sq / samples - mean * mean)
    return EquityEstimate(mean, math.sqrt(var / samples), samples, "monte_carlo", n_opponents)


def exact_equity_heads_up(hole: Sequence[int], board: Sequence[int]) -> EquityEstimate:
    """Exact equity vs one uniformly random hand on a complete (5-card) board."""
    if len(board) != 5:
        raise ValueError("exact enumeration requires a 5-card board")
    dead = set(hole) | set(board)
    deck = [c for c in range(52) if c not in dead]
    my = evaluate([*hole, *board])
    total = 0.0
    n = 0
    for a, b in combinations(deck, 2):
        total += _share(my, [evaluate([a, b, *board])])
        n += 1
    return EquityEstimate(total / n, 0.0, n, "enumeration", 1)


def pot_odds(to_call: int, pot: int) -> float:
    """Fraction of the final pot the caller must contribute: to_call / (pot + to_call)."""
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def top_fraction_filter(fraction: float) -> HandFilter:
    """Opponent range: top ``fraction`` of the 169 classes ordered by preflop strength."""
    from poker_lab.strategy.ranges import class_rank_fraction

    def f(cards: tuple[int, int]) -> bool:
        return class_rank_fraction(hand_class(cards)) <= fraction

    return f
