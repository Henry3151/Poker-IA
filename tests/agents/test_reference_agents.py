import dataclasses

from poker_lab.agents.base import Agent
from poker_lab.agents.heuristic import HeuristicAgent, made_hand_level
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.application.hand_runner import play_hand, play_session
from poker_lab.domain.actions import Action
from poker_lab.domain.cards import parse_cards
from poker_lab.domain.observation import Observation
from poker_lab.engine.hand import HandEngine
from poker_lab.strategy.preflop import chen_score


def six_agents(seed=0):
    return [RandomAgent(f"r{i}", seed=seed + i) if i % 2 else HeuristicAgent(f"h{i}", seed=seed + i) for i in range(6)]


def test_chen_known_values():
    assert chen_score(parse_cards("AsAd")) == 20
    assert chen_score(parse_cards("KsKd")) == 16
    assert chen_score(parse_cards("2s2d")) == 5
    assert chen_score(parse_cards("AsKs")) == 12
    assert chen_score(parse_cards("JsTs")) == 9
    assert chen_score(parse_cards("7s2d")) == -1


def test_made_hand_level():
    assert made_hand_level(tuple(parse_cards("AsAd")), tuple(parse_cards("Kc7d2h"))) == 3  # overpair
    assert made_hand_level(tuple(parse_cards("KsQd")), tuple(parse_cards("Kc7d2h"))) == 2  # top pair
    assert made_hand_level(tuple(parse_cards("7s6s")), tuple(parse_cards("Kc7d2h"))) == 1  # middle pair
    assert made_hand_level(tuple(parse_cards("AsQs")), tuple(parse_cards("Kc7d7h"))) == 0  # board pair only
    assert made_hand_level(tuple(parse_cards("Ks7s")), tuple(parse_cards("Kc7d2h"))) == 3  # two pair


def test_smoke_zero_invalid_actions():
    res = play_session(six_agents(), 600, seed=11)
    assert res.invalid_actions == 0
    assert sum(res.net_by_agent.values()) == 0
    assert res.decisions > 600


def test_sessions_reproducible():
    a = play_session(six_agents(5), 150, seed=3)
    b = play_session(six_agents(5), 150, seed=3)
    c = play_session(six_agents(5), 150, seed=4)
    assert a.net_by_agent == b.net_by_agent
    assert a.net_by_agent != c.net_by_agent


class SpyAgent(Agent):
    algorithm = "spy"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.seen: list[Observation] = []

    def act(self, obs):
        self.seen.append(obs)
        # try to reach engine internals through the observation
        assert not any(hasattr(obs, attr) for attr in ("_deck", "engine", "_seats", "deck"))
        assert dataclasses.is_dataclass(obs)
        return obs.legal.safe_default() if not obs.legal.can_call else Action.call()


def test_agent_sees_only_own_cards_and_public_state():
    agents = [SpyAgent(f"s{i}") for i in range(6)]
    for h in range(30):
        e = HandEngine([(a.name, 1000) for a in agents], h % 6, 5, 10, seed=h)
        holes = {i: set(e.hole_cards_offline(i)) for i in range(6)}
        play_hand(e, agents)
        for i, ag in enumerate(agents):
            for obs in ag.seen:
                assert set(obs.hole_cards) == holes[i]
                others = set().union(*(holes[j] for j in range(6) if j != i))
                assert not (set(obs.board) & others)
                # no field of the observation carries another player's hole cards
                flat = repr(obs.to_dict())
                assert "hole_cards_dealt" not in flat
            ag.seen.clear()


class BrokenAgent(Agent):
    algorithm = "broken"

    def __init__(self, mode, *a, **k):
        super().__init__(*a, **k)
        self.mode = mode

    def act(self, obs):
        if self.mode == "raise_too_much":
            return Action.raise_to(10**9)
        if self.mode == "exception":
            raise RuntimeError("boom")
        if self.mode == "garbage":
            return "all-in please"
        return Action.check()  # illegal when facing a bet


def test_invalid_actions_are_caught_and_fallback_applied():
    for mode in ("raise_too_much", "exception", "garbage", "check"):
        agents = [BrokenAgent(mode, "bad"), RandomAgent("ok", seed=1)]
        e = HandEngine([("bad", 1000), ("ok", 1000)], 0, 5, 10, seed=1)
        rec = play_hand(e, agents)
        bad = [d for d in rec.decisions if d.player_id == "bad"]
        assert bad and all(d.fallback_applied for d in bad if not d.valid)
        assert any(not d.valid for d in bad)
        assert sum(rec.result.ending_stacks) == 2000
        for d in bad:
            if not d.valid:
                assert d.issue in {"invalid_action", "agent_exception"}
                assert d.applied["kind"] in {"check", "fold"}


def test_timeout_triggers_fallback():
    class Slow(Agent):
        algorithm = "slow"

        def act(self, obs):
            import time

            time.sleep(0.02)
            return Action.call() if obs.legal.can_call else Action.check()

    e = HandEngine([("slow", 1000), ("r", 1000)], 0, 5, 10, seed=2)
    rec = play_hand(e, [Slow("slow"), RandomAgent("r")], latency_budget_ms=5)
    first = rec.decisions[0]
    assert first.issue == "timeout" and first.applied["kind"] == "fold"
