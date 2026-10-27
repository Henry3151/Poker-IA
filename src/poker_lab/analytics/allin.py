"""Offline all-in equity / chip-EV ("all-in adjusted") for completed hands.

Runs only after a hand is finished, using the offline audit truth (all hole cards). It is
never available to an agent during a decision. It separates *luck in the runout* from the
decision: ``ev_net - actual_net`` is the chips won/lost purely to the cards that came.
"""

from __future__ import annotations

import random
from itertools import combinations

from poker_lab.engine.evaluator import evaluate
from poker_lab.engine.hand import HandEngine

MAX_ENUMERATION = 2000


def board_at_last_action(engine: HandEngine) -> tuple[int, ...] | None:
    """Board when betting closed, if the hand then ran out to showdown without action."""
    r = engine.result()
    if not r.showdown_seats:
        return None
    events = engine.events
    last_action = max((e.seq for e in events if e.type == "action_applied"), default=-1)
    dealt_after = [e for e in events if e.type == "street_dealt" and e.seq > last_action]
    if not dealt_after:
        return None  # river was reached with betting; no runout luck
    n_before = 0
    for e in events:
        if e.type == "street_dealt" and e.seq < last_action:
            n_before = len(e.payload["board"])
    return tuple(r.board[:n_before])


def allin_ev(engine: HandEngine, samples: int = MAX_ENUMERATION, seed: int = 0) -> dict[int, tuple[float, float]]:
    """Return {seat: (equity_in_main_pot, ev_net_chips)} for seats that went to showdown."""
    r = engine.result()
    known = board_at_last_action(engine)
    if known is None:
        return {}
    live = list(r.showdown_seats)
    holes = {i: engine.hole_cards_offline(i) for i in range(engine.n)}
    dead = set(known) | {c for i in range(engine.n) for c in holes[i]}
    deck = [c for c in range(52) if c not in dead]
    need = 5 - len(known)
    pots = [p for p in r.pots]
    contrib = [r.starting_stacks[i] - r.ending_stacks[i] + sum(sh for p in pots for w, sh in zip(p.winners, p.shares, strict=True) if w == i) for i in range(engine.n)]

    runouts: list[tuple[int, ...]]
    combos_count = _ncr(len(deck), need)
    if combos_count <= samples:
        runouts = list(combinations(deck, need))
    else:
        rng = random.Random(seed)
        runouts = [tuple(rng.sample(deck, need)) for _ in range(samples)]
    gross = dict.fromkeys(live, 0.0)
    main_share = dict.fromkeys(live, 0.0)
    for ro in runouts:
        board = list(known) + list(ro)
        scores = {i: evaluate([*holes[i], *board]) for i in live}
        for k, p in enumerate(pots):
            elig = [i for i in p.eligible if i in scores]
            if not elig:
                continue
            best = max(scores[i] for i in elig)
            winners = [i for i in elig if scores[i] == best]
            for w in winners:
                gross[w] += p.amount / len(winners)
                if k == 0:
                    main_share[w] += 1.0 / len(winners)
    n = len(runouts)
    return {i: (main_share[i] / n, gross[i] / n - contrib[i]) for i in live}


def _ncr(n: int, k: int) -> int:
    from math import comb

    return comb(n, k)
