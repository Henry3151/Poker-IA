import random

import pytest

from poker_lab.agents.equity_agent import EquityAgent
from poker_lab.agents.heuristic import HeuristicAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.application.hand_runner import play_session
from poker_lab.domain.cards import parse_cards
from poker_lab.strategy.equity import exact_equity_heads_up, monte_carlo_equity, pot_odds
from poker_lab.strategy.ranges import class_rank_fraction, preflop_equity_table, top_classes

# Reference preflop all-in equities vs one random hand (widely published values).
KNOWN_VS_RANDOM = {"AsAd": 0.852, "KsKd": 0.824, "AsKs": 0.670, "7s2d": 0.346, "2s2d": 0.503}


@pytest.mark.parametrize("hand,expected", KNOWN_VS_RANDOM.items())
def test_preflop_vs_random_matches_reference(hand, expected):
    est = monte_carlo_equity(parse_cards(hand), [], 1, 6000, random.Random(1))
    assert abs(est.equity - expected) <= 4 * est.stderr + 0.005
    assert est.method == "monte_carlo" and est.samples == 6000


def test_aa_vs_kk_like_range():
    # AA vs a range that is only KK: ~81.9% (published)
    def only_kk(cards):
        return cards[0] >> 2 == 11 and cards[1] >> 2 == 11

    est = monte_carlo_equity(parse_cards("AsAd"), [], 1, 4000, random.Random(2), only_kk, max_rejections=2000)
    assert abs(est.equity - 0.819) <= 4 * est.stderr + 0.01


def test_exact_river_enumeration():
    nuts = exact_equity_heads_up(parse_cards("AsKs"), parse_cards("QsJsTs2d3c"))
    assert nuts.equity == 1.0 and nuts.samples == 990
    board_plays = exact_equity_heads_up(parse_cards("2c3d"), parse_cards("AsKdQhJcTs"))
    assert board_plays.equity < 1.0
    mc = monte_carlo_equity(parse_cards("8h8d"), parse_cards("Kc7d2h5s9c"), 1, 8000, random.Random(3))
    ex = exact_equity_heads_up(parse_cards("8h8d"), parse_cards("Kc7d2h5s9c"))
    assert abs(mc.equity - ex.equity) <= 4 * mc.stderr + 0.003


def test_multiway_equity_decreases():
    rng = random.Random(4)
    e1 = monte_carlo_equity(parse_cards("AsAd"), [], 1, 3000, rng).equity
    e5 = monte_carlo_equity(parse_cards("AsAd"), [], 5, 3000, rng).equity
    assert e5 < e1 and 0.45 < e5 < 0.55  # published AA vs 5 random ~49%


def test_pot_odds():
    assert pot_odds(0, 100) == 0
    assert pot_odds(50, 150) == pytest.approx(0.25)


def test_ranges():
    assert class_rank_fraction("AA") <= 6 / 1326 + 1e-9
    top = top_classes(0.05)
    assert "AA" in top and "72o" not in top
    assert class_rank_fraction("32o") > 0.97
    eq = preflop_equity_table()
    assert abs(eq["AA"] - 0.852) < 0.01 and abs(eq["72o"] - 0.346) < 0.01


def test_equity_agent_plays_legal_and_records_estimates():
    agents = [EquityAgent(f"e{i}", seed=i, samples=60) if i < 2 else RandomAgent(f"r{i}", seed=i) for i in range(6)]
    infos = []
    res = play_session(agents, 60, seed=9, on_hand=lambda rec: infos.extend(d.info for d in rec.decisions if d.player_id.startswith("e")))
    assert res.invalid_actions == 0
    assert infos and all("equity" in i and "samples" in i and "stderr" in i for i in infos)


def test_equity_agent_beats_random_benchmark():
    """Benchmark (not a proof): equity agent vs random agents over a fixed seed set."""
    agents = [EquityAgent("eq", seed=1, samples=80)] + [RandomAgent(f"r{i}", seed=i) for i in range(1, 6)]
    res = play_session(agents, 300, seed=21)
    assert res.net_by_agent["eq"] > 0


def test_heuristic_beats_random_benchmark():
    agents = [HeuristicAgent("h", seed=1)] + [RandomAgent(f"r{i}", seed=i) for i in range(1, 6)]
    res = play_session(agents, 400, seed=22)
    assert res.net_by_agent["h"] > 0
