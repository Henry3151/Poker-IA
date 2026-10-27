"""Card representation.

A card is an ``int`` in ``0..51``: ``rank = card // 4`` (0 = deuce .. 12 = ace) and
``suit = card % 4`` (0=c, 1=d, 2=h, 3=s). Integers keep the engine fast and trivially
serialisable; helpers convert to/from the conventional two-character notation ("As", "Td").
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"
FULL_DECK: tuple[int, ...] = tuple(range(52))

Card = int


def make_card(rank: int, suit: int) -> Card:
    if not (0 <= rank < 13 and 0 <= suit < 4):
        raise ValueError(f"invalid rank/suit {rank}/{suit}")
    return rank * 4 + suit


def rank_of(card: Card) -> int:
    return card // 4


def suit_of(card: Card) -> int:
    return card % 4


def card_to_str(card: Card) -> str:
    if not 0 <= card < 52:
        raise ValueError(f"invalid card {card}")
    return RANK_CHARS[card // 4] + SUIT_CHARS[card % 4]


def parse_card(text: str) -> Card:
    if len(text) != 2:
        raise ValueError(f"invalid card text {text!r}")
    r = RANK_CHARS.find(text[0].upper())
    s = SUIT_CHARS.find(text[1].lower())
    if r < 0 or s < 0:
        raise ValueError(f"invalid card text {text!r}")
    return make_card(r, s)


def parse_cards(text: str) -> list[Card]:
    """Parse "AsKd Th" or "AsKdTh" into a list of cards."""
    compact = text.replace(" ", "").replace(",", "")
    if len(compact) % 2:
        raise ValueError(f"invalid cards text {text!r}")
    cards = [parse_card(compact[i : i + 2]) for i in range(0, len(compact), 2)]
    if len(set(cards)) != len(cards):
        raise ValueError(f"duplicate cards in {text!r}")
    return cards


def cards_to_str(cards: Iterable[Card]) -> str:
    return " ".join(card_to_str(c) for c in cards)


def hand_class(hole: Sequence[Card]) -> str:
    """Canonical 169-class label: 'AA', 'AKs', 'AKo', ..."""
    if len(hole) != 2:
        raise ValueError("hand_class requires exactly two cards")
    a, b = sorted(hole, key=lambda c: (rank_of(c), suit_of(c)), reverse=True)
    ra, rb = RANK_CHARS[rank_of(a)], RANK_CHARS[rank_of(b)]
    if ra == rb:
        return ra + rb
    return ra + rb + ("s" if suit_of(a) == suit_of(b) else "o")


def all_hand_classes() -> list[str]:
    out: list[str] = []
    for hi in range(12, -1, -1):
        for lo in range(hi, -1, -1):
            if hi == lo:
                out.append(RANK_CHARS[hi] * 2)
            else:
                out.append(RANK_CHARS[hi] + RANK_CHARS[lo] + "s")
                out.append(RANK_CHARS[hi] + RANK_CHARS[lo] + "o")
    return out
