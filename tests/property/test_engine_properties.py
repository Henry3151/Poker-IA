import random

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from poker_lab.domain.actions import Action, ActionKind
from poker_lab.engine.hand import HandEngine, IllegalActionError


def random_legal_action(rng: random.Random, lg) -> Action:
    options: list[Action] = []
    if lg.can_fold:
        options.append(Action.fold())
    if lg.can_check:
        options.append(Action.check())
    if lg.can_call:
        options.append(Action.call())
    if lg.raise_kind is not None:
        amt = rng.choice([lg.min_raise_to, lg.max_raise_to, rng.randint(lg.min_raise_to, lg.max_raise_to)])
        options.append(Action(lg.raise_kind, amt))
    return rng.choice(options)


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    n=st.integers(min_value=2, max_value=6),
    stacks=st.lists(st.integers(min_value=1, max_value=5000), min_size=6, max_size=6),
    sb=st.integers(min_value=1, max_value=100),
    ante=st.integers(min_value=0, max_value=30),
    seed=st.integers(min_value=0, max_value=2**31),
    button=st.integers(min_value=0, max_value=5),
)
def test_random_hands_conserve_chips_and_terminate(n, stacks, sb, ante, seed, button):
    bb = sb * 2
    players = [(f"p{i}", stacks[i]) for i in range(n)]
    e = HandEngine(players, button=button % n, small_blind=sb, big_blind=bb, ante=ante, seed=seed)
    total = sum(stacks[:n])
    rng = random.Random(seed)
    steps = 0
    while not e.is_finished:
        seat = e.to_act
        assert seat is not None
        assert e.total_chips() == total
        lg = e.legal_actions(seat)
        # legal set is never empty
        assert lg.can_check or lg.can_call or lg.can_fold
        # an out-of-range raise is always rejected
        if lg.raise_kind is not None:
            try:
                e.apply(seat, Action(lg.raise_kind, lg.max_raise_to + 1))
                raise AssertionError("over-stack raise accepted")
            except IllegalActionError:
                pass
        e.apply(seat, random_legal_action(rng, lg))
        steps += 1
        assert steps < 500
    r = e.result()
    assert sum(r.ending_stacks) == total
    assert all(s >= 0 for s in r.ending_stacks)
    assert r.pot_total >= sum(max(0, -x) for x in r.net)  # pot covers every loss
    # every pot awarded fully
    for p in r.pots:
        assert sum(p.shares) == p.amount and set(p.winners) <= set(p.eligible)
    # winners can only gain what the losers lost
    assert sum(r.net) == 0


@settings(max_examples=150, deadline=None)
@given(seed=st.integers(min_value=0, max_value=2**31))
def test_same_seed_same_hand(seed):
    def play():
        e = HandEngine([(f"p{i}", 1000) for i in range(6)], 0, 5, 10, seed=seed, hand_id="h")
        rng = random.Random(seed)
        while not e.is_finished:
            s = e.to_act
            e.apply(s, random_legal_action(rng, e.legal_actions(s)))
        return [(ev.type, ev.payload) for ev in e.events]

    assert play() == play()


def test_fold_only_when_facing_bet():
    e = HandEngine([("a", 1000), ("b", 1000)], 0, 5, 10, seed=3)
    e.apply(0, Action.call())
    lg = e.legal_actions(1)
    assert lg.can_check and not lg.can_fold
    assert lg.raise_kind is ActionKind.RAISE


def _contributions(e: HandEngine) -> list[int]:
    contrib = [0] * e.n
    for ev in e.events:
        if ev.type in ("ante_posted", "blind_posted"):
            contrib[ev.payload["seat"]] += ev.payload["amount"]
        elif ev.type == "action_applied":
            contrib[ev.payload["seat"]] += ev.payload["added"]
    return contrib


@settings(max_examples=400, deadline=None)
@given(
    n=st.integers(min_value=2, max_value=6),
    stacks=st.lists(st.integers(min_value=1, max_value=3000), min_size=6, max_size=6),
    seed=st.integers(min_value=0, max_value=2**31),
)
def test_nobody_wins_more_than_matched_and_best_hand_wins_main_pot(n, stacks, seed):
    e = HandEngine([(f"p{i}", stacks[i]) for i in range(n)], seed % n, 10, 20, ante=2, seed=seed)
    rng = random.Random(seed)
    while not e.is_finished:
        s = e.to_act
        e.apply(s, random_legal_action(rng, e.legal_actions(s)))
    r = e.result()
    contrib = _contributions(e)
    for i in range(n):
        gross = r.ending_stacks[i] - (r.starting_stacks[i] - contrib[i])
        cap = sum(min(contrib[j], contrib[i]) for j in range(n))
        assert 0 <= gross <= cap
    if r.showdown_seats:
        best = max(r.hand_scores.values())
        # the first (main) pot always goes to a best hand among those eligible for it
        main = r.pots[0]
        top = max(r.hand_scores[i] for i in main.eligible)
        assert all(r.hand_scores[w] == top for w in main.winners)
        assert best >= top


def test_bulk_random_hands_smoke():
    rng = random.Random(7)
    hands = 0
    for k in range(5000):
        n = rng.randint(2, 6)
        stacks = [rng.randint(1, 4000) for _ in range(n)]
        e = HandEngine([(f"p{i}", stacks[i]) for i in range(n)], k % n, 25, 50, ante=rng.choice([0, 5]), seed=k)
        while not e.is_finished:
            s = e.to_act
            e.apply(s, random_legal_action(rng, e.legal_actions(s)))
        assert sum(e.result().ending_stacks) == sum(stacks)
        hands += 1
    assert hands == 5000
