"""P7c development set (seed 777002): choose bluff_rate for the challengers. Never used for promotion."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7c_common import CHAMPION, hybrid_spec, scenarios  # noqa: E402

from poker_lab.evaluation.protocol import Candidate, Protocol, merge_shards, run_shard  # noqa: E402
from poker_lab.evaluation.report import build_report  # noqa: E402
from poker_lab.persistence.db import open_db  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts/p7c"


def protocol() -> Protocol:
    cands = [
        CHAMPION,
        Candidate(label="v1_b0.2", spec=hybrid_spec("hybrid-v1-b0.2", 0.2), lineage="pushfold"),
        Candidate(label="v2_b0", spec=hybrid_spec("hybrid-v2-adaptive-b0", 0.0, True), lineage="pushfold"),
        Candidate(label="v2_b0.2", spec=hybrid_spec("hybrid-v2-adaptive-b0.2", 0.2, True), lineage="pushfold"),
    ]
    return Protocol(
        name="p7c-dev", seed=777002, candidates=cands,
        scenarios=scenarios({"robust_mix": 80, "adaptive_only": 60, "bluff_heavy": 60}), progressive_n=[60], min_n_claim=200,
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "shard":
        i, n = int(sys.argv[2]), int(sys.argv[3])
        print(json.dumps(run_shard(OUT / f"dev{i}.db", protocol(), i, n, log_every=100)), flush=True)
    else:
        n = int(sys.argv[2])
        merge_shards(OUT / "dev.db", [OUT / f"dev{i}.db" for i in range(n)])
        rep = build_report(open_db(OUT / "dev.db"), protocol(), "hybrid_v1", "robust_mix")
        (OUT / "dev_report.json").write_text(json.dumps(rep, indent=1, default=str))
        for scen, d in rep["paired_vs_baseline"].items():
            for c, v in d.items():
                print(scen, c, round(v["estimate"], 3), [round(v["ci_low"], 3), round(v["ci_high"], 3)], v["n"])
        for scen, d in rep["scenarios"].items():
            print(scen, {c: round(s["roi"]["estimate"], 3) for c, s in d.items()})
