"""P7c robustness cycle: candidates and scenarios (shared by dev and final runs)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7b_candidates import CKPT_P7, CKPT_V2, TABLE  # noqa: E402

from poker_lab.agents.registry import OPPONENT_PROFILES, AgentSpec  # noqa: E402
from poker_lab.evaluation.protocol import Candidate, Scenario  # noqa: E402


def hybrid_spec(label: str, bluff_rate: float = 0.0, adaptive: bool = False) -> AgentSpec:
    params: dict = {"hybrid": True, "table_path": TABLE, "samples": 150, "bluff_rate": bluff_rate, "icm": True}
    if adaptive:
        params["adaptive_steal"] = True
    return AgentSpec(algorithm="policy", version_label=label, checkpoint_path=CKPT_V2, params=params)


CHAMPION = Candidate(label="hybrid_v1", spec=hybrid_spec("hybrid-v1"), lineage="pushfold")


def challengers(beta_v2: float, beta_v1: float) -> list[Candidate]:
    out = [Candidate(label="hybrid_v2_adaptive", spec=hybrid_spec(f"hybrid-v2-adaptive-b{beta_v2:g}", beta_v2, True), lineage="pushfold")]
    if beta_v1 != 0.0:
        out.append(Candidate(label="hybrid_v1_bluffcatch", spec=hybrid_spec(f"hybrid-v1-b{beta_v1:g}", beta_v1), lineage="pushfold"))
    return out


REFERENCES = [
    Candidate(
        label="pushfold_p7",
        spec=AgentSpec(algorithm="policy", version_label="p7", checkpoint_path=CKPT_P7, params={"fallback_samples": 120}),
        lineage="pushfold",
    ),
    Candidate(label="lag", spec=OPPONENT_PROFILES["lag"], lineage="ref_lag"),
]

EXTRA = {
    "hybrid-v1": hybrid_spec("hybrid-v1"),
    "p7": AgentSpec(algorithm="policy", version_label="p7", checkpoint_path=CKPT_P7, params={"fallback_samples": 120}),
    "v2-ante": AgentSpec(algorithm="policy", version_label="v2-ante", checkpoint_path=CKPT_V2, params={"fallback_samples": 120}),
    "equity": AgentSpec(algorithm="equity", params={"samples": 120}),
}

ROBUST_MIX = ["tag", "lag", "nit", "station", "adaptive_tag", "adaptive_lag", "bluffer40", "bluffer60"]


def scenarios(scale: dict[str, int]) -> list[Scenario]:
    s = {
        "robust_mix": Scenario(label="robust_mix", field_mix=ROBUST_MIX, n_tournaments=scale.get("robust_mix", 1)),
        "adaptive_only": Scenario(label="adaptive_only", field_mix=["adaptive_tag", "adaptive_lag"], n_tournaments=scale.get("adaptive_only", 1)),
        "bluff_heavy": Scenario(label="bluff_heavy", field_mix=["bluffer40", "bluffer60", "maniac"], n_tournaments=scale.get("bluff_heavy", 1)),
        "baseline_mixed": Scenario(label="baseline_mixed", field_profile="mixed", n_tournaments=scale.get("baseline_mixed", 1)),
        "selfplay_hybrid": Scenario(label="selfplay_hybrid", field_mix=["hybrid-v1"], extra_specs=EXTRA, n_tournaments=scale.get("selfplay_hybrid", 1)),
        "versions_mix": Scenario(
            label="versions_mix", field_mix=["hybrid-v1", "p7", "v2-ante", "equity"], extra_specs=EXTRA, n_tournaments=scale.get("versions_mix", 1)
        ),
    }
    return [s[k] for k in scale if scale[k] > 0]
