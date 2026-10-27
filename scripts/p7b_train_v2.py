"""Train pushfold-v2-ante (P7b, hypothesis H1). The P7 checkpoint is NOT modified."""

import json
from pathlib import Path

from poker_lab.application.training_service import run_pushfold_training
from poker_lab.persistence.db import open_db

ROOT = Path(__file__).resolve().parents[1]
ANTE = 0.125  # ante/bb ratio of most tournament levels (levels 4-10 of DEFAULT_LEVELS)
CONTEXTS = [(0.0, 0.0)] + [(ANTE, ANTE * k) for k in range(5)]  # dead = antes of 0..4 folded players
ASSUMPTIONS = [
    "game: heads-up push/fold abstraction (SB: fold/all-in; BB: fold/call), 169 classes, chip EV, no ICM",
    "each player pays ante a from its stack; extra dead money d = antes of players who already folded",
    f"contexts (ante_bb, dead_bb): {CONTEXTS}; stacks 5/8/10/12/15/20 bb (stack includes blind and ante)",
    "equity table: Monte Carlo 200 samples per class pair, seed 20261026 (same table as pushfold-p7)",
    "training: external-sampling MCCFR, 150000 iterations per context, seed 20261101",
    "valid only for SB-vs-BB spots; elsewhere the agent falls back to other logic",
]

if __name__ == "__main__":
    conn = open_db(ROOT / "artifacts/p7b/p7b_lab.db")
    out = run_pushfold_training(
        conn, iterations=150_000, seed=20261101, version_label="v2-ante", artifacts_dir=ROOT / "artifacts",
        table_samples=200, contexts=CONTEXTS, assumptions=ASSUMPTIONS,
    )
    Path(ROOT / "artifacts/p7b/training_v2_ante.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("sha256", "elapsed_seconds", "peak_memory_mb")}), out["metrics"]["mean_exploitability_bb"])
