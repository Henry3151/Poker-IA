"""Development-set check of the challengers (seed root 777001). Not used for promotion."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7b_candidates import challengers, champion  # noqa: E402

from poker_lab.evaluation.protocol import Protocol, Scenario, merge_shards, run_shard  # noqa: E402
from poker_lab.evaluation.report import build_report  # noqa: E402
from poker_lab.persistence.db import open_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/p7b"


def protocol(n: int) -> Protocol:
    return Protocol(
        name="p7b-dev-check", seed=777001, candidates=[champion(), *challengers()],
        scenarios=[Scenario(label="dev_mixed", field_profile="mixed", n_tournaments=n)], progressive_n=[n], min_n_claim=200,
    )


if __name__ == "__main__":
    cmd, n = sys.argv[1], int(sys.argv[2])
    if cmd == "shard":
        i, k = int(sys.argv[3]), int(sys.argv[4])
        print(run_shard(OUT / f"devcheck{i}.db", protocol(n), i, k, log_every=50))
    else:
        k = int(sys.argv[3])
        merge_shards(OUT / "devcheck.db", [OUT / f"devcheck{i}.db" for i in range(k)])
        rep = build_report(open_db(OUT / "devcheck.db"), protocol(n), "pushfold_p7", "dev_mixed")
        (OUT / "devcheck_report.json").write_text(json.dumps(rep, indent=1, default=str))
        for c, s in rep["scenarios"]["dev_mixed"].items():
            print(c, s["roi"]["estimate"], s["roi"]["ci_low"], s["roi"]["ci_high"], "ITM", s["itm_rate"]["estimate"], "wins", s["wins"])
        print(json.dumps(rep["paired_vs_baseline"], indent=1))
