"""External-sampling Monte Carlo CFR and exact best response for small tabular games.

Reproducibility: iteration ``t`` uses ``random.Random(derive_seed(seed, "iter", t))`` so a
run of N iterations equals a run of N/2 iterations resumed for N/2 more.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from poker_lab.domain.seeds import derive_seed
from poker_lab.training.games import History, TabularGame


@dataclass
class MCCFRState:
    regret_sum: dict[str, list[float]] = field(default_factory=dict)
    strategy_sum: dict[str, list[float]] = field(default_factory=dict)
    iterations: int = 0

    def to_json(self) -> dict[str, Any]:
        return {"regret_sum": self.regret_sum, "strategy_sum": self.strategy_sum, "iterations": self.iterations}

    @staticmethod
    def from_json(d: dict[str, Any]) -> MCCFRState:
        return MCCFRState(
            {k: [float(x) for x in v] for k, v in d["regret_sum"].items()},
            {k: [float(x) for x in v] for k, v in d["strategy_sum"].items()},
            int(d["iterations"]),
        )


def regret_matching(regrets: list[float]) -> list[float]:
    pos = [r if r > 0 else 0.0 for r in regrets]
    s = sum(pos)
    if s <= 0:
        return [1.0 / len(regrets)] * len(regrets)
    return [p / s for p in pos]


class ExternalSamplingMCCFR:
    def __init__(self, game: TabularGame, seed: int, state: MCCFRState | None = None) -> None:
        self.game = game
        self.seed = seed
        self.state = state or MCCFRState()

    def _regrets(self, key: str, n: int) -> list[float]:
        r = self.state.regret_sum.get(key)
        if r is None:
            r = self.state.regret_sum[key] = [0.0] * n
        return r

    def _traverse(self, h: History, outcome: Any, p: int, rng: random.Random) -> float:
        g = self.game
        if g.is_terminal(h):
            u = g.utility(h, outcome)
            return u if p == 0 else -u
        pl = g.player(h)
        key = g.infoset(h, outcome)
        acts = g.actions(h)
        regrets = self._regrets(key, len(acts))
        strat = regret_matching(regrets)
        if pl == p:
            vals = [self._traverse((*h, a), outcome, p, rng) for a in acts]
            v = sum(s * x for s, x in zip(strat, vals, strict=True))
            for k in range(len(acts)):
                regrets[k] += vals[k] - v
            return v
        ss = self.state.strategy_sum.get(key)
        if ss is None:
            ss = self.state.strategy_sum[key] = [0.0] * len(acts)
        for k in range(len(acts)):
            ss[k] += strat[k]
        r = rng.random()
        acc = 0.0
        choice = len(acts) - 1
        for k, s in enumerate(strat):
            acc += s
            if r < acc:
                choice = k
                break
        return self._traverse((*h, acts[choice]), outcome, p, rng)

    def run(self, iterations: int, callback: Callable[[int], None] | None = None) -> MCCFRState:
        for _ in range(iterations):
            t = self.state.iterations
            rng = random.Random(derive_seed(self.seed, "iter", t))
            for p in (0, 1):
                outcome = self.game.sample_chance(rng)
                self._traverse(self.game.root(), outcome, p, rng)
            self.state.iterations += 1
            if callback:
                callback(self.state.iterations)
        return self.state

    def average_strategy(self) -> dict[str, list[float]]:
        out = {}
        for k, s in self.state.strategy_sum.items():
            tot = sum(s)
            out[k] = [x / tot for x in s] if tot > 0 else [1.0 / len(s)] * len(s)
        return out


def _strategy_at(policy: dict[str, list[float]], key: str, n: int) -> list[float]:
    return policy.get(key, [1.0 / n] * n)


def best_response_value(game: TabularGame, policy: dict[str, list[float]], br: int) -> float:
    """Exact value (for player ``br``) of a best response against ``policy``."""
    infos: dict[str, list[tuple[Any, History, float]]] = defaultdict(list)

    def walk(h: History, o: Any, w: float) -> None:
        if game.is_terminal(h):
            return
        pl = game.player(h)
        acts = game.actions(h)
        if pl == br:
            infos[game.infoset(h, o)].append((o, h, w))
            for a in acts:
                walk((*h, a), o, w)
        else:
            st = _strategy_at(policy, game.infoset(h, o), len(acts))
            for a, pa in zip(acts, st, strict=True):
                if pa > 0:
                    walk((*h, a), o, w * pa)

    outcomes = game.chance_outcomes()
    for prob, o in outcomes:
        walk(game.root(), o, prob)

    decision: dict[str, str] = {}

    def value(h: History, o: Any) -> float:
        if game.is_terminal(h):
            u = game.utility(h, o)
            return u if br == 0 else -u
        pl = game.player(h)
        acts = game.actions(h)
        if pl == br:
            return value((*h, decision[game.infoset(h, o)]), o)
        st = _strategy_at(policy, game.infoset(h, o), len(acts))
        return sum(pa * value((*h, a), o) for a, pa in zip(acts, st, strict=True) if pa > 0)

    for key in sorted(infos, key=lambda k: -len(infos[k][0][1])):
        acts = game.actions(infos[key][0][1])
        best_a, best_v = acts[0], float("-inf")
        for a in acts:
            v = sum(w * value((*h, a), o) for o, h, w in infos[key])
            if v > best_v:
                best_a, best_v = a, v
        decision[key] = best_a
    return sum(prob * value(game.root(), o) for prob, o in outcomes)


def policy_value(game: TabularGame, policy: dict[str, list[float]]) -> float:
    """Expected utility for player 0 when both players follow ``policy``."""

    def value(h: History, o: Any) -> float:
        if game.is_terminal(h):
            return game.utility(h, o)
        acts = game.actions(h)
        st = _strategy_at(policy, game.infoset(h, o), len(acts))
        return sum(pa * value((*h, a), o) for a, pa in zip(acts, st, strict=True) if pa > 0)

    return sum(p * value(game.root(), o) for p, o in game.chance_outcomes())


def exploitability(game: TabularGame, policy: dict[str, list[float]]) -> float:
    """(BR_0 + BR_1) / 2: average gain of a best responder; 0 at a Nash equilibrium."""
    return (best_response_value(game, policy, 0) + best_response_value(game, policy, 1)) / 2.0
