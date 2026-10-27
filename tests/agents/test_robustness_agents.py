import pytest

from poker_lab.agents.adaptive import AdaptiveHeuristicAgent
from poker_lab.agents.hybrid import HybridAdaptiveAgent, HybridAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.agents.registry import OPPONENT_PROFILES, create_agent
from poker_lab.application.hand_runner import play_session
from poker_lab.domain.actions import Action
from poker_lab.engine.hand import HandEngine
from poker_lab.strategy.opponents import OpponentModel, PlayerStats
from poker_lab.strategy.preflop_model import open_fraction
from poker_lab.training.pushfold_tables import build_table
from poker_lab.training.pushfold_trainer import train_pushfold


@pytest.fixture(scope="module")
def table():
    return build_table(samples=16, seed=7)


@pytest.fixture(scope="module")
def ckpt(table):
    return train_pushfold(table, 1500, seed=3, stacks=[5.0, 10.0, 20.0], contexts=[(0.0, 0.0), (0.125, 0.0)], evaluate=False).checkpoint


def test_opponent_model_counts_steals_and_folds():
    m = OpponentModel()
    # 6-max, button seat 0: UTG(3) folds, HJ(4) folds, CO(5) raises (steal), BTN folds, SB folds, BB to act
    e = HandEngine([(f"p{i}", 10000) for i in range(6)], 0, 50, 100, seed=1)
    for seat in (3, 4):
        e.apply(seat, Action.fold())
    e.apply(5, Action.raise_to(250))
    e.apply(0, Action.fold())
    e.apply(1, Action.fold())
    obs = e.observation(2)  # BB observes
    m.observe(obs)
    co = m.get("p5")
    assert co.steal_opps == 1 and co.steals == 1
    sb = m.get("p1")
    assert sb.vs_steal_opps == 1 and sb.vs_steal_folds == 1
    btn = m.get("p0")
    assert btn.threebet_opps == 1 and btn.threebets == 0
    m.observe(obs)  # idempotent for the same history
    assert m.get("p5").steal_opps == 1


def test_adaptive_agent_registry_and_legal_play():
    a = create_agent(OPPONENT_PROFILES["adaptive_lag"], "a", 1)
    assert isinstance(a, AdaptiveHeuristicAgent)
    agents = [a, create_agent(OPPONENT_PROFILES["adaptive_tag"], "b", 2)] + [RandomAgent(f"r{i}", seed=i) for i in range(4)]
    res = play_session(agents, 250, starting_stack=5000, small_blind=25, big_blind=50, seed=2)
    assert res.invalid_actions == 0
    with pytest.raises(ValueError):
        create_agent(type(OPPONENT_PROFILES["tag"])(algorithm="heuristic", params={"defend_pct": 0.3}), "x", 1)


def test_hybrid_v1_hooks_unchanged(ckpt, table):
    h = HybridAgent(ckpt, table, "h", seed=1, samples=30)
    e = HandEngine([(f"p{i}", 20000) for i in range(6)], 0, 50, 100, seed=3)
    obs = e.observation(e.to_act)
    for k in range(1, 6):
        assert h._open_fraction(obs, list(range(k)))[0] == open_fraction(k)
    assert h._reraise_range(obs, 4)[1] == "+3bet"


def test_hybrid_v2_tightens_against_resistance(ckpt, table):
    h = HybridAdaptiveAgent(ckpt, table, "h", seed=1, samples=30)
    e = HandEngine([(f"p{i}", 20000) for i in range(6)], 0, 50, 100, seed=3)
    obs = e.observation(e.to_act)
    neutral, _ = h._open_fraction(obs, [1, 2])  # no data -> prior -> unchanged
    assert neutral == pytest.approx(open_fraction(2))
    for pid, folds in (("p1", 2), ("p2", 3)):  # blinds rarely fold to steals
        h.model.stats[pid] = PlayerStats(vs_steal_opps=40, vs_steal_folds=folds)
    tight, info = h._open_fraction(obs, [1, 2])
    assert tight < neutral and info["p_all_fold_est"] < 0.2
    for pid in ("p1", "p2"):
        h.model.stats[pid] = PlayerStats(vs_steal_opps=40, vs_steal_folds=39)
    wide, _ = h._open_fraction(obs, [1, 2])
    assert wide > neutral


def test_hybrid_v2_uses_observed_3bet_rate(ckpt, table):
    h = HybridAdaptiveAgent(ckpt, table, "h", seed=1, samples=30)
    e = HandEngine([(f"p{i}", 20000) for i in range(6)], 0, 50, 100, seed=3)
    obs = e.observation(e.to_act)
    h.model.stats["p4"] = PlayerStats(threebet_opps=100, threebets=30)
    rng, tag = h._reraise_range(obs, 4)
    assert "rate=" in tag and len(rng) > len(h._reraise_range(obs, 1)[0])


def test_hybrid_v2_legal_session(ckpt, table):
    agents = [HybridAdaptiveAgent(ckpt, table, "h", seed=1, samples=30)] + [
        create_agent(OPPONENT_PROFILES[p], p, i) for i, p in enumerate(["adaptive_lag", "adaptive_tag", "bluffer60", "maniac", "nit"])
    ]
    res = play_session(agents, 150, starting_stack=4000, small_blind=25, big_blind=50, seed=5)
    assert res.invalid_actions == 0
