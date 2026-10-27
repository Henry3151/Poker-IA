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
    "heuristic": {"bluff_freq", "tightness", "aggression", "stickiness"},
    "equity": {"samples", "call_margin", "value_multiplier", "raised_range", "icm", "adaptive"},
    "policy": {"fallback_samples", "hybrid", "table_path", "samples", "bluff_rate", "icm", "shove_max_bb", "cbet_freq"},
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
    if spec.params.get("hybrid"):
        from poker_lab.agents.hybrid import HybridAgent

        params = {k: v for k, v in spec.params.items() if k not in ("hybrid", "table_path", "fallback_samples")}
        if "table_path" not in spec.params:
            raise ValueError("hybrid policy requires table_path")
        hybrid: Agent = HybridAgent.from_checkpoint(
            spec.checkpoint_path, name, spec.version_label, seed, str(spec.params["table_path"]), **params
        )
        return hybrid
    if set(spec.params) - {"fallback_samples"}:
        raise ValueError("non-hybrid policy agents only accept fallback_samples")
    agent: Agent = PolicyAgent.from_checkpoint(spec.checkpoint_path, name, spec.version_label, seed, **spec.params)
    return agent


# Opponent profiles for sensitivity tests (heuristic variants with documented parameters).
OPPONENT_PROFILES: dict[str, AgentSpec] = {
    "tag": AgentSpec(algorithm="heuristic", version_label="tag", params={"tightness": 1, "aggression": 0.7, "bluff_freq": 0.08}),
    "lag": AgentSpec(algorithm="heuristic", version_label="lag", params={"tightness": -3, "aggression": 0.8, "bluff_freq": 0.25}),
    "nit": AgentSpec(algorithm="heuristic", version_label="nit", params={"tightness": 3, "aggression": 0.3, "bluff_freq": 0.0}),
    "station": AgentSpec(
        algorithm="heuristic", version_label="station", params={"tightness": -3, "aggression": 0.1, "stickiness": 3.0, "bluff_freq": 0.02}
    ),
    "random": AgentSpec(algorithm="random", version_label="v1"),
}
