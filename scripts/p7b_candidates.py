"""Candidate definitions for P7b (shared by dev checks and the final evaluation)."""

from pathlib import Path

from poker_lab.agents.registry import OPPONENT_PROFILES, AgentSpec
from poker_lab.evaluation.protocol import Candidate

ROOT = Path(__file__).resolve().parents[1]
CKPT_P7 = str(ROOT / "artifacts/checkpoints/pushfold-p7.json")
CKPT_V2 = str(ROOT / "artifacts/checkpoints/pushfold-v2-ante.json")
TABLE = str(ROOT / "artifacts/tables/hu_class_equity_s200_seed20261026.json")
BLUFF_RATE = 0.0  # selected on the development set (artifacts/p7b/calibration.json)


def champion() -> Candidate:
    return Candidate(
        label="pushfold_p7",
        spec=AgentSpec(algorithm="policy", version_label="p7", checkpoint_path=CKPT_P7, params={"fallback_samples": 120}),
        lineage="pushfold",
    )


def challengers() -> list[Candidate]:
    return [
        Candidate(
            label="pushfold_v2_ante",
            spec=AgentSpec(algorithm="policy", version_label="v2-ante", checkpoint_path=CKPT_V2, params={"fallback_samples": 120}),
            lineage="pushfold",
        ),
        Candidate(
            label="hybrid_v1",
            spec=AgentSpec(
                algorithm="policy", version_label="hybrid-v1", checkpoint_path=CKPT_V2,
                params={"hybrid": True, "table_path": TABLE, "samples": 150, "bluff_rate": BLUFF_RATE, "icm": True},
            ),
            lineage="pushfold",
        ),
    ]


def references() -> list[Candidate]:
    return [
        Candidate(label="random", spec=AgentSpec(algorithm="random")),
        Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
        Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": 120})),
        Candidate(label="lag", spec=OPPONENT_PROFILES["lag"], lineage="ref_lag"),
    ]
