import random

import pytest

from poker_lab.agents.base import Agent
from poker_lab.agents.hybrid import HybridAgent
from poker_lab.agents.policy_agent import PolicyAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.application.hand_runner import play_hand, play_session
from poker_lab.domain.actions import Action
from poker_lab.domain.cards import parse_cards
from poker_lab.engine.hand import HandEngine
from poker_lab.strategy.postflop_ranges import betting_filter
from poker_lab.strategy.preflop_model import ClassEquity, open_fraction, top_range
from poker_lab.strategy.ranges import preflop_equity_table
from poker_lab.training.games import PushFoldGame
from poker_lab.training.pushfold_tables import build_table
from poker_lab.training.pushfold_trainer import train_pushfold
from tests.engine.helpers import make_deck

from .test_information_leakage import _hero_decisions, _swap_opponent_cards


@pytest.fixture(scope="module")
def table():
    return build_table(samples=24, seed=5)


@pytest.fixture(scope="module")
def ckpt_v2(table):
    ctx = [(0.0, 0.0), (0.125, 0.0), (0.125, 0.5)]
    return train_pushfold(table, 3000, seed=3, stacks=[5.0, 10.0, 15.0, 20.0], contexts=ctx, evaluate=False).checkpoint


def hybrid(ckpt, table, seed=1):
    return HybridAgent(ckpt, table, "hero", seed=seed, samples=40)


def test_pushfold_game_with_ante_and_dead_money(table):
    g = PushFoldGame(10, table["classes"], table["equity"], table["weights"], ante_bb=0.125, dead_bb=0.5)
    o = (0, 1)
    assert g.utility(("f",), o) == pytest.approx(-0.625)
    assert g.utility(("p", "f"), o) == pytest.approx(1 + 0.125 + 0.5)
    e = table["equity"][0][1]
    assert g.utility(("p", "c"), o) == pytest.approx(e * (20 + 0.5) - 10)
    with pytest.raises(ValueError):
        PushFoldGame(1.05, table["classes"], table["equity"], table["weights"], ante_bb=0.125)


def test_dead_money_widens_pushing(ckpt_v2):
    pol = ckpt_v2.policy

    def pct(key):
        return sum(pol.sb_push[key].values())

    assert pct("10|a0.125|d0.5") > pct("10|a0|d0")  # more dead money -> wider shoves
    assert set(pol.context_table()) == set(pol.sb_push)


def test_policy_context_selection(ckpt_v2):
    a = PolicyAgent(ckpt_v2, "p", seed=1, fallback_samples=20)
    assert a._bucket(10.2, 0.125, 0.5) == "10|a0.125|d0.5"
    assert a._bucket(9.0, 0.0, 0.0) == "10|a0|d0"
    assert a._bucket(14.0, 0.12, 0.1) == "15|a0.125|d0"
    assert a._bucket(40.0, 0.0, 0.0) is None


def test_eq_vs_full_range_matches_vs_random(table):
    ce = ClassEquity.from_table(table)
    ref = preflop_equity_table()
    full = {c: 1.0 for c in table["classes"]}
    for cls in ("AA", "KQs", "72o", "55"):
        eq, mass = ce.eq_vs_range(cls, full)
        assert abs(eq - ref[cls]) < 0.03 and mass == pytest.approx(1.0)


def test_shove_ev_properties(table):
    ce = ClassEquity.from_table(table)
    everything = {c: 1.0 for c in table["classes"]}
    nothing: dict[str, float] = {}
    # nobody calls -> win the pot
    assert ce.shove_ev("72o", pot_bb=2.5, my_posted_bb=0.5, my_total_bb=10, callers=[(10, 1, nothing)]) == pytest.approx(2.5)
    # AA vs any calling range is profitable; 72o vs an always-calling deep player is not
    assert ce.shove_ev("AA", pot_bb=1.5, my_posted_bb=0.0, my_total_bb=20, callers=[(20, 1, everything)]) > 0
    assert ce.shove_ev("72o", pot_bb=1.5, my_posted_bb=0.0, my_total_bb=20, callers=[(20, 1, everything)]) < 0


def test_open_fraction_monotone():
    vals = [open_fraction(k) for k in range(1, 9)]
    assert vals == sorted(vals, reverse=True)
    assert "AA" in top_range(0.02) and "72o" not in top_range(0.5)


def test_betting_filter_keeps_made_hands_and_draws():
    board = parse_cards("Kh9h2c")
    flt = betting_filter(board, 0.0, random.Random(1))
    assert flt(tuple(parse_cards("KsQd")))  # top pair
    assert flt(tuple(parse_cards("Ah5h")))  # flush draw
    assert not flt(tuple(parse_cards("JcTd")))  # 9-T-J-K is only a gutshot: not kept with bluff_rate 0
    assert betting_filter(parse_cards("Qh9h2c"), 0.0, random.Random(1))(tuple(parse_cards("JcTd")))  # OESD
    assert not flt(tuple(parse_cards("4d3s")))  # air with bluff_rate 0
    always = betting_filter(board, 1.0, random.Random(1))
    assert always(tuple(parse_cards("4d3s")))


def test_hybrid_routing(ckpt_v2, table):
    h = hybrid(ckpt_v2, table)
    # HU, SB first-in at 10bb with ante -> trained push/fold v2
    e = HandEngine([("hero", 1000), ("v", 1000)], 0, 50, 100, ante=12, deck=make_deck(["AsAd", "7c2d"]))
    h.act(e.observation(0))
    assert h.last_info["component"] == "pushfold_v2"
    # deep 6-max UTG with 72o -> fold, BTN with AKo -> open 2.2bb
    e2 = HandEngine([(f"p{i}", 20000) for i in range(6)], 0, 50, 100, deck=make_deck(["As3d", "Kc4d", "Qs5d", "7h2c", "9s9d", "AhKd"]))
    assert e2.to_act == 3
    assert h.act(e2.observation(3)).kind.value == "fold"
    for seat in (3, 4, 5):
        e2.apply(seat, Action.fold())
    a = h.act(e2.observation(0))
    assert a.kind.value == "raise" and a.amount == 220 and h.last_info["component"] == "first_in_open"


def test_hybrid_never_limps_first_in(ckpt_v2, table):
    h = hybrid(ckpt_v2, table)
    rng = random.Random(3)
    for k in range(200):
        deck = list(range(52))
        rng.shuffle(deck)
        e = HandEngine([(f"p{i}", 30000) for i in range(6)], 0, 50, 100, deck=deck)
        for seat in (3, 4, 5, 0):
            e.apply(seat, Action.fold())
        a = h.act(e.observation(1))  # SB first in, deep
        assert a.kind.value in ("raise", "fold"), (k, a)


def test_hybrid_plays_legal_session(ckpt_v2, table):
    agents = [hybrid(ckpt_v2, table)] + [RandomAgent(f"r{i}", seed=i) for i in range(5)]
    res = play_session(agents, 120, starting_stack=3000, small_blind=25, big_blind=50, seed=4)
    assert res.invalid_actions == 0


def test_hybrid_invariant_to_hidden_and_future_cards(ckpt_v2, table):
    rng = random.Random(9)
    h = hybrid(ckpt_v2, table, seed=5)
    for _ in range(20):
        n = rng.choice([2, 6])
        seat = rng.randrange(n)
        deck = list(range(52))
        rng.shuffle(deck)
        stacks = [rng.choice([700, 3000]) for _ in range(n)]
        a = _hero_decisions(deck, seat, n, h, stacks, 0)
        b = _hero_decisions(_swap_opponent_cards(deck, seat, n, rng), seat, n, h, stacks, 0)
        assert a == b


class _Caller(Agent):
    algorithm = "c"

    def act(self, obs):
        return Action.call() if obs.legal.can_call else Action.check()


def test_hybrid_folds_air_facing_postflop_bet(ckpt_v2, table):
    h = hybrid(ckpt_v2, table)
    e = HandEngine([("hero", 5000), ("v", 5000)], 0, 50, 100, deck=make_deck(["4d3s", "KsQd"], "Kh9h2cJc8s"))
    rec_actions = []
    e.apply(0, Action.call())
    e.apply(1, Action.check())
    e.apply(1, Action.bet(150))  # villain bets the flop
    obs = e.observation(0)
    act = h.act(obs)
    rec_actions.append(act.kind.value)
    assert act.kind.value == "fold"
    _ = play_hand  # imported for parity with other tests
