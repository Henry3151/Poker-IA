"""Table state tracking and translation between Open Poker messages and internal types.

Only data the platform sends to this seat during the hand is used: own hole cards and
public events. ``shown_cards`` from ``hand_result`` are never copied into an observation.
Per-player street commitments are reconstructed from public events (``contribution_delta``
or stack changes); where the platform gives authoritative numbers (pot, call amount,
min/max raise-to, current stacks) those override the reconstruction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from poker_lab.domain.actions import Action, ActionKind, LegalActions, Street
from poker_lab.domain.observation import Observation, PublicAction, PublicSeat, position_label
from poker_lab.integrations.openpoker import protocol as P

STREETS = {"preflop": Street.PREFLOP, "flop": Street.FLOP, "turn": Street.TURN, "river": Street.RIVER}
BLIND_ACTIONS = {"small_blind", "big_blind", "post_blind", "post_sb", "post_bb", "sb", "bb", "blind"}


HASH_EXCLUDED = ("ts", "table_seq", "hand_seq", "state_hash")


def compute_state_hash(message: dict[str, Any]) -> str:
    """Documented algorithm: SHA-256 of the message without ts/table_seq/hand_seq/state_hash,
    compact sorted-key JSON with ASCII escaping, prefixed 'sha256:'."""
    body = {k: v for k, v in message.items() if k not in HASH_EXCLUDED}
    text = json.dumps(body, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("ascii")).hexdigest()


def state_hash_ok(message: dict[str, Any]) -> bool:
    """True when there is no state_hash or it matches (verifies the snapshot, not completeness)."""
    h = message.get("state_hash")
    return h is None or h == compute_state_hash(message)


class UnsupportedState(RuntimeError):
    """State the adapter cannot represent safely; the caller must use the safe fallback."""


class StateDivergence(UnsupportedState):
    """Our reconstruction disagrees with the server (missed events, other hand, pot mismatch).
    The caller must NOT act on it: pause and recover an authoritative snapshot first."""


def reconcile_pot(platform_pot: int, total_committed: int, street_committed: int) -> str | None:
    """Return the pot convention that matches ('incl_street' / 'excl_street') or None.

    The docs do not state whether ``pot`` in ``your_turn`` includes bets of the current street,
    so both are accepted; anything else is a divergence (no ante, no rake on the platform)."""
    if platform_pot == total_committed:
        return "incl_street"
    if platform_pot == total_committed - street_committed:
        return "excl_street"
    return None


@dataclass
class SeatTrack:
    seat: int
    name: str
    stack: int
    street_commit: int = 0
    total_commit: int = 0
    folded: bool = False


@dataclass
class TableTracker:
    my_seat: int | None = None
    table_id: str | None = None
    last_table_seq: int = 0
    roster: dict[int, str] = field(default_factory=dict)
    roster_stacks: dict[int, int] = field(default_factory=dict)
    hand_id: str | None = None
    dealer: int = 0
    sb: int = 0
    bb: int = 0
    seats: dict[int, SeatTrack] = field(default_factory=dict)
    hole: tuple[int, int] | None = None
    board: list[int] = field(default_factory=list)
    street: str = "preflop"
    history: list[tuple[int, str, str, int, int]] = field(default_factory=list)
    blind_inferred: set[int] = field(default_factory=set)
    duplicates_ignored: int = 0
    gaps_detected: int = 0
    gap_pending: bool = False

    # ------------------------------------------------------------ dedupe
    def accept(self, msg: P._Msg) -> bool:
        """False for duplicate/regressed table-scoped messages (documented: ignore them)."""
        if msg.table_seq is None:
            return True
        if msg.table_seq <= self.last_table_seq:
            self.duplicates_ignored += 1
            return False
        if self.last_table_seq and msg.table_seq > self.last_table_seq + 1:
            self.gaps_detected += 1  # events were missed: state may have diverged
            self.gap_pending = True
        self.last_table_seq = msg.table_seq
        return True

    # ------------------------------------------------------------ events
    def apply(self, msg: P._Msg) -> None:
        if isinstance(msg, P.TableJoined):
            self.table_id = msg.table_id
            self.my_seat = msg.seat
            self.roster = {p.seat: p.name or f"seat{p.seat}" for p in msg.players}
            self.roster_stacks = {p.seat: p.stack for p in msg.players}
        elif msg.type == "player_joined":
            extra: dict[str, Any] = msg.model_extra or {}
            if "seat" in extra:
                self.roster[int(extra["seat"])] = str(extra.get("name") or f"seat{extra['seat']}")
                if "stack" in extra:
                    self.roster_stacks[int(extra["seat"])] = int(extra["stack"])
        elif msg.type == "player_left":
            extra = msg.model_extra or {}
            if "seat" in extra:
                self.roster.pop(int(extra["seat"]), None)
        elif isinstance(msg, P.HandStart):
            self._start_hand(msg)
        elif isinstance(msg, P.HoleCards):
            if len(msg.cards) != 2:
                raise UnsupportedState("expected two hole cards")
            self.hole = (P.card(msg.cards[0]), P.card(msg.cards[1]))
        elif isinstance(msg, P.CommunityCards):
            self.board = [P.card(c) for c in msg.cards] if len(msg.cards) >= 3 else self.board + [P.card(c) for c in msg.cards]
            self.street = msg.street
            for s in self.seats.values():
                s.street_commit = 0
        elif isinstance(msg, P.PlayerAction):
            self._player_action(msg)
        elif isinstance(msg, P.HandResult):
            for k, v in msg.final_stacks.items():
                self.roster_stacks[int(k)] = int(v)
            self.hand_id = None
            self.hole = None  # never carried into the next hand

    def committed_total(self) -> int:
        return sum(s.total_commit for s in self.seats.values())

    def install_snapshot(self, snap: dict[str, Any], hand_id: str | None = None) -> None:
        """Replace the reconstructed state with an authoritative table_state/resync snapshot."""
        if not snap:
            return
        if hand_id:
            self.hand_id = hand_id
        self.dealer = int(snap.get("dealer_seat", self.dealer))
        self.sb = int(snap.get("small_blind", self.sb))
        self.bb = int(snap.get("big_blind", self.bb))
        self.street = str(snap.get("street", self.street))
        if "board" in snap:  # only overwrite fields the snapshot actually contains
            self.board = [P.card(c) for c in snap["board"]]
        new: dict[int, SeatTrack] = {}
        for st in snap.get("seats", []):
            if not st.get("in_hand", False):  # documented: in_hand = dealt in (folded players included)
                continue
            seat = int(st["seat"])
            prev = self.seats.get(seat)
            bet = int(st.get("bet", 0))
            t = SeatTrack(seat, st.get("name") or f"seat{seat}", int(st.get("stack", 0)), bet,
                          max(bet, prev.total_commit if prev else bet),
                          bool(st.get("folded", False)) or st.get("status") == "folded")
            new[seat] = t
        if new:
            self.seats = new
            self.roster = {s: t.name for s, t in new.items()}
        hero = snap.get("hero") or {}
        if hero.get("seat") is not None:
            self.my_seat = int(hero["seat"])
        if hero.get("hole_cards"):
            cards = hero["hole_cards"]
            if len(cards) == 2:
                self.hole = (P.card(cards[0]), P.card(cards[1]))

    def _start_hand(self, msg: P.HandStart) -> None:
        self.hand_id = msg.hand_id
        self.my_seat = msg.seat
        self.dealer = msg.dealer_seat
        self.sb, self.bb = msg.blinds.small_blind, msg.blinds.big_blind
        self.board, self.street, self.history, self.hole = [], "preflop", [], None
        roster = dict(self.roster)
        roster.setdefault(msg.seat, f"seat{msg.seat}")
        self.seats = {
            s: SeatTrack(s, roster[s], self.roster_stacks.get(s, 0)) for s in sorted(roster) if self.roster_stacks.get(s, 1) > 0
        }
        self.blind_inferred = set()
        order = self.order()
        if len(order) >= 2:
            if len(order) == 2:
                sb_seat = self.dealer if self.dealer in order else order[0]
            else:
                sb_seat = self._next(self.dealer)
            bb_seat = self._next(sb_seat)
            for seat, amt in ((sb_seat, self.sb), (bb_seat, self.bb)):
                t = self.seats[seat]
                paid = min(amt, t.stack) if t.stack else amt
                t.street_commit += paid
                t.total_commit += paid
                t.stack = max(0, t.stack - paid)
                self.blind_inferred.add(seat)

    def order(self) -> list[int]:
        return sorted(self.seats)

    def _next(self, seat: int) -> int:
        order = self.order()
        after = [s for s in order if s > seat]
        return after[0] if after else order[0]

    def _player_action(self, msg: P.PlayerAction) -> None:
        t = self.seats.get(msg.seat)
        if t is None:
            t = self.seats[msg.seat] = SeatTrack(msg.seat, msg.name or f"seat{msg.seat}", msg.stack or 0)
        kind = msg.action.lower()
        if kind in BLIND_ACTIONS and msg.seat in self.blind_inferred:
            return  # already accounted for by blind inference
        new_stack = msg.stack_after if msg.stack_after is not None else msg.stack
        if msg.contribution_delta is not None:
            added = int(msg.contribution_delta)
        elif new_stack is not None:
            added = max(0, t.stack - int(new_stack))
        elif kind == "raise" and msg.amount is not None:
            added = max(0, int(msg.amount) - t.street_commit)
        else:
            added = int(msg.amount or 0)
        t.street_commit += added
        t.total_commit += added
        t.stack = int(new_stack) if new_stack is not None else max(0, t.stack - added)
        if kind == "fold":
            t.folded = True
        norm = {"all_in": "raise", "bet": "bet"}.get(kind, kind)
        if norm in BLIND_ACTIONS:
            return
        self.history.append((msg.seat, msg.street, norm, added, t.street_commit))

    # ------------------------------------------------------------ observation
    def observation(self, turn: P.YourTurn) -> tuple[Observation, dict[str, Any]]:
        if self.hand_id is None or self.hole is None or self.my_seat is None:
            raise StateDivergence("your_turn without an active hand / hole cards")
        if turn.hand_id and turn.hand_id != self.hand_id:
            raise StateDivergence("your_turn for a different hand")
        for p in turn.players:
            if p.seat in self.seats:
                self.seats[p.seat].stack = p.stack
        board = [P.card(c) for c in turn.community_cards] if turn.community_cards else self.board
        street = {0: Street.PREFLOP, 3: Street.FLOP, 4: Street.TURN, 5: Street.RIVER}.get(len(board))
        if street is None:
            raise UnsupportedState(f"unexpected board size {len(board)}")
        order = self.order()
        if self.my_seat not in order:
            raise StateDivergence("hero not in hand")
        idx = {s: i for i, s in enumerate(order)}
        n = len(order)
        if not 2 <= n <= 6:
            raise UnsupportedState(f"unsupported player count {n}")
        btn = idx.get(self.dealer, 0)
        me = self.seats[self.my_seat]
        valid = {v.action: v for v in turn.valid_actions}
        to_call = int(valid["call"].amount or 0) if "call" in valid else 0
        street_max = max(s.street_commit for s in self.seats.values())
        current_bet = max(street_max, me.street_commit + to_call)
        legal, ctx = legal_from_valid(valid, me.street_commit, me.stack, current_bet, turn)
        street_total = sum(s.street_commit for s in self.seats.values())
        convention = reconcile_pot(int(turn.pot), self.committed_total(), street_total)
        if convention is None:
            raise StateDivergence(f"pot {turn.pot} != reconstructed {self.committed_total()} (street {street_total})")
        ctx["pot_convention"] = convention
        seats = tuple(
            PublicSeat(
                seat=idx[s],
                player_id=self.seats[s].name,
                position=position_label((idx[s] - btn) % n, n),
                stack=self.seats[s].stack,
                street_commitment=self.seats[s].street_commit,
                total_commitment=self.seats[s].total_commit,
                folded=self.seats[s].folded,
                all_in=self.seats[s].stack == 0 and not self.seats[s].folded,
            )
            for s in order
        )
        hist = tuple(PublicAction(idx[s], st, k, a, tot) for (s, st, k, a, tot) in self.history if s in idx)
        obs = Observation(
            hand_id=self.hand_id,
            seat=idx[self.my_seat],
            player_id=me.name,
            position=position_label((idx[self.my_seat] - btn) % n, n),
            hole_cards=self.hole,
            board=tuple(board),
            street=street,
            button_seat=btn,
            small_blind=self.sb,
            big_blind=self.bb,
            ante=0,
            pot=int(turn.pot),
            current_bet=current_bet,
            to_call=min(to_call, me.stack) if to_call else 0,
            stack=me.stack,
            seats=seats,
            history=hist,
            legal=legal,
        )
        return obs, ctx


def legal_from_valid(
    valid: dict[str, P.ValidAction], my_street: int, my_stack: int, current_bet: int, turn: P.YourTurn
) -> tuple[LegalActions, dict[str, Any]]:
    """Platform valid_actions -> internal LegalActions (+ context for the reverse mapping).

    Conservative rules (never widen what the platform allows):
    - the internal raise range is ``[raise.min, raise.max]``; it is extended to the all-in
      total only when the platform's max already equals it or no max is given;
    - a short all-in that the platform reports as ``call`` stays a CALL (amount capped by stack);
    - ``all_in`` alone (no ``raise``) becomes a single-point raise range at the all-in total;
    - when the platform max is below the all-in total, ``all_in`` is not reachable by the agent
      (flag ``allin_unreachable``) instead of silently turning a raise into an all-in.
    """
    if not valid:
        raise UnsupportedState("empty valid_actions")
    unknown = set(valid) - {"fold", "check", "call", "raise", "all_in"}
    if unknown:
        raise UnsupportedState(f"unknown platform actions {sorted(unknown)}")
    can_check = "check" in valid
    call_raw = int(valid["call"].amount or 0) if "call" in valid else 0
    if "call" in valid and call_raw <= 0:
        raise UnsupportedState("call without a positive amount")
    call_amount = min(call_raw, my_stack) if my_stack > 0 else call_raw
    can_fold = "fold" in valid and not can_check
    allin_total = my_street + my_stack
    rmin = rmax = 0
    kind: ActionKind | None = None
    pmax: int | None = None
    allin_unreachable = False
    if "raise" in valid:
        v = valid["raise"]
        rmin = int(v.min if v.min is not None else (turn.min_raise or 0))
        pmax = int(v.max) if v.max is not None else (int(turn.max_raise) if turn.max_raise is not None else None)
        if pmax is None:
            rmax = allin_total
        elif pmax > allin_total:
            raise UnsupportedState(f"platform raise max {pmax} above all-in total {allin_total}")
        else:
            rmax = pmax
        allin_unreachable = "all_in" in valid and rmax < allin_total
        kind = ActionKind.BET if current_bet == 0 else ActionKind.RAISE
    elif "all_in" in valid:
        rmin = rmax = allin_total
        kind = ActionKind.BET if current_bet == 0 else ActionKind.RAISE
    if kind is not None and not (0 < rmin <= rmax):
        raise UnsupportedState(f"invalid raise bounds {rmin}..{rmax}")
    if kind is not None and rmax <= current_bet and "all_in" not in valid:
        raise UnsupportedState(f"raise-to {rmax} does not exceed current bet {current_bet}")
    legal = LegalActions(can_fold, can_check, call_amount, kind, rmin, rmax)
    ctx = {"valid": sorted(valid), "allin_total": allin_total, "raise_min": rmin, "raise_max": rmax,
           "platform_raise_max": pmax, "allin_unreachable": allin_unreachable}
    return legal, ctx


def to_platform(action: Action, legal: LegalActions, ctx: dict[str, Any]) -> tuple[str, int | None]:
    """Internal action -> (platform action, amount). Raises ValueError when not legal.

    The amount sent is always exactly the amount requested (raise-to) or the platform's own
    all-in; no rounding up, no clamping."""
    why = legal.why_illegal(action)
    if why is not None:
        raise ValueError(why)
    valid = set(ctx["valid"])
    k = action.kind
    if k is ActionKind.FOLD:
        return "fold", None
    if k is ActionKind.CHECK:
        return "check", None
    if k is ActionKind.CALL:
        return "call", None
    assert action.amount is not None
    amt = int(action.amount)
    if "all_in" in valid and amt == ctx["allin_total"]:
        return "all_in", None
    pmax = ctx["platform_raise_max"]
    if "raise" in valid and amt >= ctx["raise_min"] and (pmax is None or amt <= pmax):
        return "raise", amt
    raise ValueError("no platform action matches the requested raise")
