"""Cash-game policy used ONLY by the Open Poker adapter (P11).

Deliberately separate from the MTT champion (``hybrid-v1``, P7b/P7c): the platform plays
6-max cash-style tables with deep stacks (50-250 bb), fixed blinds 10/20 and no ante, so
ICM and tournament context do not apply. ``cash6max-v0`` reuses the hybrid engine code
with ICM disabled; it is an UNVALIDATED experimental policy:

- it is not the champion, is never promoted automatically, and online chip results are
  not evidence of profitability (virtual chips, unknown field, small samples);
- the wrapper refuses tournament observations and antes, so MTT logic cannot leak in and
  this policy cannot be used in the MTT evaluation by mistake.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from poker_lab.agents.base import Agent
from poker_lab.agents.registry import AgentSpec, create_agent
from poker_lab.domain.actions import Action
from poker_lab.domain.observation import Observation

ROOT = Path(__file__).resolve().parents[4]
CASH_POLICY_LABEL = "cash6max-v0"


def cash_policy_spec(root: Path = ROOT) -> AgentSpec:
    return AgentSpec(
        algorithm="policy",
        version_label=CASH_POLICY_LABEL,
        checkpoint_path=str(root / "artifacts/checkpoints/pushfold-v2-ante.json"),  # read-only
        params={
            "hybrid": True,
            "table_path": str(root / "artifacts/tables/hu_class_equity_s200_seed20261026.json"),
            "samples": 150,
            "bluff_rate": 0.0,
            "icm": False,  # no ICM in cash games
        },
    )


class CashGamePolicy(Agent):
    """Guard wrapper: cash observations only (no tournament info, no ante)."""

    algorithm = "cash_policy"

    def __init__(self, inner: Agent, version_label: str = CASH_POLICY_LABEL) -> None:
        super().__init__(f"{inner.name}-cash", version_label, inner.seed)
        self.inner = inner

    def act(self, obs: Observation) -> Action:
        if obs.tournament is not None:
            raise ValueError("cash policy received a tournament observation")
        if obs.ante != 0:
            raise ValueError("cash policy received an ante (platform has none)")
        action = self.inner.act(obs)
        self.last_info = dict(getattr(self.inner, "last_info", {}) or {})
        return action

    def config(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm, "version_label": self.version_label, "inner": self.inner.config()}


def create_cash_policy(seed: int = 1, root: Path = ROOT) -> CashGamePolicy:
    return CashGamePolicy(create_agent(cash_policy_spec(root), CASH_POLICY_LABEL, seed))
