"""Decision classification (P9-C): reference, inconclusive cases, hidden information, outcome invariance."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from poker_lab.domain.actions import Action
from poker_lab.domain.cards import parse_cards
from poker_lab.engine.hand import HandEngine
from poker_lab.lab.assessment import PushFoldReference, technical
from poker_lab.lab.quality import ADEQUATE, ERROR, INCONCLUSIVE, TECHNICAL

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ref() -> PushFoldReference:
    return PushFoldReference.load(ROOT)


def hu_engine(hero: str, stack_bb: float = 10, rest_seed: int = 0, n: int = 2) -> HandEngine:
    """Seat 0 is the button (= SB heads-up). The hero's cards are fixed; every other card is shuffled."""
    mine = parse_cards(hero)
    rest = [c for c in range(52) if c not in mine]
    random.Random(rest_seed).shuffle(rest)
    deck = list(mine) + rest
    stack = int(stack_bb * 100)
    if n == 2:
        return HandEngine([("hero", stack), ("villain", stack)], button=0, small_blind=50, big_blind=100, seed=1, hand_id="h", deck=deck)
    # 6-max: put the hero cards in the UTG seat (button=0 -> SB=1, BB=2, UTG=3)
    deck = rest[:6] + list(mine) + rest[6:]
    return HandEngine([(f"p{i}", stack) for i in range(n)], button=0, small_blind=50, big_blind=100, seed=1, hand_id="h", deck=deck)


def test_aa_push_is_adequate_and_fold_is_an_error(ref):
    e = hu_engine("AsAh")
    obs = e.observation(e.to_act)
    push = ref.assess(obs, Action.raise_to(obs.legal.max_raise_to))
    fold = ref.assess(obs, Action.fold())
    assert push.label == ADEQUATE and push.best_action == "push" and push.ev_gap_bb == 0
    assert fold.label == ERROR and fold.ev_gap_bb is not None and fold.ev_gap_bb <= -0.5
    assert push.reference == "pushfold_nash" and push.assumptions and push.limitations


def test_trash_deep_push_is_flagged_and_fold_adequate(ref):
    e = hu_engine("7c2d", stack_bb=20)
    obs = e.observation(e.to_act)
    assert ref.assess(obs, Action.fold()).label == ADEQUATE
    assert ref.assess(obs, Action.raise_to(obs.legal.max_raise_to)).label in (ERROR, INCONCLUSIVE)


def test_bb_versus_shove_is_graded(ref):
    e = hu_engine("KsKh")
    e.apply(0, Action.raise_to(e.legal_actions(0).max_raise_to))
    obs = e.observation(1)
    # hero cards are at deck[0:2] = seat 0, so look at seat 1's class only through the observation
    a = ref.assess(obs, Action.call())
    assert a.spot == "bb_vs_shove" and a.label in (ADEQUATE, ERROR, INCONCLUSIVE) and a.ev_chosen_bb is not None


def test_spots_without_validated_reference_are_inconclusive(ref):
    e = hu_engine("AsAh", n=6)
    obs = e.observation(e.to_act)  # UTG, 6 players live
    a = ref.assess(obs, Action.raise_to(obs.legal.max_raise_to))
    assert a.label == INCONCLUSIVE and a.reference is None and a.limitations


def test_partial_raise_and_untrained_context_are_inconclusive(ref):
    e = hu_engine("AsAh")
    obs = e.observation(e.to_act)
    assert ref.assess(obs, Action.raise_to(obs.legal.min_raise_to)).label == INCONCLUSIVE  # outside push/fold
    e2 = hu_engine("AsAh", stack_bb=60)
    obs2 = e2.observation(e2.to_act)
    a = ref.assess(obs2, Action.raise_to(obs2.legal.max_raise_to))
    assert a.label == INCONCLUSIVE and "fora do treinado" in a.reason


def test_technical_failures_are_separate():
    assert technical("timeout").label == TECHNICAL


def test_label_ignores_hidden_cards_and_hand_outcome(ref):
    """Same decision-time observation -> same label, whatever the opponent holds or how the hand ends."""
    results = set()
    outcomes = set()
    for seed in range(12):
        e = hu_engine("Td9d", stack_bb=10, rest_seed=seed)
        obs = e.observation(e.to_act)
        a = ref.assess(obs, Action.raise_to(obs.legal.max_raise_to))
        results.add((a.label, a.ev_chosen_bb, a.ev_best_bb))
        e.apply(0, Action.raise_to(obs.legal.max_raise_to))
        e.apply(1, Action.call())
        outcomes.add(e.result().net[0] > 0)
    assert len(results) == 1  # identical assessment
    assert outcomes == {True, False}  # ...although the hand was won in some deals and lost in others


def test_observation_never_contains_opponent_cards():
    e = hu_engine("AsAh", rest_seed=4)
    obs = e.observation(0)
    villain = set(e.hole_cards_offline(1))
    d = obs.to_dict()
    flat = repr(d)
    assert set(obs.hole_cards) == set(parse_cards("AsAh"))
    assert all(str(c) not in {str(x) for x in d["hole_cards"]} for c in villain)
    assert "hole" not in repr(d["seats"]) and "villain_cards" not in flat
