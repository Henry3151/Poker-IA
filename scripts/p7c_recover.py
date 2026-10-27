"""P7c operational recovery: remove INCOMPLETE ('running') tournaments from a shard DB so the
frozen, resumable run_shard can recompute them with the SAME deterministic seeds.

Does not touch completed tournaments, the protocol, seeds or analysis code. The original
files must already be preserved (incident folder with SHA256SUMS) before running this.

    python scripts/p7c_recover.py artifacts/p7c/final0.db artifacts/p7c/final1.db
"""

from __future__ import annotations

import json
import sqlite3
import sys


def purge_incomplete(path: str) -> dict:
    c = sqlite3.connect(path)
    tids = [r[0] for r in c.execute("SELECT tournament_id FROM tournaments WHERE status!='completed'")]
    out: dict = {"db": path, "incomplete_tournaments": tids, "deleted": {}}
    if not tids:
        return out
    q = ",".join("?" * len(tids))
    hands = f"SELECT hand_id FROM hands WHERE tournament_id IN ({q})"
    decs = f"SELECT decision_id FROM decisions WHERE hand_id IN ({hands})"
    stmts = [
        ("decision_metrics", f"DELETE FROM decision_metrics WHERE decision_id IN ({decs})"),
        ("explanations", f"DELETE FROM explanations WHERE tournament_id IN ({q}) OR hand_id IN ({hands})"),
        ("notes", f"DELETE FROM notes WHERE tournament_id IN ({q}) OR hand_id IN ({hands})"),
        ("audit_issues", f"DELETE FROM audit_issues WHERE tournament_id IN ({q}) OR hand_id IN ({hands})"),
        ("decisions", f"DELETE FROM decisions WHERE hand_id IN ({hands})"),
        ("action_events", f"DELETE FROM action_events WHERE hand_id IN ({hands})"),
        ("offline_hole_cards", f"DELETE FROM offline_hole_cards WHERE hand_id IN ({hands})"),
        ("hand_players", f"DELETE FROM hand_players WHERE hand_id IN ({hands})"),
        ("hands", f"DELETE FROM hands WHERE tournament_id IN ({q})"),
        ("financial_ledger", f"DELETE FROM financial_ledger WHERE tournament_id IN ({q})"),
        ("entry_reentries", f"DELETE FROM entry_reentries WHERE tournament_id IN ({q})"),
        ("tournament_events", f"DELETE FROM tournament_events WHERE tournament_id IN ({q})"),
        ("tournament_entries", f"DELETE FROM tournament_entries WHERE tournament_id IN ({q})"),
        ("tournaments", f"DELETE FROM tournaments WHERE tournament_id IN ({q})"),
    ]
    with c:
        for name, sql in stmts:
            n_params = sql.count("?")
            params = (tids * (n_params // len(tids) + 1))[:n_params]
            out["deleted"][name] = c.execute(sql, params).rowcount
    out["quick_check"] = c.execute("PRAGMA quick_check").fetchone()[0]
    out["status_counts"] = dict(c.execute("SELECT status, COUNT(*) FROM tournaments GROUP BY status").fetchall())
    c.close()
    return out


if __name__ == "__main__":
    print(json.dumps([purge_incomplete(p) for p in sys.argv[1:]], indent=1))
