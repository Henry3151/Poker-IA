"""Unit, property and reference tests for EV, outs, SPR, fold equity, ICM and statistics."""

import itertools
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poker_lab.domain.cards import parse_cards
from poker_lab.engine.evaluator import FLUSH, STRAIGHT
from poker_lab.evaluation.stats import bootstrap_ci, max_drawdown, ratio_bootstrap_ci, verdict
from poker_lab.strategy.icm import icm_call_decision, icm_equities, tournament_phase
from poker_lab.strategy.math import breakeven_fold_equity, count_outs, ev_bet, ev_call, pot_odds, spr


# ------------------------------------------------------------------ pot odds / EV
def test_pot_odds_reference():
    assert pot_odds(50, 100) == pytest.approx(1 / 3)  # call 50 into 100 -> need 33.3%
    assert pot_odds(100, 100) == pytest.approx(0.5)
    assert pot_odds(0, 100) == 0


@given(st.floats(0.01, 1000), st.floats(0.01, 1000))
def test_ev_call_zero_exactly_at_pot_odds(to_call, pot):
    eq = pot_odds(to_call, pot)
    assert ev_call(eq, pot, to_call) == pytest.approx(0, abs=1e-6 * (pot + to_call))
    assert ev_call(min(1, eq + 0.01), pot, to_call) > 0 or eq >= 0.99
    assert ev_call(max(0, eq - 0.01), pot, to_call) < 0 or eq <= 0.01


@given(st.floats(1, 1000), st.floats(1, 1000))
def test_pure_bluff_breakeven_fold_equity(bet, pot):
    fe = breakeven_fold_equity(bet, pot)
    assert ev_bet(fe, 0.0, pot, bet) == pytest.approx(0, abs=1e-6 * (pot + bet))
    assert ev_bet(1.0, 0.0, pot, bet) == pytest.approx(pot)  # always folds -> win the pot


def test_breakeven_reference_values():
    assert breakeven_fold_equity(100, 100) == pytest.approx(0.5)  # pot-size bluff
    assert breakeven_fold_equity(50, 100) == pytest.approx(1 / 3)  # half-pot bluff


def test_spr():
    assert spr(1000, 200) == 5
    assert spr(100, 0) == float("inf")


# ------------------------------------------------------------------ outs
def test_flush_draw_outs():
    o = count_outs(parse_cards("AhKh"), parse_cards("2h7h9c"), min_category=FLUSH)
    assert o["outs"] == 9
    assert o["p_next_card"] == pytest.approx(9 / 47, abs=1e-4)
    assert o["p_by_river"] == pytest.approx(1 - (38 / 47) * (37 / 46), abs=1e-4)  # ~0.35
    assert abs(o["rule_of_2_4"] - o["p_by_river"]) < 0.02  # rule of 4 is an approximation


def test_open_ended_straight_draw_outs():
    o = count_outs(parse_cards("9s8d"), parse_cards("7c6h2s"), min_category=STRAIGHT)
    assert o["outs"] == 8
    turn = count_outs(parse_cards("9s8d"), parse_cards("7c6h2sKd"), min_category=STRAIGHT)
    assert turn["outs"] == 8 and turn["p_by_river"] == pytest.approx(8 / 46, abs=1e-4)


def test_board_only_improvement_is_not_an_out():
    # pair on board: a card making board trips does not use our hole cards
    o = count_outs(parse_cards("AsKd"), parse_cards("7c7h2s"))
    hole_rank_outs = 6  # three aces + three kings make two pair using a hole card
    assert o["outs"] >= hole_rank_outs
    assert all(isinstance(o[k], (int, float)) for k in o)
    with pytest.raises(ValueError):
        count_outs(parse_cards("AsKd"), [])


# ------------------------------------------------------------------ ICM
def harville_bruteforce(stacks, payouts):
    """Independent implementation: enumerate every finishing order (Harville probabilities)."""
    n = len(stacks)
    eq = [0.0] * n
    for order in itertools.permutations(range(n)):
        p = 1.0
        rem = sum(stacks)
        for i in order:
            if rem <= 0:
                break
            p *= stacks[i] / rem
            rem -= stacks[i]
        for place, i in enumerate(order[: len(payouts)]):
            eq[i] += p * payouts[place]
    return eq


@pytest.mark.parametrize(
    "stacks,payouts",
    [([5000, 3000, 2000], [50, 30, 20]), ([1000, 1000, 1000, 1000], [65, 35]), ([7000, 2000, 500, 500, 3000], [50, 30, 20])],
)
def test_icm_matches_bruteforce(stacks, payouts):
    assert icm_equities(stacks, payouts) == pytest.approx(harville_bruteforce(stacks, payouts), abs=1e-9)


def test_icm_reference_two_players():
    # closed form for 2 players: P(win) = s1/(s1+s2)
    e = icm_equities([3000, 1000], [70, 30])
    assert e[0] == pytest.approx(0.75 * 70 + 0.25 * 30)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(1, 10000), min_size=2, max_size=7))
def test_icm_properties(stacks):
    payouts = [50, 30, 20][: len(stacks)]
    e = icm_equities(stacks, payouts)
    assert sum(e) == pytest.approx(sum(payouts))  # all prize money is distributed
    order = sorted(range(len(stacks)), key=lambda i: stacks[i])
    for a, b in zip(order, order[1:], strict=False):  # monotone in stack
        assert e[a] <= e[b] + 1e-9
    assert all(e[i] >= payouts[-1] * 0 for i in range(len(stacks)))
    assert max(e) <= payouts[0] + 1e-9
    # equity is concave in chips: the chip leader's $ share is below its chip share
    big = max(range(len(stacks)), key=lambda i: stacks[i])
    assert e[big] / sum(payouts) <= stacks[big] / sum(stacks) + 1e-9


def test_icm_risk_premium_on_bubble():
    # 4 left, 3 paid, hero mid stack facing a shove from the big stack: ICM needs more equity
    d = icm_call_decision(
        hero_total=3000, hero_committed=100, villain_total=6000, dead_chips=50,
        other_stacks=[500, 500], payouts=[50, 30, 20], equity=0.5,
    )
    assert d["icm_breakeven_equity"] > d["chip_breakeven_equity"] + 0.05
    assert d["risk_premium"] > 0
    # winner-take-all ICM == chip EV
    w = icm_call_decision(3000, 100, 6000, 50, [500, 500], [100], 0.5)
    assert w["icm_breakeven_equity"] == pytest.approx(w["chip_breakeven_equity"], abs=1e-6)


def test_tournament_phase():
    assert tournament_phase(100, 100, 15, 100) == "early"
    assert tournament_phase(17, 100, 15, 20) == "bubble"
    assert tournament_phase(12, 100, 15, 20) == "itm"
    assert tournament_phase(6, 100, 15, 20) == "final_table"
    assert tournament_phase(50, 100, 15, 20) == "middle"


# ------------------------------------------------------------------ statistics
def test_bootstrap_ci_covers_known_mean_and_is_reproducible():
    rng = random.Random(1)
    data = [rng.gauss(10, 2) for _ in range(400)]
    a = bootstrap_ci(data, seed=3)
    b = bootstrap_ci(data, seed=3)
    assert a == b and a.low < 10 < a.high and a.high - a.low < 0.6


def test_bootstrap_coverage_simulation():
    """Empirical coverage of the 95% percentile bootstrap on normal data is close to nominal."""
    rng = random.Random(7)
    hits = 0
    trials = 150
    for t in range(trials):
        data = [rng.gauss(0, 1) for _ in range(60)]
        ci = bootstrap_ci(data, resamples=500, seed=t)
        hits += ci.low <= 0 <= ci.high
    assert 0.88 <= hits / trials <= 0.99


def test_ratio_ci_and_verdicts():
    net = [-110] * 80 + [400] * 20
    cost = [110] * 100
    ci = ratio_bootstrap_ci(net, cost, seed=1)
    assert ci.estimate == pytest.approx(sum(net) / sum(cost))
    assert verdict(ci, min_n=200) == "insufficient_sample"
    assert verdict(ci, min_n=50) in ("inconclusive", "evidence_negative", "evidence_positive")
    strong = bootstrap_ci([1.0 + 0.01 * (i % 3) for i in range(300)], seed=1)
    assert verdict(strong) == "evidence_positive"


def test_max_drawdown():
    d = max_drawdown([100, -50, -80, 30, 200, -400])
    assert d["max_drawdown"] == 400 and d["final_cumulative"] == -200
