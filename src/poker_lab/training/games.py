"""Small two-player zero-sum games for MCCFR.

* :class:`KuhnPoker` — 3-card poker with a known equilibrium value of -1/18 for the
  first player. Used only to validate the MCCFR and best-response code.
* :class:`PushFoldGame` — heads-up No-Limit Hold'em *abstraction*: the small blind may
  only fold or move all-in, the big blind may only fold or call. Cards are abstracted to
  the 169 preflop classes; all-in utility uses a precomputed class-vs-class equity table.
  This is the trained policy used in tournaments at short stacks (see docs/TRAINING.md).
"""

from __future__ import annotations

import bisect
import random
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

History = tuple[str, ...]


class TabularGame(ABC):
    name: str = "abstract"

    @abstractmethod
    def chance_outcomes(self) -> list[tuple[float, Any]]: ...

    @abstractmethod
    def sample_chance(self, rng: random.Random) -> Any: ...

    def root(self) -> History:
        return ()

    @abstractmethod
    def is_terminal(self, h: History) -> bool: ...

    @abstractmethod
    def utility(self, h: History, outcome: Any) -> float:
        """Utility for player 0 at a terminal history."""

    @abstractmethod
    def player(self, h: History) -> int: ...

    @abstractmethod
    def infoset(self, h: History, outcome: Any) -> str: ...

    @abstractmethod
    def actions(self, h: History) -> Sequence[str]: ...


class KuhnPoker(TabularGame):
    """Cards J<Q<K (0,1,2). Ante 1. Actions: p (pass/check/fold), b (bet/call)."""

    name = "kuhn"
    DEALS = [(a, b) for a in range(3) for b in range(3) if a != b]

    def chance_outcomes(self) -> list[tuple[float, Any]]:
        return [(1 / 6, d) for d in self.DEALS]

    def sample_chance(self, rng: random.Random) -> Any:
        return rng.choice(self.DEALS)

    def is_terminal(self, h: History) -> bool:
        return h in (("p", "p"), ("b", "b"), ("b", "p"), ("p", "b", "p"), ("p", "b", "b"))

    def utility(self, h: History, outcome: Any) -> float:
        c0, c1 = outcome
        win = 1.0 if c0 > c1 else -1.0
        if h == ("p", "p"):
            return win
        if h in (("b", "b"), ("p", "b", "b")):
            return 2 * win
        if h == ("b", "p"):
            return 1.0
        if h == ("p", "b", "p"):
            return -1.0
        raise ValueError(h)

    def player(self, h: History) -> int:
        return len(h) % 2

    def infoset(self, h: History, outcome: Any) -> str:
        return f"{'JQK'[outcome[self.player(h)]]}:{''.join(h)}"

    def actions(self, h: History) -> Sequence[str]:
        return ("p", "b")


class PushFoldGame(TabularGame):
    """Heads-up push/fold at a fixed effective stack (in big blinds).

    ``ante_bb``: ante paid by each of the two players (part of their stack ``stack_bb``).
    ``dead_bb``: extra dead money in the pot from players who already folded (their antes),
    e.g. (players_dealt - 2) * ante when it is folded to the small blind.
    """

    name = "hu_pushfold"

    def __init__(
        self,
        stack_bb: float,
        classes: list[str],
        equity: list[list[float]],
        weights: list[list[float]],
        ante_bb: float = 0.0,
        dead_bb: float = 0.0,
    ) -> None:
        if stack_bb <= 1 + ante_bb:
            raise ValueError("stack must exceed the big blind plus ante")
        if ante_bb < 0 or dead_bb < 0:
            raise ValueError("ante and dead money must be non-negative")
        self.stack = float(stack_bb)
        self.ante = float(ante_bb)
        self.dead = float(dead_bb)
        self.classes = classes
        self.eq = equity
        n = len(classes)
        flat = [(i, j, weights[i][j]) for i in range(n) for j in range(n) if weights[i][j] > 0]
        total = sum(w for _, _, w in flat)
        self._outcomes = [(w / total, (i, j)) for i, j, w in flat]
        self._cum: list[float] = []
        acc = 0.0
        for p, _ in self._outcomes:
            acc += p
            self._cum.append(acc)

    def chance_outcomes(self) -> list[tuple[float, Any]]:
        return self._outcomes

    def sample_chance(self, rng: random.Random) -> Any:
        k = bisect.bisect_left(self._cum, rng.random() * self._cum[-1])
        return self._outcomes[min(k, len(self._outcomes) - 1)][1]

    def is_terminal(self, h: History) -> bool:
        return h in (("f",), ("p", "f"), ("p", "c"))

    def utility(self, h: History, outcome: Any) -> float:
        i, j = outcome
        if h == ("f",):
            return -(0.5 + self.ante)
        if h == ("p", "f"):
            return 1.0 + self.ante + self.dead
        if h == ("p", "c"):
            return float(self.eq[i][j]) * (2 * self.stack + self.dead) - self.stack
        raise ValueError(h)

    def player(self, h: History) -> int:
        return len(h)

    def infoset(self, h: History, outcome: Any) -> str:
        if not h:
            return f"SB:{self.classes[outcome[0]]}"
        return f"BB:{self.classes[outcome[1]]}"

    def actions(self, h: History) -> Sequence[str]:
        return ("f", "p") if not h else ("f", "c")
