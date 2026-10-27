"""P7c final data-integrity checks (read-only; run after finalize, before reading results).

Checks: completeness per (scenario, candidate) vs the frozen SCALE; no non-completed
tournaments; CRN pairing (same seed set for every candidate within a scenario); one hero per
tournament; ledger reconciliation for every tournament; chip conservation (sum of final
stacks / payouts); invalid hero actions; duplicate tournament ids across shards.

    python scripts/p7c_integrity.py artifacts/p7c/final.db > artifacts/p7c/p7c_integrity.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p7c_common import CHAMPION, REFERENCES  # noqa: E402
from p7c_final import CHALLENGERS, SCALE, protocol  # noqa: E402

from poker_lab.persistence.repositories import reconcile_tournament_ledger  # noqa: E402


def main(path: str) -> dict:
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)  # never checkpoint/modify
    conn.row_factory = sqlite3.Row
    rid = protocol().run_id()
    cands = [c.label for c in (CHAMPION, *CHALLENGERS, *REFERENCES)]
    out: dict = {"db": path, "evaluation_run_id": rid, "checks": {}, "ok": True}

    def check(name: str, ok: bool, detail: object) -> None:
        out["checks"][name] = {"ok": bool(ok), "detail": detail}
        out["ok"] = out["ok"] and bool(ok)

    status = dict(conn.execute("SELECT status, COUNT(*) FROM tournaments WHERE evaluation_run_id=? GROUP BY status", (rid,)).fetchall())
    check("all_completed", set(status) == {"completed"}, status)

    rows = conn.execute("SELECT tournament_id, scenario_label, seed FROM tournaments WHERE evaluation_run_id=?", (rid,)).fetchall()
    seeds: dict[tuple[str, str], set[int]] = defaultdict(set)
    for r in rows:
        _, scen, cand = r["scenario_label"].split("|")
        seeds[(scen, cand)].add(r["seed"])
    counts = {f"{s}|{c}": len(seeds[(s, c)]) for s in SCALE for c in cands}
    expected = {f"{s}|{c}": SCALE[s] for s in SCALE for c in cands}
    check("completeness_vs_frozen_scale", counts == expected and len(rows) == sum(expected.values()),
          {"total": len(rows), "expected_total": sum(expected.values()),
           "mismatches": {k: (counts[k], expected[k]) for k in expected if counts[k] != expected[k]}})
    crn_bad = {s: sorted({c for c in cands if seeds[(s, c)] != seeds[(s, CHAMPION.label)]}) for s in SCALE}
    check("crn_pairing_same_seeds", not any(crn_bad.values()), {s: v for s, v in crn_bad.items() if v})

    heroes = conn.execute(
        "SELECT t.tournament_id, SUM(e.role='hero') AS h FROM tournaments t JOIN tournament_entries e ON e.tournament_id=t.tournament_id"
        " WHERE t.evaluation_run_id=? GROUP BY t.tournament_id HAVING h != 1", (rid,)).fetchall()
    check("exactly_one_hero", not heroes, len(heroes))

    bad_ledger = {}
    for r in rows:
        p = reconcile_tournament_ledger(conn, r["tournament_id"])
        if p:
            bad_ledger[r["tournament_id"]] = p
    check("ledger_reconciliation", not bad_ledger, {"failures": len(bad_ledger), "examples": dict(list(bad_ledger.items())[:3])})

    cons = conn.execute(
        "SELECT t.tournament_id, t.prize_pool, SUM(f.payout) AS paid, SUM(f.net_profit) AS net, t.fee_per_entry * t.total_entries AS fees"
        " FROM tournaments t JOIN v_entry_financials f ON f.tournament_id=t.tournament_id WHERE t.evaluation_run_id=?"
        " GROUP BY t.tournament_id HAVING paid != prize_pool OR net != -fees", (rid,)).fetchall()
    check("money_conservation (payouts=prize pool, sum net = -fees)", not cons, len(cons))

    inv = dict(conn.execute(
        "SELECT substr(t.scenario_label, instr(substr(t.scenario_label, instr(t.scenario_label,'|')+1),'|')+instr(t.scenario_label,'|')+1),"
        " COUNT(*) FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
        " WHERE t.evaluation_run_id=? AND d.action_valid=0 GROUP BY 1", (rid,)).fetchall())
    check("zero_invalid_actions_recorded", not inv, inv)

    dup = conn.execute("SELECT COUNT(*) - COUNT(DISTINCT tournament_id) FROM tournaments").fetchone()[0]
    check("no_duplicate_tournaments", dup == 0, dup)
    out["integrity_check_sqlite"] = conn.execute("PRAGMA quick_check").fetchone()[0]
    out["ok"] = out["ok"] and out["integrity_check_sqlite"] == "ok"
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=1, default=str))
