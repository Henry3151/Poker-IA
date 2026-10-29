"""Generic, read-only integrity verification of an evaluation database against its frozen report.

Checks: all tournaments completed; completeness per (scenario, candidate) vs the frozen protocol;
common-random-number pairing (same seed set for every candidate in a scenario); exactly one hero
per tournament; ledger reconciliation; money conservation; invalid actions; duplicates; and
SQLite's quick_check (optional; slow on multi-GB files).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from poker_lab.lab.readonly import connect_ro
from poker_lab.persistence.repositories import reconcile_tournament_ledger

Progress = Callable[[str], None]


def verify_run(db_path: Path, report: dict[str, Any], quick_check: bool = False,
               progress: Progress | None = None) -> dict[str, Any]:
    say = progress or (lambda _msg: None)
    rid = report["evaluation_run_id"]
    scen_n = {s["label"]: int(s["n_tournaments"]) for s in report["protocol"]["scenarios"]}
    cands = [c["label"] for c in report["protocol"]["candidates"]]
    out: dict[str, Any] = {"db": db_path.as_posix(), "evaluation_run_id": rid, "checks": {}, "ok": True}

    def check(name: str, ok: bool, detail: object) -> None:
        out["checks"][name] = {"ok": bool(ok), "detail": detail}
        out["ok"] = out["ok"] and bool(ok)

    conn = connect_ro(db_path)
    try:
        say("status dos torneios")
        status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM tournaments WHERE evaluation_run_id=? GROUP BY status", (rid,))}
        check("all_completed", bool(status) and set(status) == {"completed"}, status)

        say("completude e pareamento")
        rows = conn.execute("SELECT tournament_id, scenario_label, seed FROM tournaments WHERE evaluation_run_id=?", (rid,)).fetchall()
        seeds: dict[tuple[str, str], set[int]] = defaultdict(set)
        for r in rows:
            _, scen, cand = r["scenario_label"].split("|")
            seeds[(scen, cand)].add(r["seed"])
        mism = {f"{s}|{c}": (len(seeds[(s, c)]), n) for s, n in scen_n.items() for c in cands if len(seeds[(s, c)]) != n}
        expected_total = sum(scen_n.values()) * len(cands)
        check("completeness_vs_frozen_protocol", not mism and len(rows) == expected_total,
              {"total": len(rows), "expected_total": expected_total, "mismatches": mism})
        crn_bad = {s: sorted(c for c in cands if seeds[(s, c)] != seeds[(s, cands[0])]) for s in scen_n}
        check("crn_pairing_same_seeds", not any(crn_bad.values()), {s: v for s, v in crn_bad.items() if v})

        say("um herói por torneio")
        heroes = conn.execute(
            "SELECT COUNT(*) FROM (SELECT t.tournament_id, SUM(e.role='hero') h FROM tournaments t"
            " JOIN tournament_entries e ON e.tournament_id=t.tournament_id WHERE t.evaluation_run_id=?"
            " GROUP BY t.tournament_id HAVING h != 1)", (rid,)).fetchone()[0]
        check("exactly_one_hero", heroes == 0, heroes)

        say(f"conciliação do ledger ({len(rows)} torneios)")
        bad: dict[str, list[str]] = {}
        for i, r in enumerate(rows):
            p = reconcile_tournament_ledger(conn, r["tournament_id"])
            if p:
                bad[r["tournament_id"]] = p
            if i and i % 1000 == 0:
                say(f"ledger {i}/{len(rows)}")
        check("ledger_reconciliation", not bad, {"failures": len(bad), "examples": dict(list(bad.items())[:3])})

        say("conservação do dinheiro")
        cons = conn.execute(
            "SELECT COUNT(*) FROM (SELECT t.tournament_id, t.prize_pool, SUM(f.payout) paid, SUM(f.net_profit) net,"
            " t.fee_per_entry * t.total_entries fees FROM tournaments t JOIN v_entry_financials f"
            " ON f.tournament_id=t.tournament_id WHERE t.evaluation_run_id=? GROUP BY t.tournament_id"
            " HAVING paid != prize_pool OR net != -fees)", (rid,)).fetchone()[0]
        check("money_conservation", cons == 0, cons)

        say("ações inválidas")
        inv = conn.execute(
            "SELECT COUNT(*) FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t"
            " ON t.tournament_id=h.tournament_id WHERE t.evaluation_run_id=? AND d.action_valid=0", (rid,)).fetchone()[0]
        check("zero_invalid_actions", inv == 0, inv)

        dup = conn.execute("SELECT COUNT(*) - COUNT(DISTINCT tournament_id) FROM tournaments").fetchone()[0]
        check("no_duplicate_tournaments", dup == 0, dup)

        if quick_check:
            say("PRAGMA quick_check (pode demorar)")
            qc = conn.execute("PRAGMA quick_check").fetchone()[0]
            check("sqlite_quick_check", qc == "ok", qc)
    finally:
        conn.close()
    say("concluído")
    return out
