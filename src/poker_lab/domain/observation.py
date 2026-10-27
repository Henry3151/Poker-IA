"""What an agent is allowed to see.

An :class:`Observation` is built by the engine for exactly one seat. It contains that
seat's hole cards and public information only. It holds no reference to the engine,
the deck or other players' cards, so an agent cannot reach hidden information through it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from poker_lab.domain.actions import LegalActions, Street

POSITION_TABLES: dict[int, tuple[str, ...]] = {
    # index = offset clockwise from the button
    2: ("BTN", "BB"),  # heads-up: the button posts the small blind
    3: ("BTN", "SB", "BB"),
    4: ("BTN", "SB", "BB", "CO"),
    5: ("BTN", "SB", "BB", "HJ", "CO"),
    6: ("BTN", "SB", "BB", "UTG", "HJ", "CO"),
    7: ("BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"),
    8: ("BTN", "SB", "BB", "UTG", "UTG1", "LJ", "HJ", "CO"),
    9: ("BTN", "SB", "BB", "UTG", "UTG1", "UTG2", "LJ", "HJ", "CO"),
    10: ("BTN", "SB", "BB", "UTG", "UTG1", "UTG2", "MP", "LJ", "HJ", "CO"),
}
ALL_POSITIONS = ("BTN", "SB", "BB", "UTG", "UTG1", "UTG2", "MP", "LJ", "HJ", "CO")


def position_label(offset_from_button: int, n_players: int) -> str:
    return POSITION_TABLES[n_players][offset_from_button % n_players]


@dataclass(frozen=True, slots=True)
class PublicSeat:
    seat: int
    player_id: str
    position: str
    stack: int
    street_commitment: int
    total_commitment: int
    folded: bool
    all_in: bool


@dataclass(frozen=True, slots=True)
class PublicAction:
    seat: int
    street: str
    kind: str
    amount: int  # chips added by this action (0 for fold/check)
    to_total: int  # street commitment after the action


@dataclass(frozen=True, slots=True)
class TournamentInfo:
    """Public tournament state (chip counts and payouts are public in a live MTT)."""

    entrants: int
    players_remaining: int
    paid_places: int
    payouts: tuple[int, ...]
    level: int
    phase: str
    average_stack: float
    other_table_stacks: tuple[int, ...]  # stacks of remaining players at other tables


@dataclass(frozen=True, slots=True)
class Observation:
    hand_id: str
    seat: int
    player_id: str
    position: str
    hole_cards: tuple[int, int]
    board: tuple[int, ...]
    street: Street
    button_seat: int
    small_blind: int
    big_blind: int
    ante: int
    pot: int  # all chips committed this hand, including the current street
    current_bet: int  # highest street commitment
    to_call: int
    stack: int
    seats: tuple[PublicSeat, ...]
    history: tuple[PublicAction, ...]
    legal: LegalActions
    tournament: TournamentInfo | None = None

    @property
    def n_active(self) -> int:
        return sum(1 for s in self.seats if not s.folded)

    @property
    def n_opponents_active(self) -> int:
        return self.n_active - 1

    @property
    def effective_stack(self) -> int:
        """Smallest of own (stack + street commitment) and the largest active opponent's."""
        me = self.stack + self._me().street_commitment
        opp = [s.stack + s.street_commitment for s in self.seats if s.seat != self.seat and not s.folded]
        return min(me, max(opp)) if opp else me

    def _me(self) -> PublicSeat:
        for s in self.seats:
            if s.seat == self.seat:
                return s
        raise LookupError(self.seat)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["street"] = self.street.label
        d["legal"] = self.legal.to_dict()
        return d
