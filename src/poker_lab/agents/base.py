"""Agent contract.

Agents receive only an :class:`Observation` (own cards + public state + legal actions)
and return an :class:`Action`. They never touch the engine. ``last_info`` lets an agent
report the estimates behind its last decision (equity, method, samples) for auditing.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any

from poker_lab.domain.actions import Action, LegalActions
from poker_lab.domain.observation import Observation


class Agent(ABC):
    algorithm: str = "abstract"

    def __init__(self, name: str | None = None, version_label: str = "v1", seed: int = 0) -> None:
        self.name = name or self.algorithm
        self.version_label = version_label
        self.seed = seed
        self.rng = random.Random(seed)
        self.last_info: dict[str, Any] = {}

    @abstractmethod
    def act(self, obs: Observation) -> Action: ...

    def reseed(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def config(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm, "seed": self.seed}

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name}@{self.version_label})"


def clamp_raise(legal: LegalActions, target: int) -> Action:
    """Turn a desired total raise into a legal action (raise/bet clamped, else call/check)."""
    if legal.raise_kind is None:
        return Action.call() if legal.can_call else Action.check()
    to = max(legal.min_raise_to, min(int(target), legal.max_raise_to))
    return Action(legal.raise_kind, to)


def passive(legal: LegalActions) -> Action:
    return Action.check() if legal.can_check else Action.call()


def give_up(legal: LegalActions) -> Action:
    return Action.check() if legal.can_check else Action.fold()
