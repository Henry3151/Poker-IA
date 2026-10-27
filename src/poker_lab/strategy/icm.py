"""Independent Chip Model (Malmuth-Harville) and tournament-phase helpers.

ICM converts chip stacks into expected prize equity assuming each player's chance of
finishing first is proportional to their stack, applied recursively. It ignores skill,
position and blinds — a standard but imperfect model, so ICM-based numbers are
*estimates*, never facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache


def icm_equities(stacks: Sequence[int | float], payouts: Sequence[float]) -> list[float]:
    """Expected payout per player. Exact recursion over the paid places only.

    The memoised recursion visits sum_{j<k} C(n, j) states (k = paid places), which is small
    for typical MTT payouts. Players with zero chips get nothing.
    """
    n = len(stacks)
    k = min(len(payouts), n)
    pay = tuple(float(p) for p in payouts[:k])
    st = tuple(float(s) for s in stacks)
    from math import comb

    if sum(comb(n, j) for j in range(k)) > 300_000:
        raise ValueError("ICM recursion too large; reduce players or paid places")

    @cache
    def rec(remaining: frozenset[int], place: int) -> tuple[float, ...]:
        out = [0.0] * n
        if place >= k or not remaining:
            return tuple(out)
        total = sum(st[i] for i in remaining)
        if total <= 0:
            return tuple(out)
        for i in remaining:
            if st[i] <= 0:
                continue
            p = st[i] / total
            out[i] += p * pay[place]
            sub = rec(remaining - {i}, place + 1)
            for j in range(n):
                out[j] += p * sub[j]
        return tuple(out)

    return list(rec(frozenset(range(n)), 0))


def icm_call_decision(
    hero_total: int,
    hero_committed: int,
    villain_total: int,
    dead_chips: int,
    other_stacks: Sequence[int],
    payouts: Sequence[float],
    equity: float,
) -> dict[str, float]:
    """ICM $EV of calling an all-in vs folding, hero vs one villain.

    ``hero_total``/``villain_total``: chips each had at the start of the hand.
    ``hero_committed``: chips hero already put in (lost on a fold).
    ``dead_chips``: chips in the pot from *other* players (folded blinds/antes).
    ``other_stacks``: every other remaining player's stack (any table), unchanged.
    """
    m = min(hero_total, villain_total)
    others = list(other_stacks)

    def eq(h: float, v: float) -> float:
        return icm_equities([h, v, *others], payouts)[0]

    ev_fold = eq(hero_total - hero_committed, villain_total + hero_committed + dead_chips)
    ev_win = eq(hero_total + m + dead_chips, villain_total - m)
    ev_lose = eq(hero_total - m, villain_total + m + dead_chips)
    ev_call = equity * ev_win + (1 - equity) * ev_lose
    icm_be = (ev_fold - ev_lose) / (ev_win - ev_lose) if ev_win > ev_lose else 1.0
    icm_be = max(0.0, min(1.0, icm_be))
    to_call = m - hero_committed
    final_pot = 2 * m + dead_chips
    chip_be = to_call / final_pot if final_pot > 0 else 0.0
    return {
        "ev_fold": ev_fold,
        "ev_call": ev_call,
        "icm_breakeven_equity": icm_be,
        "chip_breakeven_equity": chip_be,
        "risk_premium": icm_be - chip_be,
    }


def tournament_phase(players_remaining: int, entrants: int, paid_places: int, avg_stack_bb: float, table_size: int = 6) -> str:
    """Coarse phase label used for reporting and strategy adjustments.

    early: >60% of the field left and avg stack > 40bb; bubble: within ~15% (min 1) of the
    money; itm: in the money, before the final table; final_table: <= table_size left.
    """
    if players_remaining <= 1:
        return "finished"
    if players_remaining <= table_size:
        return "final_table"
    if players_remaining <= paid_places:
        return "itm"
    if players_remaining - paid_places <= max(1, round(0.15 * paid_places)):
        return "bubble"
    if players_remaining > 0.6 * entrants and avg_stack_bb > 40:
        return "early"
    return "middle"
