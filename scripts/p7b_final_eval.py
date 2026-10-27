"""P7b FINAL evaluation (seed root 20261028 — never used for tuning).

  python scripts/p7b_final_eval.py shard <i> <n>
  python scripts/p7b_final_eval.py finalize <n>

Pre-registered criteria (docs/MODEL_VERSIONS.md, docs/P7B_REPORT.md): primary scenario
'baseline' (n=400), key scenarios 'field_lag' and 'turbo_short' for regressions, Holm over
all challenger x {baseline, field_lag, turbo_short} tests, alpha 0.05, zero invalid actions.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7b_candidates import challengers, champion, references  # noqa: E402

from poker_lab.analytics.decision_metrics import compute_for_tournament  # noqa: E402
from poker_lab.evaluation.champion import Criteria, decide, record_and_apply  # noqa: E402
from poker_lab.evaluation.protocol import Protocol, Scenario, finish_run, merge_shards, run_shard  # noqa: E402
from poker_lab.evaluation.report import build_report  # noqa: E402
from poker_lab.persistence.db import open_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/p7b"
DB = OUT / "final.db"
SEED = 20261028
CRITERIA = Criteria(primary_scenario="baseline", key_scenarios=["field_lag", "turbo_short"], min_n=400)
TESTED = ["baseline", "field_lag", "turbo_short"]


def protocol() -> Protocol:
    return Protocol(
        name="p7b-final",
        seed=SEED,
        candidates=[champion(), *challengers(), *references()],
        scenarios=[
            Scenario(label="baseline", field_profile="mixed", n_tournaments=400),
            Scenario(label="field_lag", field_profile="lag", n_tournaments=200),
            Scenario(label="turbo_short", field_profile="mixed", starting_stack=1500, hands_per_level=5, n_tournaments=200),
            Scenario(label="field_tag", field_profile="tag", n_tournaments=100),
            Scenario(label="field_nit", field_profile="nit", n_tournaments=100),
            Scenario(label="field_station", field_profile="station", n_tournaments=100),
            Scenario(label="reentry", field_profile="mixed", reentry_levels=3, max_entries=3, n_tournaments=100),
            Scenario(label="top_heavy", field_profile="mixed", payout_percentages=[65.0, 35.0], n_tournaments=100),
        ],
        progressive_n=[50, 100, 200, 400],
        min_n_claim=200,
    )


def finalize(n_shards: int) -> None:
    p = protocol()
    t0 = time.perf_counter()
    merge_shards(DB, [OUT / f"final{i}.db" for i in range(n_shards)])
    conn = open_db(DB)
    rid = p.run_id()
    tids = [r[0] for r in conn.execute(
        "SELECT tournament_id FROM tournaments WHERE evaluation_run_id=? AND scenario_label LIKE '%|baseline|%'", (rid,)
    )]
    n_dm = sum(compute_for_tournament(conn, t, samples=100) for t in tids)
    rep = build_report(conn, p, baseline_candidate=champion().label, breakdown_scenario="baseline")
    # paired differences vs champion for the pre-registered tests
    rows = conn.execute(
        "SELECT t.scenario_label AS lbl, t.seed, f.net_profit FROM v_entry_financials f JOIN tournaments t"
        " ON t.tournament_id=f.tournament_id WHERE t.evaluation_run_id=? AND f.role='hero'", (rid,)
    ).fetchall()
    net: dict[tuple[str, str, int], float] = {}
    for r in rows:
        _, scen, cand = r["lbl"].split("|")
        net[(scen, cand, r["seed"])] = r["net_profit"] / 110.0
    champ = champion().label
    paired: dict[str, dict[str, list[float]]] = {}
    for ch in (c.label for c in challengers()):
        paired[ch] = {}
        for scen in TESTED:
            seeds = sorted(s for (sc, c, s) in net if sc == scen and c == champ)
            paired[ch][scen] = [net[(scen, ch, s)] - net[(scen, champ, s)] for s in seeds if (scen, ch, s) in net]
    invalid = {
        ch: conn.execute(
            "SELECT COUNT(*) FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
            " WHERE t.evaluation_run_id=? AND t.scenario_label LIKE ? AND d.participant_label='hero' AND d.action_valid=0",
            (rid, f"%|{ch}"),
        ).fetchone()[0]
        for ch in paired
    }
    decisions = decide(paired, invalid, CRITERIA, seed=SEED)
    ids = {r["version_label"]: r["agent_version_id"] for r in conn.execute("SELECT * FROM agent_versions WHERE name='pushfold'")}
    if conn.execute("SELECT COUNT(*) FROM agent_versions WHERE name='pushfold' AND status='champion'").fetchone()[0] == 0:
        conn.execute("UPDATE agent_versions SET status='champion' WHERE agent_version_id=?", (ids["p7"],))
    promoted = record_and_apply(
        conn,
        experiment_id=None,
        champion_version_id=ids["p7"],
        challenger_ids={"pushfold_v2_ante": ids["v2-ante"], "hybrid_v1": ids["hybrid-v1"]},
        decisions=decisions,
        criteria=CRITERIA,
        suite={"evaluation_run_id": rid, "seed": SEED, "tested_scenarios": TESTED},
    )
    rep["champion_challenger"] = {
        "criteria": CRITERIA.__dict__,
        "invalid_actions": invalid,
        "decisions": {k: {"decision": d.decision, "reason": d.reason, "tests": d.tests} for k, d in decisions.items()},
        "promoted_agent_version_id": promoted,
        "champion_after": dict(conn.execute("SELECT name, version_label FROM agent_versions WHERE status='champion'").fetchall()),
    }
    rep["decision_metrics_rows"] = n_dm
    rep["finalize_seconds"] = round(time.perf_counter() - t0, 1)
    path = OUT / "p7b_final_report.json"
    path.write_text(json.dumps(rep, indent=1, default=str))
    finish_run(conn, p, rep, path)
    print(json.dumps(rep["champion_challenger"], indent=1, default=str))


if __name__ == "__main__":
    if sys.argv[1] == "shard":
        i, n = int(sys.argv[2]), int(sys.argv[3])
        print(json.dumps(run_shard(OUT / f"final{i}.db", protocol(), i, n, log_every=200)))
    else:
        finalize(int(sys.argv[2]))
