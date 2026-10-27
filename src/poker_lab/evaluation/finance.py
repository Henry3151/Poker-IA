"""Financial metrics per agent, computed from the ledger (single source of truth).

Definitions (also in docs/FINANCIAL_METRICS.md):
- cost of an entry  = sum over its entries (first + re-entries) of (buy_in + fee)
- payout            = prize received for the final place (0 if out of the money)
- net profit        = payout - cost
- ROI (aggregate)   = sum(net) / sum(cost) across tournaments
- ROI (per entry)   = net / cost, averaged across tournaments (reported separately)
- ITM rate          = share of tournaments with payout > 0 (re-entries do not add ITM chances)
- drawdown          = max peak-to-trough decline of cumulative net, in tournament order
Re-entries and fees are counted once each via unique ledger keys (no double counting).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from poker_lab.evaluation.stats import bootstrap_ci, max_drawdown, quantiles, ratio_bootstrap_ci, verdict


def entry_rows(
    conn: sqlite3.Connection,
    *,
    evaluation_run_id: str | None = None,
    scenario_label: str | None = None,
    role: str | None = "hero",
) -> list[dict[str, Any]]:
    clauses = ["t.status='completed'"]
    params: list[Any] = []
    if evaluation_run_id:
        clauses.append("t.evaluation_run_id=?")
        params.append(evaluation_run_id)
    if scenario_label:
        clauses.append("t.scenario_label=?")
        params.append(scenario_label)
    if role:
        clauses.append("f.role=?")
        params.append(role)
    sql = (
        "SELECT f.*, t.seed, t.scenario_label, t.total_entries, t.entrant_count, t.started_at, a.name AS agent_name,"
        " a.version_label FROM v_entry_financials f JOIN tournaments t ON t.tournament_id=f.tournament_id"
        " JOIN agent_versions a ON a.agent_version_id=f.agent_version_id WHERE " + " AND ".join(clauses) +
        " ORDER BY t.started_at, t.tournament_id"
    )
    return [dict(r) for r in conn.execute(sql, params)]


def summarize(rows: list[dict[str, Any]], seed: int = 0, min_n: int = 200) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n_tournaments": 0}
    net = [float(r["net_profit"]) for r in rows]
    cost = [float(r["buy_ins_total"] + r["fees_total"]) for r in rows]
    itm = [float(r["itm"]) for r in rows]
    places = [r["final_place"] / r["entrant_count"] for r in rows]
    roi_ci = ratio_bootstrap_ci(net, cost, seed=seed)
    net_ci = bootstrap_ci(net, seed=seed + 1)
    itm_ci = bootstrap_ci(itm, seed=seed + 2)
    per_entry_roi = [n_ / c if c else 0.0 for n_, c in zip(net, cost, strict=True)]
    return {
        "n_tournaments": n,
        "total_cost": sum(cost),
        "total_payout": sum(float(r["payout"]) for r in rows),
        "total_net": sum(net),
        "entries_total": sum(int(r["entries_count"]) for r in rows),
        "reentries_total": sum(int(r["entries_count"]) - 1 for r in rows),
        "roi": roi_ci.as_dict(),
        "roi_verdict": verdict(roi_ci, min_n=min_n),
        "mean_per_entry_roi": round(sum(per_entry_roi) / n, 6),
        "net_per_tournament": net_ci.as_dict(),
        "itm_rate": itm_ci.as_dict(),
        "wins": sum(1 for r in rows if r["final_place"] == 1),
        "mean_relative_place": round(sum(places) / n, 4),  # 0 = first, 1 = last
        "net_quantiles": {k: round(v, 2) for k, v in quantiles(net).items()},
        "drawdown": max_drawdown(net),
    }
