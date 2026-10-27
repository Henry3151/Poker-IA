"""Trained-policy agent (MCCFR push/fold) with an equity fallback.

The trained policy is used **only where its abstraction applies**:
1. small blind, folded to, unraised pot, only the big blind left: shove or fold;
2. big blind facing an all-in from the small blind with no one else in: call or fold;
and only when the effective stack is within the trained range (nearest trained depth).
Everywhere else the agent delegates to :class:`EquityAgent`. ``last_info`` records which
path was used so analytics can separate trained-policy decisions from fallback ones.
"""

from __future__ import annotations

from typing import Any

from poker_lab.agents.base import Agent, clamp_raise, give_up
from poker_lab.agents.equity_agent import EquityAgent
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.cards import hand_class
from poker_lab.domain.observation import Observation
from poker_lab.training.checkpoints import Checkpoint, load_checkpoint, load_checkpoint_meta


class PolicyAgent(Agent):
    algorithm = "policy"

    def __init__(
        self,
        checkpoint: Checkpoint,
        name: str | None = None,
        version_label: str = "v1",
        seed: int = 0,
        fallback_samples: int = 200,
        checkpoint_sha256: str | None = None,
    ) -> None:
        super().__init__(name, version_label, seed)
        self.ckpt = checkpoint
        self.checkpoint_sha256 = checkpoint_sha256
        self.stacks = sorted(checkpoint.policy.stacks_bb)
        self.fallback = EquityAgent(f"{self.name}-fallback", version_label, seed + 1, samples=fallback_samples)

    @classmethod
    def from_checkpoint(cls, path: str, name: str, version_label: str, seed: int, fallback_samples: int = 200) -> PolicyAgent:
        meta = load_checkpoint_meta(path)
        return cls(load_checkpoint(path), name, version_label, seed, fallback_samples, meta["sha256"])

    def reseed(self, seed: int) -> None:
        super().reseed(seed)
        self.fallback.reseed(seed + 1)

    def config(self) -> dict[str, Any]:
        return {**super().config(), "checkpoint_sha256": self.checkpoint_sha256, "stacks_bb": self.stacks}

    def _bucket(self, eff_bb: float) -> str | None:
        if eff_bb > self.stacks[-1] * 1.15:
            return None
        s = min(self.stacks, key=lambda x: abs(x - eff_bb))
        return f"{s:g}"

    def _situation(self, obs: Observation) -> str | None:
        if obs.street is not Street.PREFLOP:
            return None
        live = [s for s in obs.seats if not s.folded]
        if len(live) != 2:
            return None
        n = len(obs.seats)
        sb_pos = "BTN" if n == 2 else "SB"
        opp = next(s for s in live if s.seat != obs.seat)
        voluntary = [a for a in obs.history if a.kind not in ("fold",)]
        if obs.position == sb_pos and opp.position == "BB" and not voluntary and obs.current_bet <= obs.big_blind:
            return "sb_first_in"
        if (
            obs.position == "BB"
            and opp.position == sb_pos
            and opp.all_in
            and obs.to_call > 0
            and len(voluntary) == 1
            and voluntary[0].seat == opp.seat
        ):
            return "bb_vs_shove"
        return None

    def act(self, obs: Observation) -> Action:
        sit = self._situation(obs)
        eff_bb = obs.effective_stack / obs.big_blind
        bucket = self._bucket(eff_bb) if sit else None
        if sit is None or bucket is None:
            action = self.fallback.act(obs)
            self.last_info = {**self.fallback.last_info, "path": "equity_fallback"}
            return action
        cls = hand_class(obs.hole_cards)
        lg = obs.legal
        if sit == "sb_first_in":
            p = self.ckpt.policy.sb_push[bucket][cls]
            shove = self.rng.random() < p
            self.last_info = {
                "path": "trained_policy",
                "method": "mccfr_pushfold",
                "situation": sit,
                "stack_bucket_bb": bucket,
                "effective_bb": round(eff_bb, 2),
                "hand_class": cls,
                "action_prob": p,
            }
            if shove and lg.can_raise:
                return clamp_raise(lg, lg.max_raise_to)
            return give_up(lg)
        p = self.ckpt.policy.bb_call[bucket][cls]
        call = self.rng.random() < p
        self.last_info = {
            "path": "trained_policy",
            "method": "mccfr_pushfold",
            "situation": sit,
            "stack_bucket_bb": bucket,
            "effective_bb": round(eff_bb, 2),
            "hand_class": cls,
            "action_prob": p,
        }
        return Action.call() if call and lg.can_call else give_up(lg)
