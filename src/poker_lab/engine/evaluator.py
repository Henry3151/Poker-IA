"""Own 5..7-card hand evaluator.

``evaluate(cards)`` returns an int where a higher value is a stronger hand. The value is
``category << 20 | tiebreak`` where ``tiebreak`` packs up to five ranks in 4-bit nibbles.
Correctness is cross-checked against the MIT-licensed ``treys`` library in the tests.
"""

from __future__ import annotations

from collections.abc import Sequence

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)
CATEGORY_NAMES = (
    "high_card",
    "pair",
    "two_pair",
    "trips",
    "straight",
    "flush",
    "full_house",
    "quads",
    "straight_flush",
)

_WHEEL = (1 << 12) | 0b1111  # A,2,3,4,5


def _straight_high(mask: int) -> int:
    """Highest rank of a 5-long straight in rank bitmask, or -1."""
    for hi in range(12, 3, -1):
        need = 0b11111 << (hi - 4)
        if mask & need == need:
            return hi
    if mask & _WHEEL == _WHEEL:
        return 3  # five-high
    return -1


def _pack(category: int, ranks: Sequence[int]) -> int:
    v = 0
    for i in range(5):
        v = (v << 4) | (ranks[i] if i < len(ranks) else 0)
    return (category << 20) | v


def evaluate(cards: Sequence[int]) -> int:
    n = len(cards)
    if not 5 <= n <= 7:
        raise ValueError("evaluate expects 5 to 7 cards")
    counts = [0] * 13
    suit_masks = [0, 0, 0, 0]
    suit_counts = [0, 0, 0, 0]
    mask = 0
    for c in cards:
        r = c >> 2
        s = c & 3
        counts[r] += 1
        suit_masks[s] |= 1 << r
        suit_counts[s] += 1
        mask |= 1 << r

    # flush / straight flush
    for s in range(4):
        if suit_counts[s] >= 5:
            fm = suit_masks[s]
            sh = _straight_high(fm)
            if sh >= 0:
                return _pack(STRAIGHT_FLUSH, [sh])
            ranks = [r for r in range(12, -1, -1) if fm >> r & 1][:5]
            flush_value = _pack(FLUSH, ranks)
            # quads/full house beat a flush; check them below and compare
            break
    else:
        flush_value = -1

    quads = [r for r in range(12, -1, -1) if counts[r] == 4]
    trips = [r for r in range(12, -1, -1) if counts[r] == 3]
    pairs = [r for r in range(12, -1, -1) if counts[r] == 2]

    if quads:
        q = quads[0]
        kicker = max(r for r in range(13) if counts[r] and r != q)
        return _pack(QUADS, [q, kicker])
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = max(trips[1] if len(trips) >= 2 else -1, pairs[0] if pairs else -1)
        return _pack(FULL_HOUSE, [t, p])
    if flush_value >= 0:
        return flush_value
    sh = _straight_high(mask)
    if sh >= 0:
        return _pack(STRAIGHT, [sh])
    singles = [r for r in range(12, -1, -1) if counts[r] == 1]
    if trips:
        t = trips[0]
        return _pack(TRIPS, [t, *singles[:2]])
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        rest = sorted([r for r in range(13) if counts[r] and r not in (p1, p2)], reverse=True)
        return _pack(TWO_PAIR, [p1, p2, rest[0]])
    if pairs:
        p = pairs[0]
        return _pack(PAIR, [p, *singles[:3]])
    return _pack(HIGH_CARD, singles[:5])


def category_of(score: int) -> int:
    return score >> 20


def category_name(score: int) -> str:
    return CATEGORY_NAMES[category_of(score)]
