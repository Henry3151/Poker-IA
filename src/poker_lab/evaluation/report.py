"""Evaluation report: financial summaries, progressive samples, paired comparisons and breakdowns.

Every number is labelled as an observation (counts, sums), an estimate with a CI, or a
verdict derived by the conservative rule in ``stats.verdict``. Breakdown buckets with
fewer than ``MIN_N_FOR_BUCKET`` units are flagged ``insufficient_sample``.
"""

from __future__ import annotations

import json
import random
import sqlite3
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from poker_lab.evaluation.finance import summarize
from poker_lab.evaluation.protocol import Protocol
from poker_lab.evaluation.stats import CI, MIN_N_FOR_BUCKET, bootstrap_ci, verdict


def _hero_rows(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    sql = (
        "SELECT f.*, t.seed, t.scenario_label, t.entrant_count, t.total_entries, t.tournament_id AS tid"
        " FROM v_entry_financials f JOIN tournaments t ON t.tournament_id = f.tournament_id"
        " WHERE t.evaluation_run_id = ? AND f.role = 'hero' AND t.status = 'completed'"
    )
    return [dict(r) for r in conn.execute(sql, (run_id,))]


def cluster_ratio_ci(
    clusters: Sequence[tuple[float, float]], *, level: float = 0.95, resamples: int = 2000, seed: int = 0
) -> CI:
    """CI for sum(num)/sum(den) resampling whole clusters (tournaments), since hands within a
    tournament are not independent."""
    n = len(clusters)
    den = sum(c[1] for c in clusters)
    if n == 0 or den == 0:
        return CI(float("nan"), float("nan"), float("nan"), n, level, "cluster_bootstrap")
    est = sum(c[0] for c in clusters) / den
    rng = random.Random(seed)
    vals = []
    for _ in range(resamples):
        smp = [clusters[rng.randrange(n)] for _ in range(n)]
        d = sum(c[1] for c in smp)
        vals.append(sum(c[0] for c in smp) / d if d else 0.0)
    vals.sort()
    a = (1 - level) / 2
    return CI(est, vals[int(a * resamples)], vals[int((1 - a) * resamples) - 1], n, level, "cluster_bootstrap")


def build_report(conn: sqlite3.Connection, protocol: Protocol, baseline_candidate: str, breakdown_scenario: str) -> dict[str, Any]:
    rid = protocol.run_id()
    rows = _hero_rows(conn, rid)
    by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        _, scen, cand = r["scenario_label"].split("|")
        by[(scen, cand)].append(r)
    seed_to_k = {(s.label, protocol.seed_for(s, k)): k for s in protocol.scenarios for k in range(s.n_tournaments)}
    for (scen, _), lst in by.items():
        for r in lst:
            r["k"] = seed_to_k[(scen, r["seed"])]
        lst.sort(key=lambda r: r["k"])

    report: dict[str, Any] = {
        "evaluation_run_id": rid,
        "protocol": json.loads(protocol.model_dump_json()),
        "units": "simulated buy-in units (SIM); no real money",
        "scenarios": {},
        "progressive": {},
        "paired_vs_baseline": {},
        "breakdowns": {},
        "allin_luck": {},
    }
    for scen in protocol.scenarios:
        report["scenarios"][scen.label] = {
            c.label: summarize(by.get((scen.label, c.label), []), seed=protocol.seed, min_n=protocol.min_n_claim)
            for c in protocol.candidates
        }
        base = {r["k"]: r for r in by.get((scen.label, baseline_candidate), [])}
        cost_per_entry = scen.buy_in + scen.fee
        report["paired_vs_baseline"][scen.label] = {}
        for c in protocol.candidates:
            if c.label == baseline_candidate:
                continue
            diffs = [
                (r["net_profit"] - base[r["k"]]["net_profit"]) / cost_per_entry
                for r in by.get((scen.label, c.label), [])
                if r["k"] in base
            ]
            ci = bootstrap_ci(diffs, seed=protocol.seed + 7)
            report["paired_vs_baseline"][scen.label][c.label] = {
                "metric": "mean paired difference in net profit per tournament, in buy-ins (buy_in+fee)",
                **ci.as_dict(),
                "verdict": verdict(ci, min_n=protocol.min_n_claim),
            }
    # progressive sample sizes on the breakdown (baseline) scenario
    scen0 = next(s for s in protocol.scenarios if s.label == breakdown_scenario)
    for c in protocol.candidates:
        lst = by.get((scen0.label, c.label), [])
        prog = []
        for n in protocol.progressive_n:
            if n > len(lst):
                break
            s = summarize(lst[:n], seed=protocol.seed, min_n=protocol.min_n_claim)
            prog.append({"n": n, "roi": s["roi"], "roi_verdict": s["roi_verdict"], "itm_rate": s["itm_rate"]["estimate"]})
        report["progressive"][c.label] = prog
    report["breakdowns"] = hand_breakdowns(conn, rid, scen0.label, protocol)
    report["decision_quality"] = decision_breakdowns(conn, rid, scen0.label)
    report["allin_luck"] = allin_luck(conn, rid, scen0.label)
    return report


def _bucket_eff(bb_stack: float) -> str:
    if bb_stack < 10:
        return "<10bb"
    if bb_stack < 20:
        return "10-20bb"
    if bb_stack < 40:
        return "20-40bb"
    return "40bb+"


def hand_breakdowns(conn: sqlite3.Connection, rid: str, scen_label: str, protocol: Protocol) -> dict[str, Any]:
    """Hero net result in big blinds per hand, by phase / position / starting stack bucket,
    with cluster-bootstrap CIs over tournaments."""
    sql = (
        "SELECT t.scenario_label, t.tournament_id, h.phase, hp.position, hp.starting_stack, h.big_blind, hp.net_chips"
        " FROM hand_players hp JOIN hands h ON h.hand_id = hp.hand_id JOIN tournaments t ON t.tournament_id = h.tournament_id"
        " JOIN tournament_entries e ON e.entry_id = hp.entry_id"
        " WHERE t.evaluation_run_id = ? AND e.role = 'hero' AND t.scenario_label LIKE ?"
    )
    out: dict[str, Any] = {}
    data: dict[str, dict[str, dict[str, dict[str, list[float]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0.0])))
    )
    for r in conn.execute(sql, (rid, f"%|{scen_label}|%")):
        cand = r["scenario_label"].split("|")[2]
        net_bb = r["net_chips"] / r["big_blind"]
        for dim, key in (
            ("phase", r["phase"] or "unknown"),
            ("position", r["position"]),
            ("stack_bucket", _bucket_eff(r["starting_stack"] / r["big_blind"])),
        ):
            cell = data[cand][dim][key][r["tournament_id"]]
            cell[0] += net_bb
            cell[1] += 1
    for cand, dims in data.items():
        out[cand] = {}
        for dim, keys in dims.items():
            out[cand][dim] = {}
            for key, clusters in sorted(keys.items()):
                cl = [(v[0], v[1]) for v in clusters.values()]
                hands = int(sum(c[1] for c in cl))
                ci = cluster_ratio_ci(cl, seed=protocol.seed, resamples=1000)
                out[cand][dim][key] = {
                    "metric": "net bb per hand",
                    "hands": hands,
                    **ci.as_dict(),
                    "flag": "insufficient_sample" if hands < MIN_N_FOR_BUCKET else verdict(ci, min_n=30),
                }
    return out


def decision_breakdowns(conn: sqlite3.Connection, rid: str, scen_label: str) -> dict[str, Any]:
    """Decision mix and decision-time math (no outcomes): by action and by pot type.

    ``call_margin`` = equity - pot odds for calls; negative margins are calls that the
    decision-time estimate did not justify (subject to the equity basis' approximation).
    """
    sql = (
        "SELECT t.scenario_label, d.action_type, m.pot_type, m.phase, m.equity, m.pot_odds, m.equity_basis, m.ev_call_chips,"
        " d.big_blind FROM decisions d JOIN decision_metrics m ON m.decision_id = d.decision_id"
        " JOIN hands h ON h.hand_id = d.hand_id JOIN tournaments t ON t.tournament_id = h.tournament_id"
        " WHERE t.evaluation_run_id = ? AND t.scenario_label LIKE ?"
    )
    acc: dict[str, dict[str, Any]] = defaultdict(lambda: {"by_action": defaultdict(int), "by_pot_type": defaultdict(lambda: defaultdict(int)), "calls": [], "n": 0, "bases": defaultdict(int)})
    for r in conn.execute(sql, (rid, f"%|{scen_label}|%")):
        cand = r["scenario_label"].split("|")[2]
        a = acc[cand]
        a["n"] += 1
        a["by_action"][r["action_type"]] += 1
        a["by_pot_type"][r["pot_type"]][r["action_type"]] += 1
        a["bases"][r["equity_basis"].split(":")[0]] += 1
        if r["action_type"] == "call" and r["pot_odds"] > 0:
            a["calls"].append(r["equity"] - r["pot_odds"])
    out = {}
    for cand, a in acc.items():
        calls = a["calls"]
        ci = bootstrap_ci(calls, seed=1, resamples=1000) if calls else None
        out[cand] = {
            "decisions": a["n"],
            "action_mix": {k: round(v / a["n"], 4) for k, v in sorted(a["by_action"].items())},
            "by_pot_type": {k: dict(v) for k, v in sorted(a["by_pot_type"].items())},
            "equity_basis_counts": dict(a["bases"]),
            "calls": len(calls),
            "call_margin_mean": ci.as_dict() if ci else None,
            "calls_below_pot_odds_rate": round(sum(1 for x in calls if x < 0) / len(calls), 4) if calls else None,
            "flag": "insufficient_sample" if len(calls) < MIN_N_FOR_BUCKET else "ok",
        }
    return out


def allin_luck(conn: sqlite3.Connection, rid: str, scen_label: str) -> dict[str, Any]:
    """Chips won/lost to the runout in all-in hands (actual - all-in EV), in big blinds.

    Uses offline hole cards AFTER the hand (never available to the agent). Positive = ran
    above expectation. Separates card luck from the decision to get all-in.
    """
    sql = (
        "SELECT t.scenario_label, hp.net_chips, hp.allin_ev_chips, h.big_blind FROM hand_players hp"
        " JOIN hands h ON h.hand_id = hp.hand_id JOIN tournaments t ON t.tournament_id = h.tournament_id"
        " JOIN tournament_entries e ON e.entry_id = hp.entry_id"
        " WHERE t.evaluation_run_id = ? AND e.role = 'hero' AND hp.allin_ev_chips IS NOT NULL AND t.scenario_label LIKE ?"
    )
    acc: dict[str, list[float]] = defaultdict(list)
    ev_acc: dict[str, list[float]] = defaultdict(list)
    for r in conn.execute(sql, (rid, f"%|{scen_label}|%")):
        cand = r["scenario_label"].split("|")[2]
        acc[cand].append((r["net_chips"] - r["allin_ev_chips"]) / r["big_blind"])
        ev_acc[cand].append(r["allin_ev_chips"] / r["big_blind"])
    return {
        c: {
            "allin_hands": len(v),
            "luck_bb_total": round(sum(v), 2),
            "luck_bb_mean": bootstrap_ci(v, seed=2, resamples=1000).as_dict(),
            "allin_ev_bb_total": round(sum(ev_acc[c]), 2),
        }
        for c, v in acc.items()
    }
