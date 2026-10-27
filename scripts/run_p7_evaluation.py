"""P7 evaluation driver.

Usage:
  python scripts/run_p7_evaluation.py train                    # trains the push/fold policy (version p7)
  python scripts/run_p7_evaluation.py shard <i> <n>            # runs shard i of n
  python scripts/run_p7_evaluation.py finalize <n>             # merges shards, decision metrics, report
All outputs go to artifacts/p7/ (git-ignored).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from poker_lab.agents.registry import AgentSpec
from poker_lab.analytics.decision_metrics import compute_for_tournament
from poker_lab.application.training_service import run_pushfold_training
from poker_lab.evaluation.protocol import Candidate, Protocol, Scenario, finish_run, merge_shards, run_shard
from poker_lab.evaluation.report import build_report
from poker_lab.persistence.db import open_db

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "p7"
MAIN_DB = OUT / "p7_lab.db"
CKPT = ROOT / "artifacts" / "checkpoints" / "pushfold-p7.json"
SEED = 20261027
EQ_SAMPLES = 120


def protocol() -> Protocol:
    return Protocol(
        name="p7-mtt-6max",
        seed=SEED,
        candidates=[
            Candidate(label="random", spec=AgentSpec(algorithm="random")),
            Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
            Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": EQ_SAMPLES})),
            Candidate(
                label="equity_icm_adaptive",
                spec=AgentSpec(algorithm="equity", version_label="icm_adaptive", params={"samples": EQ_SAMPLES, "icm": True, "adaptive": True}),
                lineage="equity_icm_adaptive",
            ),
            Candidate(
                label="pushfold_policy",
                spec=AgentSpec(algorithm="policy", version_label="p7", checkpoint_path=str(CKPT), params={"fallback_samples": EQ_SAMPLES}),
                lineage="pushfold",
            ),
        ],
        scenarios=[
            Scenario(label="baseline", field_profile="mixed", n_tournaments=400),
            Scenario(label="field_lag", field_profile="lag", n_tournaments=120),
            Scenario(label="field_nit", field_profile="nit", n_tournaments=120),
            Scenario(label="field_station", field_profile="station", n_tournaments=120),
            Scenario(label="field_random", field_profile="random", n_tournaments=60),
            Scenario(label="turbo_short", field_profile="mixed", starting_stack=1500, hands_per_level=5, n_tournaments=120),
            Scenario(label="reentry", field_profile="mixed", reentry_levels=3, max_entries=3, n_tournaments=120),
            Scenario(label="top_heavy", field_profile="mixed", payout_percentages=[65.0, 35.0], n_tournaments=120),
        ],
        progressive_n=[25, 50, 100, 200, 400],
        min_n_claim=200,
    )


def main() -> None:
    cmd = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "train":
        if CKPT.exists():
            print(f"checkpoint already exists: {CKPT} (skipping training)")
            return
        conn = open_db(MAIN_DB)
        out = run_pushfold_training(
            conn, iterations=200_000, seed=SEED, version_label="p7", artifacts_dir=ROOT / "artifacts", table_samples=200
        )
        (OUT / "training_p7.json").write_text(json.dumps(out, indent=1))
        print(json.dumps({k: out[k] for k in ("sha256", "elapsed_seconds", "peak_memory_mb", "throughput_per_second")}))
    elif cmd == "shard":
        i, n = int(sys.argv[2]), int(sys.argv[3])
        print(json.dumps(run_shard(OUT / f"shard{i}.db", protocol(), i, n, log_every=100)))
    elif cmd == "finalize":
        n = int(sys.argv[2])
        p = protocol()
        t0 = time.perf_counter()
        added = merge_shards(MAIN_DB, [OUT / f"shard{i}.db" for i in range(n)])
        conn = open_db(MAIN_DB)
        tids = [r[0] for r in conn.execute(
            "SELECT tournament_id FROM tournaments WHERE evaluation_run_id=? AND scenario_label LIKE '%|baseline|%'", (p.run_id(),)
        )]
        n_dm = sum(compute_for_tournament(conn, t, samples=100) for t in tids)
        rep = build_report(conn, p, baseline_candidate="heuristic", breakdown_scenario="baseline")
        rep["merge_rows_added"] = added
        rep["decision_metrics_rows"] = n_dm
        rep["finalize_seconds"] = round(time.perf_counter() - t0, 1)
        path = OUT / "p7_report.json"
        path.write_text(json.dumps(rep, indent=1, default=str))
        finish_run(conn, p, rep, path)
        print(f"report: {path}  decision_metrics={n_dm}")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
