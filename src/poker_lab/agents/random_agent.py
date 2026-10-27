from __future__ import annotations

from poker_lab.agents.base import Agent
from poker_lab.domain.actions import Action
from poker_lab.domain.observation import Observation


class RandomAgent(Agent):
    """Uniform over action *kinds* that are legal; raise sizes uniform in the legal range."""

    algorithm = "random"

    def act(self, obs: Observation) -> Action:
        lg = obs.legal
        kinds: list[str] = []
        if lg.can_fold:
            kinds.append("fold")
        if lg.can_check:
            kinds.append("check")
        if lg.can_call:
            kinds.append("call")
        if lg.raise_kind is not None:
            kinds.append("raise")
        k = self.rng.choice(kinds)
        self.last_info = {"method": "uniform_random"}
        if k == "fold":
            return Action.fold()
        if k == "check":
            return Action.check()
        if k == "call":
            return Action.call()
        assert lg.raise_kind is not None
        return Action(lg.raise_kind, self.rng.randint(lg.min_raise_to, lg.max_raise_to))
