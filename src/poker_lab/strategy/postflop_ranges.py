"""Range-conditioned opponent sampling for postflop equity (P7b, hypothesis H3).

Development-set evidence: equity estimated against *uniform random* hands when facing a
postflop bet overstated true equity (measured offline against the bettor's real cards)
by +0.10..+0.41 depending on street. A bettor's range is stronger than random.

``betting_filter`` keeps a sampled opponent hand if it (a) makes at least a pair using a
hole card, or (b) holds a flush draw or an open-ended straight draw, and otherwise keeps
it only with probability ``bluff_rate`` (the share of "air" in a betting range).
``bluff_rate`` is a calibrated *heuristic* parameter (chosen on the development set only).
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from poker_lab.engine.evaluator import PAIR, category_of, evaluate


def _has_draw(hole: Sequence[int], board: Sequence[int]) -> bool:
    cards = [*hole, *board]
    if len(board) >= 5:
        return False
    suits = [0, 0, 0, 0]
    for c in cards:
        suits[c & 3] += 1
    for s in range(4):
        if suits[s] == 4 and any((h & 3) == s for h in hole):
            return True
    ranks = {c >> 2 for c in cards}
    if 12 in ranks:
        ranks.add(-1)
    for lo in range(-1, 9):
        window = {lo, lo + 1, lo + 2, lo + 3}
        if window <= ranks and (lo - 1 not in ranks or lo + 4 not in ranks) and any(
            (h >> 2) in window or ((h >> 2) == 12 and -1 in window) for h in hole
        ):
            return True
    return False


def _board_category(board: Sequence[int]) -> int:
    if len(board) >= 5:
        return category_of(evaluate(list(board)))
    counts: dict[int, int] = {}
    for c in board:
        counts[c >> 2] = counts.get(c >> 2, 0) + 1
    m = sorted(counts.values(), reverse=True)
    if m[0] >= 3:
        return 3
    if m[0] == 2:
        return 2 if len(m) > 1 and m[1] == 2 else 1
    return 0


def betting_filter(board: Sequence[int], bluff_rate: float, rng: random.Random) -> Callable[[tuple[int, int]], bool]:
    board_cat = _board_category(board)
    b = list(board)

    def keep(cards: tuple[int, int]) -> bool:
        cat = category_of(evaluate([*cards, *b]))
        if cat >= PAIR and cat > board_cat:
            return True
        if _has_draw(cards, b):
            return True
        return rng.random() < bluff_rate

    return keep
