"""Closed-form poker math used by agents and analytics.

All functions are pure and documented with their assumptions. EV formulas here are
*single-decision* approximations (no future betting), clearly different from equity.
"""

from __future__ import annotations

from collections.abc import Sequence

from poker_lab.engine.evaluator import category_of, evaluate


def pot_odds(to_call: int | float, pot: int | float) -> float:
    """Share of the final pot the caller contributes: to_call / (pot + to_call)."""
    return 0.0 if to_call <= 0 else float(to_call) / float(pot + to_call)


def ev_call(equity: float, pot: float, to_call: float) -> float:
    """EV (chips, relative to folding) of calling and checking down: eq*(pot+call) - call."""
    return equity * (pot + to_call) - to_call


def breakeven_fold_equity(bet: float, pot: float) -> float:
    """Fold probability a pure bluff needs to break even: bet / (pot + bet)."""
    return 0.0 if bet <= 0 else bet / (pot + bet)


def ev_bet(fold_prob: float, equity_when_called: float, pot: float, bet: float, call: float | None = None) -> float:
    """EV (chips, relative to checking-and-giving-up) of a bet that is either folded to or called.

    ``call`` defaults to ``bet`` (opponent matches the bet). When called we check down.
    """
    c = bet if call is None else call
    called_ev = equity_when_called * (pot + bet + c) - bet
    return fold_prob * pot + (1.0 - fold_prob) * called_ev


def spr(effective_stack: float, pot: float) -> float:
    """Stack-to-pot ratio at the start of a street."""
    return float("inf") if pot <= 0 else effective_stack / pot


def count_outs(hole: Sequence[int], board: Sequence[int], min_category: int | None = None) -> dict[str, float | int]:
    """Count one-card outs on the flop or turn.

    An out is an unseen card after which (a) our hand category rises, (b) reaches at least
    ``min_category`` when given (e.g. STRAIGHT for a straight draw, FLUSH for a flush draw),
    and (c) the improvement uses our hole cards (a card that only improves the board does not
    count). It ignores whether the improved hand actually wins (reverse implied odds), so
    "outs" here are an upper bound on clean outs. Returns the exact probability of hitting on
    the next card, the exact probability by the river (two cards to come on the flop), and the
    rule-of-2/4 approximation for comparison.
    """
    if len(board) not in (3, 4):
        raise ValueError("outs are defined on the flop or the turn")
    current = category_of(evaluate([*hole, *board]))
    unseen = [c for c in range(52) if c not in set(hole) | set(board)]
    outs_cards = []
    for c in unseen:
        new_board = [*board, c]
        cat = category_of(evaluate([*hole, *new_board]))
        if cat <= current or (min_category is not None and cat < min_category):
            continue
        board_cat = category_of(evaluate(new_board)) if len(new_board) == 5 else _board_category(new_board)
        if board_cat >= cat:
            continue  # improvement is on the board, shared by everyone
        outs_cards.append(c)
    outs = len(outs_cards)
    n = len(unseen)
    p_next = outs / n
    if len(board) == 3:
        p_river = 1 - ((n - outs) / n) * ((n - 1 - outs) / (n - 1))
        rule = outs * 4 / 100.0
    else:
        p_river = p_next
        rule = outs * 2 / 100.0
    return {
        "outs": outs,
        "unseen": n,
        "p_next_card": round(p_next, 5),
        "p_by_river": round(p_river, 5),
        "rule_of_2_4": round(min(rule, 1.0), 5),
    }


def _board_category(board: Sequence[int]) -> int:
    counts: dict[int, int] = {}
    for c in board:
        counts[c >> 2] = counts.get(c >> 2, 0) + 1
    m = sorted(counts.values(), reverse=True)
    if m[0] >= 4:
        return 7
    if m[0] == 3:
        return 3
    if m[0] == 2:
        return 2 if len(m) > 1 and m[1] == 2 else 1
    return 0
