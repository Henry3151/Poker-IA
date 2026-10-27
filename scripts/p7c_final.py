"""P7c FINAL robustness evaluation (seed root 20261029 — never used for tuning).

Pre-registered (before running):
- champion: hybrid-v1. Challengers (chosen on the dev set by mean paired difference):
  hybrid-v2-adaptive with bluff_rate 0.2; hybrid-v1 with bluff_rate 0.2 (control).
- primary scenario robust_mix (n=400). Promote only if: primary paired CI > 0 AND Holm p < 0.05
  over all challenger x scenario tests; NO scenario with paired CI entirely < 0; point estimate
  >= 0 in at least 4 of 6 scenarios; zero invalid actions. Otherwise keep the champion.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7c_common import CHAMPION, REFERENCES, challengers, scenarios  # noqa: E402

from poker_lab.evaluation.champion import Criteria, decide  # noqa: E402
from poker_lab.evaluation.protocol import Protocol, finish_run, merge_shards, run_shard  # noqa: E402
from poker_lab.evaluation.report import build_report  # noqa: E402
from poker_lab.persistence.db import open_db  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts/p7c"
SEED = 20261029
SCALE = {"robust_mix": 400, "adaptive_only": 200, "bluff_heavy": 200, "baseline_mixed": 200, "selfplay_hybrid": 100, "versions_mix": 100}
CHALLENGERS = challengers(beta_v2=0.2, beta_v1=0.2)


def protocol() -> Protocol:
    return Protocol(
        name="p7c-final", seed=SEED, candidates=[CHAMPION, *CHALLENGERS, *REFERENCES],
        scenarios=scenarios(SCALE), progressive_n=[50, 100, 200, 400], min_n_claim=200,
    )


def finalize(n: int) -> None:
    p = protocol()
    t0 = time.perf_counter()
    merge_shards(OUT / "final.db", [OUT / f"final{i}.db" for i in range(n)])
    conn = open_db(OUT / "final.db")
    rep = build_report(conn, p, CHAMPION.label, "robust_mix")
    rid = p.run_id()
    net: dict[tuple[str, str, int], float] = {}
    for r in conn.execute(
        "SELECT t.scenario_label AS lbl, t.seed, f.net_profit FROM v_entry_financials f JOIN tournaments t"
        " ON t.tournament_id=f.tournament_id WHERE t.evaluation_run_id=? AND f.role='hero'", (rid,)
    ):
        _, scen, cand = r["lbl"].split("|")
        net[(scen, cand, r["seed"])] = r["net_profit"] / 110.0
    paired: dict[str, dict[str, list[float]]] = {}
    for ch in (c.label for c in CHALLENGERS):
        paired[ch] = {}
        for scen in SCALE:
            seeds = sorted(s for (sc, c, s) in net if sc == scen and c == CHAMPION.label)
            paired[ch][scen] = [net[(scen, ch, s)] - net[(scen, CHAMPION.label, s)] for s in seeds if (scen, ch, s) in net]
    invalid = {
        ch: conn.execute(
            "SELECT COUNT(*) FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
            " WHERE t.evaluation_run_id=? AND t.scenario_label LIKE ? AND d.participant_label='hero' AND d.action_valid=0",
            (rid, f"%|{ch}"),
        ).fetchone()[0]
        for ch in paired
    }
    crit = Criteria(primary_scenario="robust_mix", key_scenarios=list(SCALE), min_n=400)
    dec = decide(paired, invalid, crit, seed=SEED)
    final = {}
    for ch, d in dec.items():
        nonneg = sum(1 for t in d.tests.values() if t["estimate"] >= 0)
        decision = d.decision
        reason = d.reason
        if decision == "promote" and nonneg < 4:
            decision, reason = "keep_champion", f"point estimate >= 0 in only {nonneg}/6 scenarios"
        final[ch] = {"decision": decision, "reason": reason, "nonnegative_scenarios": nonneg, "tests": d.tests}
    rep["champion_challenger"] = {"criteria": crit.__dict__, "extra_rule": ">=4/6 non-negative", "invalid_actions": invalid, "decisions": final}
    rep["finalize_seconds"] = round(time.perf_counter() - t0, 1)
    path = OUT / "p7c_final_report.json"
    path.write_text(json.dumps(rep, indent=1, default=str))
    finish_run(conn, p, rep, path)
    print(json.dumps({k: {"decision": v["decision"], "reason": v["reason"]} for k, v in final.items()}, indent=1))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "shard":
        i, n = int(sys.argv[2]), int(sys.argv[3])
        print(json.dumps(run_shard(OUT / f"final{i}.db", protocol(), i, n, log_every=300)), flush=True)
    else:
        finalize(int(sys.argv[2]))
