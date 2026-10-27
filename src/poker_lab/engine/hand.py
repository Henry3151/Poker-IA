"""No-Limit Texas Hold'em hand engine — the single source of truth for rules.

Rules implemented (documented simplifications in docs/ENGINE_RULES.md):
- 2..10 players in seat order; button index given by the caller.
- Antes (per player, dead money) posted before blinds; partial posts go all-in.
- Heads-up: button posts the small blind, acts first preflop and last postflop.
- Minimum bet = big blind; minimum raise increment = last full bet/raise increment.
- An all-in that is less than a full raise does not reopen betting for players who
  already acted, unless short all-ins accumulate to a full raise over what they faced.
- Side pots built from total contributions; uncalled chips are returned.
- Split pots: odd chips go to winners in seat order starting left of the button.
- Fold is only legal when facing a bet.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from poker_lab.domain.actions import Action, ActionKind, LegalActions, Street
from poker_lab.domain.cards import card_to_str
from poker_lab.domain.observation import Observation, PublicAction, PublicSeat, position_label
from poker_lab.engine.evaluator import category_name, evaluate


class IllegalActionError(ValueError):
    pass


class HandFinishedError(RuntimeError):
    pass


@dataclass(slots=True)
class _Seat:
    player_id: str
    starting_stack: int
    stack: int
    hole: tuple[int, int] = (0, 0)
    street_commit: int = 0
    total_commit: int = 0
    folded: bool = False
    all_in: bool = False
    acted: bool = False
    faced: int = 0  # current_bet when this player last acted this street


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    type: str
    visibility: str  # public_observation | private_agent_observation | offline_audit
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PotAward:
    amount: int
    eligible: tuple[int, ...]
    winners: tuple[int, ...]
    shares: tuple[int, ...]
    uncalled: bool = False  # True when the chips are an uncalled bet returned at showdown


@dataclass(frozen=True, slots=True)
class HandResult:
    hand_id: str
    final_street: Street
    board: tuple[int, ...]
    starting_stacks: tuple[int, ...]
    ending_stacks: tuple[int, ...]
    net: tuple[int, ...]
    pots: tuple[PotAward, ...]
    showdown_seats: tuple[int, ...]
    hand_scores: dict[int, int] = field(default_factory=dict)

    @property
    def pot_total(self) -> int:
        return sum(p.amount for p in self.pots if not p.uncalled)


class HandEngine:
    def __init__(
        self,
        players: list[tuple[str, int]],
        button: int,
        small_blind: int,
        big_blind: int,
        ante: int = 0,
        seed: int = 0,
        hand_id: str | None = None,
        deck: list[int] | None = None,
    ) -> None:
        n = len(players)
        if not 2 <= n <= 10:
            raise ValueError("2..10 players required")
        if any(stack <= 0 for _, stack in players):
            raise ValueError("all players must have chips")
        if len({pid for pid, _ in players}) != n:
            raise ValueError("duplicate player ids")
        if not (0 < small_blind <= big_blind) or ante < 0:
            raise ValueError("invalid blinds/ante")
        if not 0 <= button < n:
            raise ValueError("invalid button index")
        self.hand_id = hand_id or str(uuid.uuid4())
        self.n = n
        self.button = button
        self.sb_amount = small_blind
        self.bb_amount = big_blind
        self.ante = ante
        self.seed = seed
        self._seats = [_Seat(pid, s, s) for pid, s in players]
        self._board: list[int] = []
        self._events: list[Event] = []
        self._history: list[PublicAction] = []
        self.street = Street.PREFLOP
        self.current_bet = 0
        self.min_raise_inc = big_blind
        self._to_act: int | None = None
        self._needs: set[int] = set()
        self._finished = False
        self._result: HandResult | None = None

        if deck is None:
            deck = list(range(52))
            random.Random(seed).shuffle(deck)
        else:
            if sorted(deck) != list(range(52)):
                raise ValueError("deck must be a permutation of 0..51")
            deck = list(deck)
        self._deck = deck  # never exposed to agents
        self._deck_pos = 0

        self._emit(
            "hand_started",
            "public_observation",
            {
                "hand_id": self.hand_id,
                "button": button,
                "small_blind": small_blind,
                "big_blind": big_blind,
                "ante": ante,
                "players": [{"seat": i, "player_id": p, "stack": s} for i, (p, s) in enumerate(players)],
            },
        )
        self._post_forced_bets()
        self._deal_hole_cards()
        self._start_round(first=self._first_preflop_actor())

    # ------------------------------------------------------------------ helpers
    def _emit(self, etype: str, visibility: str, payload: dict[str, Any]) -> None:
        self._events.append(Event(len(self._events), etype, visibility, payload))

    def _next_seat(self, i: int) -> int:
        return (i + 1) % self.n

    @property
    def sb_seat(self) -> int:
        return self.button if self.n == 2 else self._next_seat(self.button)

    @property
    def bb_seat(self) -> int:
        return self._next_seat(self.sb_seat)

    def _commit(self, i: int, amount: int, *, street: bool = True) -> int:
        s = self._seats[i]
        amount = min(amount, s.stack)
        s.stack -= amount
        s.total_commit += amount
        if street:
            s.street_commit += amount
        if s.stack == 0:
            s.all_in = True
        return amount

    def _draw(self) -> int:
        c = self._deck[self._deck_pos]
        self._deck_pos += 1
        return c

    def _post_forced_bets(self) -> None:
        if self.ante:
            for i in range(self.n):
                paid = self._commit(i, self.ante, street=False)
                self._emit("ante_posted", "public_observation", {"seat": i, "amount": paid})
        for seat, amt, label in ((self.sb_seat, self.sb_amount, "small_blind"), (self.bb_seat, self.bb_amount, "big_blind")):
            if self._seats[seat].stack > 0:
                paid = self._commit(seat, amt)
                self._emit("blind_posted", "public_observation", {"seat": seat, "blind": label, "amount": paid})
        # the level to call is the full big blind even if the BB is short
        self.current_bet = max(self.bb_amount, max(s.street_commit for s in self._seats))
        self.min_raise_inc = self.bb_amount

    def _deal_hole_cards(self) -> None:
        for i in range(self.n):
            self._seats[i].hole = (self._draw(), self._draw())
        for i, s in enumerate(self._seats):
            self._emit(
                "hole_cards_dealt",
                "offline_audit",
                {"seat": i, "cards": [card_to_str(c) for c in s.hole]},
            )

    def _first_preflop_actor(self) -> int:
        return self._next_seat(self.bb_seat)

    def _first_postflop_actor(self) -> int:
        return self._next_seat(self.button)

    def _live(self) -> list[int]:
        return [i for i, s in enumerate(self._seats) if not s.folded]

    def _actionable(self) -> list[int]:
        return [i for i, s in enumerate(self._seats) if not s.folded and not s.all_in]

    def _start_round(self, first: int) -> None:
        actionable = self._actionable()
        live = self._live()
        if len(live) <= 1:
            self._finish()
            return
        max_commit = max(self._seats[i].street_commit for i in live)
        if not actionable or (
            len(actionable) == 1 and self._seats[actionable[0]].street_commit >= max_commit
        ):
            self._advance_street()
            return
        self._needs = set(actionable)
        for i in range(self.n):
            self._seats[i].acted = False
            self._seats[i].faced = 0
        self._to_act = self._next_needing(first, inclusive=True)

    def _next_needing(self, start: int, *, inclusive: bool) -> int | None:
        if not self._needs:
            return None
        i = start if inclusive else self._next_seat(start)
        for _ in range(self.n):
            if i in self._needs:
                return i
            i = self._next_seat(i)
        return None

    # ------------------------------------------------------------------ public API
    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def to_act(self) -> int | None:
        return None if self._finished else self._to_act

    @property
    def board(self) -> tuple[int, ...]:
        return tuple(self._board)

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def public_events(self) -> list[Event]:
        return [e for e in self._events if e.visibility == "public_observation"]

    def stacks(self) -> list[int]:
        return [s.stack for s in self._seats]

    def pot(self) -> int:
        return sum(s.total_commit for s in self._seats)

    def total_chips(self) -> int:
        return sum(s.stack + s.total_commit for s in self._seats)

    def hole_cards_offline(self, seat: int) -> tuple[int, int]:
        """Offline audit access to hole cards. Never pass the result to an agent."""
        return self._seats[seat].hole

    def legal_actions(self, seat: int) -> LegalActions:
        if self._finished or seat != self._to_act:
            raise IllegalActionError(f"seat {seat} is not to act")
        s = self._seats[seat]
        to_call = max(0, self.current_bet - s.street_commit)
        call_amount = min(to_call, s.stack)
        others_can_respond = any(
            not o.folded and not o.all_in for j, o in enumerate(self._seats) if j != seat
        )
        can_raise_rights = (not s.acted) or (self.current_bet - s.faced >= self.min_raise_inc)
        raise_kind: ActionKind | None = None
        min_to = max_to = 0
        max_possible = s.street_commit + s.stack
        if others_can_respond and can_raise_rights and s.stack > to_call:
            raise_kind = ActionKind.BET if self.current_bet == 0 else ActionKind.RAISE
            full_min = self.current_bet + self.min_raise_inc if self.current_bet else self.bb_amount
            max_to = max_possible
            min_to = min(full_min, max_possible)
        return LegalActions(
            can_fold=to_call > 0,
            can_check=to_call == 0,
            call_amount=call_amount,
            raise_kind=raise_kind,
            min_raise_to=min_to,
            max_raise_to=max_to,
        )

    def observation(self, seat: int) -> Observation:
        s = self._seats[seat]
        seats = tuple(
            PublicSeat(
                seat=i,
                player_id=o.player_id,
                position=position_label((i - self.button) % self.n, self.n),
                stack=o.stack,
                street_commitment=o.street_commit,
                total_commitment=o.total_commit,
                folded=o.folded,
                all_in=o.all_in,
            )
            for i, o in enumerate(self._seats)
        )
        return Observation(
            hand_id=self.hand_id,
            seat=seat,
            player_id=s.player_id,
            position=position_label((seat - self.button) % self.n, self.n),
            hole_cards=s.hole,
            board=tuple(self._board),
            street=self.street,
            button_seat=self.button,
            small_blind=self.sb_amount,
            big_blind=self.bb_amount,
            ante=self.ante,
            pot=self.pot(),
            current_bet=self.current_bet,
            to_call=min(max(0, self.current_bet - s.street_commit), s.stack),
            stack=s.stack,
            seats=seats,
            history=tuple(self._history),
            legal=self.legal_actions(seat),
        )

    def apply(self, seat: int, action: Action) -> None:
        if self._finished:
            raise HandFinishedError("hand is finished")
        legal = self.legal_actions(seat)
        why = legal.why_illegal(action)
        if why is not None:
            raise IllegalActionError(why)
        s = self._seats[seat]
        added = 0
        kind = action.kind
        if kind is ActionKind.FOLD:
            s.folded = True
        elif kind is ActionKind.CHECK:
            pass
        elif kind is ActionKind.CALL:
            added = self._commit(seat, legal.call_amount)
        else:
            assert action.amount is not None
            target = action.amount
            added = self._commit(seat, target - s.street_commit)
            increment = s.street_commit - self.current_bet
            if self.current_bet == 0:
                # opening bet: full if >= big blind
                if s.street_commit >= self.bb_amount:
                    self.min_raise_inc = s.street_commit
                self.current_bet = s.street_commit
            else:
                if increment >= self.min_raise_inc:
                    self.min_raise_inc = increment
                self.current_bet = s.street_commit
            # everyone else still in and not all-in must respond
            for j, o in enumerate(self._seats):
                if j != seat and not o.folded and not o.all_in:
                    self._needs.add(j)
        s.acted = True
        s.faced = self.current_bet
        self._needs.discard(seat)
        if s.all_in:
            self._needs.discard(seat)
        pa = PublicAction(seat, self.street.label, kind.value, added, s.street_commit)
        self._history.append(pa)
        self._emit(
            "action_applied",
            "public_observation",
            {"seat": seat, "street": self.street.label, "kind": kind.value, "added": added, "to_total": s.street_commit},
        )

        live = self._live()
        if len(live) == 1:
            self._finish()
            return
        nxt = self._next_needing(seat, inclusive=False)
        if nxt is None:
            self._advance_street()
        else:
            self._to_act = nxt

    # ------------------------------------------------------------------ streets
    def _advance_street(self) -> None:
        if len(self._live()) <= 1:
            self._finish()
            return
        if self.street is Street.RIVER:
            self._finish()
            return
        self.street = Street(self.street + 1)
        for s in self._seats:
            s.street_commit = 0
        self.current_bet = 0
        self.min_raise_inc = self.bb_amount
        if self.street is Street.FLOP:
            self._draw()  # burn
            new = [self._draw(), self._draw(), self._draw()]
        else:
            self._draw()  # burn
            new = [self._draw()]
        self._board.extend(new)
        self._emit(
            "street_dealt",
            "public_observation",
            {"street": self.street.label, "cards": [card_to_str(c) for c in new], "board": [card_to_str(c) for c in self._board]},
        )
        self._start_round(first=self._first_postflop_actor())

    def _finish(self) -> None:
        if self._finished:
            return
        live = self._live()
        showdown = len(live) > 1
        if showdown:
            while len(self._board) < 5:
                self._draw()
                if len(self._board) == 0:
                    self._board.extend([self._draw(), self._draw(), self._draw()])
                else:
                    self._board.append(self._draw())
        scores: dict[int, int] = {}
        if showdown:
            for i in live:
                scores[i] = evaluate([*self._seats[i].hole, *self._board])
        pots = self._settle(live, scores)
        final_street = Street.SHOWDOWN if showdown else self.street
        self.street = final_street
        self._finished = True
        self._to_act = None
        result = HandResult(
            hand_id=self.hand_id,
            final_street=final_street,
            board=tuple(self._board),
            starting_stacks=tuple(s.starting_stack for s in self._seats),
            ending_stacks=tuple(s.stack for s in self._seats),
            net=tuple(s.stack - s.starting_stack for s in self._seats),
            pots=tuple(pots),
            showdown_seats=tuple(live) if showdown else (),
            hand_scores=scores,
        )
        if showdown:
            self._emit(
                "showdown",
                "public_observation",
                {
                    "board": [card_to_str(c) for c in self._board],
                    "hands": [
                        {
                            "seat": i,
                            "cards": [card_to_str(c) for c in self._seats[i].hole],
                            "category": category_name(scores[i]),
                        }
                        for i in live
                    ],
                },
            )
        for p in pots:
            self._emit(
                "pot_awarded",
                "public_observation",
                {"amount": p.amount, "eligible": list(p.eligible), "winners": list(p.winners), "shares": list(p.shares)},
            )
        self._emit(
            "hand_completed",
            "public_observation",
            {"final_street": final_street.label, "net": list(result.net), "ending_stacks": list(result.ending_stacks)},
        )
        if sum(result.ending_stacks) != sum(result.starting_stacks):  # pragma: no cover - invariant
            raise AssertionError("chip conservation violated")
        self._result = result

    def _settle(self, live: list[int], scores: dict[int, int]) -> list[PotAward]:
        remaining = [s.total_commit for s in self._seats]
        pots: list[PotAward] = []
        order = [(self.button + 1 + k) % self.n for k in range(self.n)]  # left of button first
        while any(remaining):
            live_left = [i for i in live if remaining[i] > 0]
            if not live_left:
                # Forced bets (antes/blinds) of folded players above every live player's
                # contribution: no live player can win them (a player wins at most what
                # they matched), so they are returned to their contributors.
                for j in range(self.n):
                    if remaining[j]:
                        self._seats[j].stack += remaining[j]
                        self._emit("uncalled_returned", "public_observation", {"seat": j, "amount": remaining[j]})
                remaining = [0] * self.n
                break
            level = min(remaining[i] for i in live_left)
            amount = 0
            takes = [0] * self.n
            for j in range(self.n):
                take = min(remaining[j], level)
                remaining[j] -= take
                takes[j] = take
                amount += take
            eligible = tuple(i for i in live_left)
            if len(eligible) == 1 and len(live) > 1:
                # Only the part of the sole eligible player's chips that nobody matched is
                # "uncalled"; dead money from folded players in this slice is won normally.
                me = eligible[0]
                matched = max((takes[j] for j in range(self.n) if j != me), default=0)
                won = amount - takes[me] + min(takes[me], matched)
                returned = amount - won
                self._seats[me].stack += amount
                if won:
                    pots.append(PotAward(won, eligible, eligible, (won,)))
                if returned:
                    pots.append(PotAward(returned, eligible, eligible, (returned,), uncalled=True))
                continue
            if len(eligible) == 1 or not scores:
                winners: tuple[int, ...] = (eligible[0],) if len(eligible) == 1 else tuple(live_left[:1])
            else:
                best = max(scores[i] for i in eligible)
                winners = tuple(i for i in order if i in eligible and scores[i] == best)
            base, odd = divmod(amount, len(winners))
            shares = tuple(base + (1 if k < odd else 0) for k in range(len(winners)))
            for w, sh in zip(winners, shares, strict=True):
                self._seats[w].stack += sh
            pots.append(PotAward(amount, eligible, winners, shares))
        for s in self._seats:
            s.street_commit = 0
        return pots

    def result(self) -> HandResult:
        if self._result is None:
            raise RuntimeError("hand not finished")
        return self._result
