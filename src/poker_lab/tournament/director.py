"""Multi-table tournament (MTT) director.

Simulation model (documented in docs/TOURNAMENT_RULES.md):
- Players are seated at random (seeded) into ceil(N / table_size) balanced tables.
- Play proceeds in *rounds*: in each round every table with 2+ players plays one hand.
- Blind level = round // hands_per_level. After the last configured level, blinds keep
  growing by 1.5x per level so a tournament always terminates.
- Players busted in the same round finish in order of their stack at the start of the
  hand (larger stack = better place); exact ties are broken by seeded random order.
- After each round tables are broken when the remaining players fit in fewer tables, then
  balanced so table sizes differ by at most one. A moved player takes a random free seat.
- Button: simple moving button to the next occupied seat (no dead-button rule).
- Chip integrity is asserted after every hand and every move.
"""

from __future__ import annotations

import math
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from poker_lab.agents.base import Agent
from poker_lab.application.hand_runner import HandRecord, play_hand
from poker_lab.domain.observation import TournamentInfo
from poker_lab.domain.seeds import derive_seed
from poker_lab.engine.hand import HandEngine
from poker_lab.strategy.icm import tournament_phase
from poker_lab.tournament.config import BlindLevel, TournamentConfig, compute_payouts


class ChipIntegrityError(AssertionError):
    pass


@dataclass(slots=True)
class Entry:
    entry_id: str
    label: str
    agent: Agent
    stack: int
    table: int | None = None
    seat: int | None = None
    place: int | None = None
    payout: int = 0
    hands_played: int = 0
    eliminated_round: int | None = None
    eliminated_hand_id: str | None = None
    entries_count: int = 1
    reentries: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class Table:
    number: int
    seats: list[str | None]  # entry_id per physical seat
    button_seat: int = -1

    def occupied(self) -> list[int]:
        return [i for i, e in enumerate(self.seats) if e is not None]

    def count(self) -> int:
        return len(self.occupied())


@dataclass(slots=True)
class TournamentEvent:
    seq: int
    type: str
    round: int
    payload: dict[str, Any]


@dataclass(slots=True)
class HandContext:
    tournament_id: str
    table_number: int
    hand_number: int  # global sequence across the tournament
    round: int
    level_index: int
    level: BlindLevel
    seat_entry_ids: list[str]  # compact seat order used by the engine
    physical_seats: list[int]
    phase: str = "middle"
    players_remaining: int = 0


@dataclass(slots=True)
class TournamentResult:
    tournament_id: str
    seed: int
    entries: list[Entry]
    rounds: int
    hands_played: int
    prize_pool: int
    payouts: list[int]
    events: list[TournamentEvent] = field(default_factory=list)
    total_entries: int = 0

    def standings(self) -> list[Entry]:
        return sorted(self.entries, key=lambda e: e.place or 10**9)

    @property
    def winner(self) -> Entry:
        return self.standings()[0]


HandCallback = Callable[[HandContext, HandRecord], None]
EventCallback = Callable[[TournamentEvent], None]


def level_at(cfg: TournamentConfig, index: int) -> BlindLevel:
    if index < len(cfg.levels):
        return cfg.levels[index]
    last = cfg.levels[-1]
    k = index - len(cfg.levels) + 1
    f = 1.5**k
    return BlindLevel(
        small_blind=max(1, int(last.small_blind * f)),
        big_blind=max(1, int(last.big_blind * f)),
        ante=int(last.ante * f),
    )


class TournamentDirector:
    def __init__(
        self,
        config: TournamentConfig,
        entrants: list[tuple[str, Agent]],
        seed: int,
        tournament_id: str | None = None,
        on_hand: HandCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        if len(entrants) < 2:
            raise ValueError("at least two entrants")
        if len({label for label, _ in entrants}) != len(entrants):
            raise ValueError("entrant labels must be unique")
        if len({id(a) for _, a in entrants}) != len(entrants):
            raise ValueError("each entrant needs its own agent instance")
        self.cfg = config
        self.seed = seed
        self.tournament_id = tournament_id or str(uuid.uuid4())
        self.rng = random.Random(derive_seed(seed, "director"))
        self.entries_list = [
            Entry(entry_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.tournament_id}/{label}")), label=label, agent=agent, stack=config.starting_stack)
            for label, agent in entrants
        ]
        self.by_id = {e.entry_id: e for e in self.entries_list}
        self.total_chips = config.starting_stack * len(entrants)
        self.on_hand = on_hand
        self.on_event = on_event
        self.events: list[TournamentEvent] = []
        self.tables: dict[int, Table] = {}
        self.round = 0
        self.hand_counter = 0
        self.next_place = len(entrants)
        self.payouts: list[int] = []
        self.prize_pool = 0

    # ------------------------------------------------------------------ events
    def _event(self, etype: str, payload: dict[str, Any]) -> None:
        ev = TournamentEvent(len(self.events), etype, self.round, payload)
        self.events.append(ev)
        if self.on_event:
            self.on_event(ev)

    def _check_chips(self, where: str) -> None:
        alive = sum(e.stack for e in self.entries_list)
        if alive != self.total_chips:
            raise ChipIntegrityError(f"chip integrity violated at {where}: {alive} != {self.total_chips}")

    # ------------------------------------------------------------------ seating
    def _seat_initial(self) -> None:
        n = len(self.entries_list)
        n_tables = math.ceil(n / self.cfg.table_size)
        order = list(self.entries_list)
        self.rng.shuffle(order)
        for k in range(n_tables):
            self.tables[k + 1] = Table(k + 1, [None] * self.cfg.table_size)
        for i, e in enumerate(order):
            t = self.tables[i % n_tables + 1]
            free = [s for s, x in enumerate(t.seats) if x is None]
            seat = self.rng.choice(free)
            t.seats[seat] = e.entry_id
            e.table, e.seat = t.number, seat
        for t in self.tables.values():
            t.button_seat = self.rng.choice(t.occupied())
        self._event(
            "tournament_started",
            {"entrants": n, "tables": n_tables, "seating": {e.label: [e.table, e.seat] for e in self.entries_list}},
        )

    def _move(self, entry_id: str, src: Table, dst: Table, reason: str) -> None:
        e = self.by_id[entry_id]
        assert e.seat is not None
        src.seats[e.seat] = None
        free = [s for s, x in enumerate(dst.seats) if x is None]
        if not free:
            raise RuntimeError("destination table full")
        seat = self.rng.choice(free)
        dst.seats[seat] = entry_id
        self._event(
            "player_moved",
            {"entry": e.label, "from_table": src.number, "from_seat": e.seat, "to_table": dst.number, "to_seat": seat, "reason": reason},
        )
        e.table, e.seat = dst.number, seat

    def _next_bb_entry(self, t: Table) -> str:
        occ = t.occupied()
        # player who would post the big blind next hand (fairest single player to move)
        nxt = [s for s in occ if s > t.button_seat] + [s for s in occ if s <= t.button_seat]
        idx = 1 if len(occ) == 2 else 2
        seat = nxt[min(idx, len(nxt) - 1)]
        sid = t.seats[seat]
        assert sid is not None
        return sid

    def _rebalance(self) -> None:
        remaining = sum(1 for e in self.entries_list if e.place is None)
        # break tables while players fit in fewer tables
        while len(self.tables) > max(1, math.ceil(remaining / self.cfg.table_size)):
            victim = min(self.tables.values(), key=lambda t: (t.count(), -t.number))
            del self.tables[victim.number]
            for seat in victim.occupied():
                eid = victim.seats[seat]
                assert eid is not None
                dst = min(self.tables.values(), key=lambda t: (t.count(), t.number))
                self._move(eid, victim, dst, "table_broken")
            self._event("table_broken", {"table": victim.number})
        # balance so sizes differ by at most one
        while True:
            big = max(self.tables.values(), key=lambda t: (t.count(), -t.number))
            small = min(self.tables.values(), key=lambda t: (t.count(), t.number))
            if big.count() - small.count() <= 1:
                break
            self._move(self._next_bb_entry(big), big, small, "balance")
        self._check_chips("rebalance")

    # ------------------------------------------------------------------ play
    def _public_info(self, t: Table, level_index: int, level: BlindLevel) -> TournamentInfo:
        alive = [e for e in self.entries_list if e.place is None]
        avg = sum(e.stack for e in alive) / max(1, len(alive))
        others = tuple(sorted((e.stack for e in alive if e.table != t.number), reverse=True))
        return TournamentInfo(
            entrants=len(self.entries_list),
            players_remaining=len(alive),
            paid_places=len(self.payouts),
            payouts=tuple(self.payouts),
            level=level_index + 1,
            phase=tournament_phase(len(alive), len(self.entries_list), len(self.payouts), avg / level.big_blind, self.cfg.table_size),
            average_stack=round(avg, 1),
            other_table_stacks=others,
        )

    def _play_table_hand(self, t: Table, level_index: int, level: BlindLevel) -> list[tuple[Entry, int]]:
        occ = t.occupied()
        nxt = [s for s in occ if s > t.button_seat] + [s for s in occ if s <= t.button_seat]
        t.button_seat = nxt[0]
        seats_in_order = occ  # physical order
        ids = [t.seats[s] for s in seats_in_order]
        entries = [self.by_id[i] for i in ids if i is not None]
        button_idx = seats_in_order.index(t.button_seat)
        self.hand_counter += 1
        hand_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.tournament_id}/hand/{self.hand_counter}"))
        engine = HandEngine(
            [(e.label, e.stack) for e in entries],
            button=button_idx,
            small_blind=level.small_blind,
            big_blind=level.big_blind,
            ante=level.ante,
            seed=derive_seed(self.seed, "hand", self.hand_counter),
            hand_id=hand_id,
        )
        info = self._public_info(t, level_index, level)
        rec = play_hand(
            engine,
            [e.agent for e in entries],
            latency_budget_ms=self.cfg.latency_budget_ms,
            tournament_info=info,
        )
        start = [e.stack for e in entries]
        for e, s in zip(entries, rec.result.ending_stacks, strict=True):
            e.stack = s
            e.hands_played += 1
        ctx = HandContext(
            self.tournament_id,
            t.number,
            self.hand_counter,
            self.round,
            level_index,
            level,
            [e.entry_id for e in entries],
            seats_in_order,
            info.phase,
            info.players_remaining,
        )
        if self.on_hand:
            self.on_hand(ctx, rec)
        busted = []
        for e, st in zip(entries, start, strict=True):
            if e.stack == 0:
                e.eliminated_hand_id = hand_id
                busted.append((e, st))
        for e, _ in busted:
            assert e.seat is not None
            t.seats[e.seat] = None
        return busted

    def _total_entries(self) -> int:
        return sum(e.entries_count for e in self.entries_list)

    def _recompute_payouts(self) -> None:
        self.prize_pool = self.cfg.buy_in * self._total_entries()
        self.payouts = compute_payouts(self.prize_pool, self.cfg.payout_percentages, len(self.entries_list))

    def _reenter(self, e: Entry, level_index: int) -> None:
        e.entries_count += 1
        e.stack = self.cfg.starting_stack
        self.total_chips += self.cfg.starting_stack
        e.reentries.append({"entry_number": e.entries_count, "round": self.round, "level": level_index + 1, "hand_id": e.eliminated_hand_id})
        e.eliminated_hand_id = None
        candidates = [t for t in self.tables.values() if t.count() < self.cfg.table_size]
        if candidates:
            dst = min(candidates, key=lambda t: (t.count(), t.number))
        else:
            num = max(self.tables) + 1 if self.tables else 1
            dst = self.tables[num] = Table(num, [None] * self.cfg.table_size)
        free = [s for s, x in enumerate(dst.seats) if x is None]
        seat = self.rng.choice(free)
        dst.seats[seat] = e.entry_id
        e.table, e.seat = dst.number, seat
        if dst.button_seat < 0:
            dst.button_seat = seat
        self._recompute_payouts()
        self._event("player_reentered", {"entry": e.label, "entry_number": e.entries_count, "to_table": dst.number, "to_seat": seat})

    def run(self) -> TournamentResult:
        self._seat_initial()
        self._check_chips("start")
        self._recompute_payouts()
        current_level = -1
        while sum(1 for e in self.entries_list if e.place is None) > 1:
            if self.round >= self.cfg.max_rounds:
                raise RuntimeError("max_rounds exceeded")
            level_index = self.round // self.cfg.hands_per_level
            level = level_at(self.cfg, level_index)
            if level_index != current_level:
                current_level = level_index
                self._event("level_started", {"level": level_index + 1, **level.model_dump()})
            busted_round: list[tuple[Entry, int]] = []
            for tn in sorted(self.tables):
                t = self.tables[tn]
                if t.count() >= 2:
                    busted_round.extend(self._play_table_hand(t, level_index, level))
            self._check_chips(f"round {self.round}")
            # finishing order for this round: smaller starting stack busts first (worse place)
            tiebreak = {e.entry_id: self.rng.random() for e, _ in busted_round}
            for e, st in sorted(busted_round, key=lambda x: (x[1], tiebreak[x[0].entry_id])):
                if level_index < self.cfg.reentry_levels and e.entries_count < self.cfg.max_entries:
                    self._reenter(e, level_index)
                    continue
                e.place = self.next_place
                e.eliminated_round = self.round
                self.next_place -= 1
                self._event(
                    "player_eliminated",
                    {"entry": e.label, "place": e.place, "hand_id": e.eliminated_hand_id, "start_stack": st},
                )
            self.round += 1
            if sum(1 for e in self.entries_list if e.place is None) > 1:
                self._rebalance()
        winner = next(e for e in self.entries_list if e.place is None)
        winner.place = 1
        payouts = self.payouts
        prize_pool = self.prize_pool
        for e in self.entries_list:
            assert e.place is not None
            e.payout = payouts[e.place - 1] if e.place <= len(payouts) else 0
        places = sorted(e.place for e in self.entries_list if e.place is not None)
        if places != list(range(1, len(self.entries_list) + 1)):
            raise AssertionError("places are not a permutation")
        if winner.stack != self.total_chips:
            raise ChipIntegrityError("winner does not hold all chips")
        self._event(
            "tournament_completed",
            {"winner": winner.label, "rounds": self.round, "hands": self.hand_counter, "prize_pool": prize_pool},
        )
        return TournamentResult(
            self.tournament_id,
            self.seed,
            self.entries_list,
            self.round,
            self.hand_counter,
            prize_pool,
            payouts,
            self.events,
            self._total_entries(),
        )
