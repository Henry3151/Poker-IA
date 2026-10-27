"""Explicit information-leakage tests.

1. Structural: the observation exposes a fixed whitelist of fields, holds no engine
   objects, and carries no other player's cards.
2. Counterfactual hidden cards: changing ONLY the opponents' hole cards never changes
   any decision of the agent (same seeds, deterministic opponents).
3. Counterfactual future cards: changing ONLY turn/river never changes preflop/flop
   decisions.
4. Static boundary: decision-time code (agents, strategy, engine, domain, training) does
   not import persistence, analytics, evaluation or application modules (results/labels).
"""

import ast
import dataclasses
import random
from pathlib import Path

import pytest

from poker_lab.agents.base import Agent
from poker_lab.agents.equity_agent import EquityAgent
from poker_lab.agents.heuristic import HeuristicAgent
from poker_lab.agents.policy_agent import PolicyAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.application.hand_runner import play_hand
from poker_lab.domain.actions import Action
from poker_lab.domain.cards import card_to_str
from poker_lab.domain.observation import Observation, PublicAction, PublicSeat, TournamentInfo
from poker_lab.engine.hand import HandEngine
from poker_lab.training.pushfold_tables import build_table
from poker_lab.training.pushfold_trainer import train_pushfold

OBS_FIELDS = {
    "hand_id", "seat", "player_id", "position", "hole_cards", "board", "street", "button_seat", "small_blind",
    "big_blind", "ante", "pot", "current_bet", "to_call", "stack", "seats", "history", "legal", "tournament",
}
SEAT_FIELDS = {"seat", "player_id", "position", "stack", "street_commitment", "total_commitment", "folded", "all_in"}
ACTION_FIELDS = {"seat", "street", "kind", "amount", "to_total"}
TOURNAMENT_FIELDS = {
    "entrants", "players_remaining", "paid_places", "payouts", "level", "phase", "average_stack", "other_table_stacks",
}


def test_observation_field_whitelists():
    """Adding a field to any of these types must be a deliberate, reviewed change."""
    assert {f.name for f in dataclasses.fields(Observation)} == OBS_FIELDS
    assert {f.name for f in dataclasses.fields(PublicSeat)} == SEAT_FIELDS
    assert {f.name for f in dataclasses.fields(PublicAction)} == ACTION_FIELDS
    assert {f.name for f in dataclasses.fields(TournamentInfo)} == TOURNAMENT_FIELDS


def _walk(obj, seen=None):
    seen = seen if seen is not None else set()
    if id(obj) in seen:
        return
    seen.add(id(obj))
    yield obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _walk(getattr(obj, f.name), seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for x in obj:
            yield from _walk(x, seen)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from _walk(x, seen)


def test_observation_object_graph_has_no_engine_or_hidden_cards():
    for seed in range(40):
        e = HandEngine([(f"p{i}", 1000) for i in range(6)], seed % 6, 5, 10, ante=1, seed=seed)
        rng = random.Random(seed)
        while not e.is_finished:
            seat = e.to_act
            obs = e.observation(seat)
            hidden = {c for j in range(6) if j != seat for c in e.hole_cards_offline(j)}
            for node in _walk(obs):
                assert not isinstance(node, HandEngine)
                assert type(node).__name__ not in {"_Seat", "Event", "HandResult"}
            assert not (set(obs.hole_cards) | set(obs.board)) & hidden
            # serialised form only contains own cards + board as cards
            d = obs.to_dict()
            assert set(d) == OBS_FIELDS
            lg = obs.legal
            opts = [Action.check() if lg.can_check else Action.call()]
            if lg.can_fold:
                opts.append(Action.fold())
            e.apply(seat, rng.choice(opts))


class AlwaysCall(Agent):
    algorithm = "always_call"

    def act(self, obs):
        return Action.call() if obs.legal.can_call else Action.check()


def _swap_opponent_cards(deck, hero_seat, n_players, rng):
    """New deck: same hero cards and same board, different opponents' hole cards."""
    deck = list(deck)
    hole_end = 2 * n_players
    board_idx = [hole_end + k for k in (1, 2, 3, 5, 7)]  # burn, flop x3, burn, turn, burn, river
    fixed = set(range(2 * hero_seat, 2 * hero_seat + 2)) | set(board_idx)
    opp_idx = [i for i in range(hole_end) if i not in fixed]
    spare_idx = [i for i in range(hole_end + 8, 52)]
    pick = rng.sample(spare_idx, len(opp_idx))
    for a, b in zip(opp_idx, pick, strict=True):
        deck[a], deck[b] = deck[b], deck[a]
    return deck


@pytest.fixture(scope="module")
def policy_ckpt():
    t = build_table(samples=8, seed=1)
    return train_pushfold(t, 1500, seed=2, stacks=[5.0, 10.0, 20.0], evaluate=False).checkpoint


def _agents(kind, policy_ckpt):
    if kind == "heuristic":
        return HeuristicAgent("hero", seed=5)
    if kind == "equity":
        return EquityAgent("hero", seed=5, samples=40)
    if kind == "equity_icm_adaptive":
        return EquityAgent("hero", seed=5, samples=40, icm=True, adaptive=True)
    if kind == "policy":
        return PolicyAgent(policy_ckpt, "hero", seed=5, fallback_samples=40)
    return RandomAgent("hero", seed=5)


def _hero_decisions(deck, hero_seat, n, hero, stacks, button):
    hero.reseed(5)
    if isinstance(hero, PolicyAgent):
        hero.fallback.reseed(6)
    players = [("hero" if i == hero_seat else f"opp{i}", stacks[i]) for i in range(n)]
    agents = [hero if i == hero_seat else AlwaysCall(f"opp{i}") for i in range(n)]
    e = HandEngine(players, button, 50, 100, deck=deck, hand_id="fixed")
    rec = play_hand(e, agents)
    return [(d.street, d.applied["kind"], d.applied.get("amount")) for d in rec.decisions if d.seat == hero_seat]


@pytest.mark.parametrize("kind", ["random", "heuristic", "equity", "equity_icm_adaptive", "policy"])
def test_decisions_invariant_to_opponents_hidden_cards(kind, policy_ckpt):
    rng = random.Random(42)
    hero = _agents(kind, policy_ckpt)
    for trial in range(25):
        n = rng.choice([2, 3, 6])
        hero_seat = rng.randrange(n)
        stacks = [rng.choice([600, 1500, 5000]) for _ in range(n)]
        button = rng.randrange(n)
        deck = list(range(52))
        rng.shuffle(deck)
        base = _hero_decisions(deck, hero_seat, n, hero, stacks, button)
        alt_deck = _swap_opponent_cards(deck, hero_seat, n, rng)
        assert alt_deck[2 * hero_seat : 2 * hero_seat + 2] == deck[2 * hero_seat : 2 * hero_seat + 2]
        alt = _hero_decisions(alt_deck, hero_seat, n, hero, stacks, button)
        assert base == alt, f"{kind}: decisions changed with opponents' hidden cards (trial {trial})"


@pytest.mark.parametrize("kind", ["heuristic", "equity", "policy"])
def test_early_decisions_invariant_to_future_board_cards(kind, policy_ckpt):
    rng = random.Random(7)
    hero = _agents(kind, policy_ckpt)
    for _ in range(25):
        n = rng.choice([2, 6])
        hero_seat = rng.randrange(n)
        stacks = [5000] * n
        deck = list(range(52))
        rng.shuffle(deck)
        base = _hero_decisions(deck, hero_seat, n, hero, stacks, 0)
        alt = list(deck)
        turn_i, river_i = 2 * n + 5, 2 * n + 7
        spare = rng.sample(range(2 * n + 8, 52), 2)
        alt[turn_i], alt[spare[0]] = alt[spare[0]], alt[turn_i]
        alt[river_i], alt[spare[1]] = alt[spare[1]], alt[river_i]
        early = [d for d in base if d[0] in ("preflop", "flop")]
        alt_dec = _hero_decisions(alt, hero_seat, n, hero, stacks, 0)
        assert early == [d for d in alt_dec if d[0] in ("preflop", "flop")]


DECISION_TIME_PACKAGES = ["agents", "strategy", "engine", "domain", "training"]
FORBIDDEN = ("poker_lab.persistence", "poker_lab.analytics", "poker_lab.evaluation", "poker_lab.application", "sqlite3")


def test_decision_time_code_cannot_reach_results_or_labels():
    root = Path(__file__).resolve().parents[2] / "src" / "poker_lab"
    offenders = []
    for pkg in DECISION_TIME_PACKAGES:
        for f in (root / pkg).glob("*.py"):
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for nm in names:
                    if nm.startswith(FORBIDDEN):
                        offenders.append(f"{pkg}/{f.name}: {nm}")
    assert offenders == []


def test_public_tournament_info_contains_no_identities_or_results():
    from poker_lab.agents.registry import AgentSpec, create_agent
    from poker_lab.tournament.config import TournamentConfig
    from poker_lab.tournament.director import TournamentDirector

    seen: list[TournamentInfo] = []

    class Spy(RandomAgent):
        def act(self, obs):
            if obs.tournament is not None:
                seen.append(obs.tournament)
            return super().act(obs)

    ents = [(f"s{i}", Spy(f"s{i}", seed=i)) for i in range(8)]
    TournamentDirector(TournamentConfig(starting_stack=500, hands_per_level=3), ents, 3).run()
    assert seen
    for t in seen:
        assert all(isinstance(x, int) for x in t.other_table_stacks)  # anonymous chip counts only
        assert isinstance(t.phase, str) and t.players_remaining >= 2
    _ = create_agent(AgentSpec(algorithm="random"), "x", 1)
    assert card_to_str(0) == "2c"


def test_counterfactual_test_detects_a_cheating_agent():
    """Power check: an agent that peeks at the engine via the garbage collector IS caught."""
    import gc

    class Cheater(Agent):
        algorithm = "cheater"

        def act(self, obs):
            eng = next(o for o in gc.get_objects() if isinstance(o, HandEngine) and o.hand_id == obs.hand_id)
            opp_best = max(c >> 2 for j in range(eng.n) if j != obs.seat for c in eng.hole_cards_offline(j))
            if obs.legal.can_fold and opp_best >= 11:
                return Action.fold()
            return Action.call() if obs.legal.can_call else Action.check()

    rng = random.Random(1)
    changed = 0
    for _ in range(30):
        deck = list(range(52))
        rng.shuffle(deck)
        a = _hero_decisions(deck, 0, 6, Cheater("hero"), [1000] * 6, 3)
        b = _hero_decisions(_swap_opponent_cards(deck, 0, 6, rng), 0, 6, Cheater("hero"), [1000] * 6, 3)
        changed += a != b
    assert changed > 0
