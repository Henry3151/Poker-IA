"""Build agents from declarative specs (no arbitrary code execution from configs)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from poker_lab.agents.base import Agent
from poker_lab.agents.equity_agent import EquityAgent
from poker_lab.agents.heuristic import HeuristicAgent
from poker_lab.agents.random_agent import RandomAgent


class AgentSpec(BaseModel):
    algorithm: str
    version_label: str = "v1"
    params: dict[str, Any] = Field(default_factory=dict)
    checkpoint_path: str | None = None

    @property
    def key(self) -> str:
        return f"{self.algorithm}@{self.version_label}"


_ALLOWED_PARAMS = {
    "random": set(),
    "heuristic": {"bluff_freq"},
    "equity": {"samples", "call_margin", "value_multiplier", "raised_range"},
    "policy": {"fallback_samples"},
}


def create_agent(spec: AgentSpec, name: str, seed: int) -> Agent:
    allowed = _ALLOWED_PARAMS.get(spec.algorithm)
    if allowed is None:
        raise ValueError(f"unknown algorithm {spec.algorithm!r}")
    unknown = set(spec.params) - allowed
    if unknown:
        raise ValueError(f"unknown params for {spec.algorithm}: {sorted(unknown)}")
    if spec.algorithm == "random":
        return RandomAgent(name, spec.version_label, seed)
    if spec.algorithm == "heuristic":
        return HeuristicAgent(name, spec.version_label, seed, **spec.params)
    if spec.algorithm == "equity":
        return EquityAgent(name, spec.version_label, seed, **spec.params)
    from poker_lab.agents.policy_agent import PolicyAgent  # trained policy (P6)

    if not spec.checkpoint_path:
        raise ValueError("policy agent requires checkpoint_path")
    agent: Agent = PolicyAgent.from_checkpoint(spec.checkpoint_path, name, spec.version_label, seed, **spec.params)
    return agent
