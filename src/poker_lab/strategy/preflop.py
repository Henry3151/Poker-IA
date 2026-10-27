"""Preflop hand-strength helpers (no external data).

``chen_score`` implements Bill Chen's published preflop formula (a well-known public
heuristic). It is a *heuristic*, not an equilibrium strategy.
"""

from __future__ import annotations

from collections.abc import Sequence

from poker_lab.domain.cards import rank_of, suit_of

_HIGH_POINTS = {12: 10.0, 11: 8.0, 10: 7.0, 9: 6.0}


def chen_score(hole: Sequence[int]) -> float:
    a, b = sorted((rank_of(c) for c in hole), reverse=True)
    suited = suit_of(hole[0]) == suit_of(hole[1])
    score = _HIGH_POINTS.get(a, (a + 2) / 2.0)
    if a == b:
        score = max(score * 2, 5.0)
        return score
    if suited:
        score += 2
    gap = a - b - 1
    score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and a < 10:  # both below queen and connected/one-gap
        score += 1
    return float(round(score + 0.49))  # Chen rounds half up


def chen_percentile(score: float) -> float:
    """Rough mapping of Chen score (-1..20) to 0..1 strength."""
    return max(0.0, min(1.0, (score + 1.0) / 21.0))
