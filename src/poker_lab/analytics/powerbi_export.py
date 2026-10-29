"""P8: Power BI star-schema export with mandatory reconciliation.

Layout (one folder per table, one file per run, so Power BI's "Folder" source combines runs):

    <out>/<Table>/<RunLabel>.parquet   (or .csv with --format csv)
    <out>/manifest.json                (row counts, sha256 per file, schema version, sources)
    <out>/reconciliation.json          (every KPI recomputed in SQL vs exported files vs report)

Design rules (see powerbi/POWERBI_MODEL_SPEC_P8.md):
- confidence intervals and p-values are NOT computed in DAX; they are exported ready-made from
  the frozen evaluation reports (FactScenarioSummary, FactPairedComparison, FactBreakdownCI, ...);
- source databases are opened read-only (``mode=ro``);
- the export refuses to finish (raises ``ReconciliationError``) if any KPI diverges;
- no hidden information is exported per decision: only the hero's own observation-derived
  fields (no opponents' hole cards, no observation JSON).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poker_lab.evaluation.report import _bucket_eff

SCHEMA_VERSION = "p8-1"
COST_PER_ENTRY_DEFAULT = 110.0
EPS = 1e-6

PROFILE_CLASS = {
    "tag": "exploitable_static", "nit": "exploitable_static", "station": "exploitable_static",
    "random": "exploitable_static", "v1": "exploitable_static",
    "lag": "aggressive_static", "maniac": "aggressive_static", "bluffer40": "aggressive_static",
    "bluffer60": "aggressive_static",
    "adaptive_tag": "adaptive", "adaptive_lag": "adaptive",
}
FIELD_CLASS_LABEL = {
    "exploitable_static": "Explorável (estático)",
    "aggressive_static": "Agressivo / blefador (estático)",
    "adaptive": "Adaptativo",
    "self_play": "Self-play / versões do agente",
    "mixed": "Misto",
}
POSITIONS = ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
STACK_BUCKETS = ["<10bb", "10-20bb", "20-40bb", "40bb+"]
PHASES = ["early", "middle", "bubble", "itm", "final_table", "unknown"]


class ReconciliationError(RuntimeError):
    """An exported KPI does not match its SQL recomputation or the frozen report."""


@dataclass(frozen=True)
class RunSource:
    label: str  # P7 / P7b / P7c
    set_role: str  # final (dev sets are not exported by default)
    db_path: Path
    report_path: Path
    steal_path: Path | None = None


@dataclass
class Tables:
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))

    def add(self, table: str, rows: Iterable[dict[str, Any]]) -> None:
        self.rows[table].extend(rows)


def default_sources(root: Path) -> list[RunSource]:
    return [
        RunSource("P7", "final", root / "artifacts/p7/p7_lab.db", root / "docs/p7_artifacts/p7_report.json"),
        RunSource("P7b", "final", root / "artifacts/p7b/final.db", root / "docs/p7b_artifacts/p7b_final_report.json"),
        RunSource("P7c", "final", root / "artifacts/p7c/final.db", root / "docs/p7c_artifacts/p7c_final_report.json",
                  root / "docs/p7c_artifacts/steal_analysis.json"),
    ]


def _ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def profile_class(version_label: str, algorithm: str) -> str:
    if version_label in PROFILE_CLASS:
        return PROFILE_CLASS[version_label] if algorithm != "equity" else "exploitable_static"
    return "self_play"


def scenario_class(shares: dict[str, float]) -> str:
    """Dominant class when it holds >= 75% of field seats, else 'mixed'."""
    if not shares:
        return "mixed"
    cls, share = max(shares.items(), key=lambda kv: kv[1])
    return cls if share >= 0.75 - EPS else "mixed"


def _baseline_candidate(report: dict[str, Any]) -> str:
    cands = [c["label"] for c in report["protocol"]["candidates"]]
    first = next(iter(report["paired_vs_baseline"].values()))
    missing = [c for c in cands if c not in first]
    if len(missing) != 1:
        raise ValueError(f"cannot infer baseline candidate: {missing}")
    return str(missing[0])


def _primary_scenario(report: dict[str, Any]) -> str:
    cc = report.get("champion_challenger")
    if cc:
        return str(cc["criteria"]["primary_scenario"])
    return str(report["protocol"]["scenarios"][0]["label"])


def _ci(prefix: str, v: dict[str, Any] | None) -> dict[str, Any]:
    v = v or {}
    return {f"{prefix}": v.get("estimate"), f"{prefix}CiLow": v.get("ci_low"), f"{prefix}CiHigh": v.get("ci_high"),
            f"{prefix}N": v.get("n"), f"{prefix}Method": v.get("method")}


# ---------------------------------------------------------------------------------------------- run
RUN_TABLES = ["DimRun", "DimCandidate", "DimScenario", "FactEntryResult", "FactHandHero", "FactDecision", "FactLedger",
              "FactAudit", "FactScenarioSummary", "FactPairedComparison", "FactBreakdownCI", "FactAllinLuck", "FactProgressive"]


def export_run(src: RunSource, t: Tables) -> dict[str, Any]:
    for name in RUN_TABLES:
        t.rows.setdefault(name, [])  # declare: every table exists (with a stable schema) even when empty
    report = json.loads(src.report_path.read_text())
    rid = report["evaluation_run_id"]
    run_key = src.label
    conn = _ro(src.db_path)
    db_rid = {r[0] for r in conn.execute("SELECT DISTINCT evaluation_run_id FROM tournaments")}
    if db_rid != {rid}:
        raise ReconciliationError(f"{src.label}: database runs {db_rid} != report run {rid}")
    baseline = _baseline_candidate(report)
    primary = _primary_scenario(report)
    decisions = (report.get("champion_challenger") or {}).get("decisions", {})
    proto = report["protocol"]

    er = conn.execute("SELECT * FROM evaluation_runs WHERE evaluation_run_id=?", (rid,)).fetchone()
    t.add("DimRun", [{
        "RunKey": run_key, "EvaluationRunId": rid, "RunLabel": src.label, "SetRole": src.set_role,
        "ProtocolName": proto["name"], "SeedRoot": proto["seed"], "PrimaryScenario": primary,
        "BaselineCandidate": baseline, "CodeVersion": er["code_version"] if er else None,
        "StartedAt": er["started_at"] if er else None, "CompletedAt": er["completed_at"] if er else None,
        "Units": report.get("units"),
    }])

    for c in proto["candidates"]:
        lab = c["label"]
        role = "baseline_champion" if lab == baseline else ("challenger" if lab in decisions else "reference")
        spec = c["spec"]
        t.add("DimCandidate", [{
            "CandidateKey": f"{run_key}|{lab}", "RunKey": run_key, "Candidate": lab, "Lineage": c.get("lineage"),
            "Algorithm": spec.get("algorithm"), "VersionLabel": spec.get("version_label"),
            "Checkpoint": Path(spec["checkpoint_path"]).name if spec.get("checkpoint_path") else None,
            "BluffRate": (spec.get("params") or {}).get("bluff_rate"),
            "RoleInRun": role, "PromotionDecision": decisions.get(lab, {}).get("decision"),
            "PromotionReason": decisions.get(lab, {}).get("reason"),
        }])

    # field composition per scenario (from the database, not from labels)
    comp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in conn.execute(
        "SELECT t.scenario_label, a.version_label, a.algorithm, COUNT(*) n FROM tournament_entries e"
        " JOIN agent_versions a ON a.agent_version_id=e.agent_version_id JOIN tournaments t ON t.tournament_id=e.tournament_id"
        " WHERE e.role='field' GROUP BY 1,2,3"
    ):
        scen = r["scenario_label"].split("|")[1]
        comp[scen][profile_class(r["version_label"], r["algorithm"])] += r["n"]
        t.rows.setdefault("_profiles", []).append({"Profile": r["version_label"], "Algorithm": r["algorithm"]})
    for s in proto["scenarios"]:
        lab = s["label"]
        tot = sum(comp[lab].values()) or 1
        shares = {k: v / tot for k, v in comp[lab].items()}
        cls = scenario_class(shares)
        t.add("DimScenario", [{
            "ScenarioKey": f"{run_key}|{lab}", "RunKey": run_key, "Scenario": lab, "IsPrimary": lab == primary,
            "FieldProfile": s.get("field_profile"), "FieldMix": ",".join(s.get("field_mix") or []) or None,
            "FieldClass": cls, "FieldClassLabel": FIELD_CLASS_LABEL[cls],
            "ShareExploitable": round(shares.get("exploitable_static", 0.0), 4),
            "ShareAggressive": round(shares.get("aggressive_static", 0.0), 4),
            "ShareAdaptive": round(shares.get("adaptive", 0.0), 4),
            "ShareSelfPlay": round(shares.get("self_play", 0.0), 4),
            "Entrants": s.get("entrants"), "StartingStack": s.get("starting_stack"), "BlindScale": s.get("blind_scale"),
            "BuyIn": s.get("buy_in"), "Fee": s.get("fee"), "ReentryLevels": s.get("reentry_levels"),
            "Payout": "/".join(f"{p:g}" for p in s.get("payout_percentages") or []), "NTournaments": s.get("n_tournaments"),
        }])

    # entries (hero and field)
    for r in conn.execute(
        "SELECT t.scenario_label, t.seed, t.tournament_id, f.entry_id, f.role, e.participant_label, a.version_label, a.algorithm,"
        " f.final_place, f.entries_count, f.buy_ins_total, f.fees_total, f.payout, f.net_profit, f.roi, f.itm"
        " FROM v_entry_financials f JOIN tournaments t ON t.tournament_id=f.tournament_id"
        " JOIN tournament_entries e ON e.entry_id=f.entry_id JOIN agent_versions a ON a.agent_version_id=e.agent_version_id"
    ):
        _, scen, cand = r["scenario_label"].split("|")
        cost = (r["buy_ins_total"] or 0) + (r["fees_total"] or 0)
        t.add("FactEntryResult", [{
            "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
            "TournamentId": r["tournament_id"], "Seed": r["seed"], "EntryId": r["entry_id"], "Role": r["role"],
            "Participant": r["participant_label"],
            "OpponentProfile": None if r["role"] == "hero" else r["version_label"],
            "OpponentClass": None if r["role"] == "hero" else profile_class(r["version_label"], r["algorithm"]),
            "FinalPlace": r["final_place"], "EntriesCount": r["entries_count"], "BuyIns": r["buy_ins_total"],
            "Fees": r["fees_total"], "Cost": cost, "Payout": r["payout"], "NetProfit": r["net_profit"],
            "NetBuyIns": (r["net_profit"] / cost) if cost else None, "ROI": r["roi"], "ITM": r["itm"],
        }])

    # hero hands
    for r in conn.execute(
        "SELECT t.scenario_label, t.tournament_id, h.hand_id, h.phase, h.level_index, h.ante, h.big_blind, h.player_count,"
        " hp.position, hp.starting_stack, hp.net_chips, hp.allin_ev_chips, hp.went_to_showdown, hp.won_at_showdown"
        " FROM hand_players hp JOIN hands h ON h.hand_id=hp.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
        " JOIN tournament_entries e ON e.entry_id=hp.entry_id WHERE e.role='hero'"
    ):
        _, scen, cand = r["scenario_label"].split("|")
        bb = r["big_blind"]
        ev = r["allin_ev_chips"]
        t.add("FactHandHero", [{
            "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
            "TournamentId": r["tournament_id"], "HandId": r["hand_id"], "Phase": r["phase"] or "unknown",
            "Position": r["position"], "StackBucket": _bucket_eff(r["starting_stack"] / bb), "Level": r["level_index"],
            "HasAnte": int((r["ante"] or 0) > 0), "Players": r["player_count"], "StartingStackBB": r["starting_stack"] / bb,
            "NetBB": r["net_chips"] / bb, "AllIn": int(ev is not None),
            "AllInEvBB": (ev / bb) if ev is not None else None,
            "LuckBB": ((r["net_chips"] - ev) / bb) if ev is not None else None,
            "WentToShowdown": r["went_to_showdown"], "WonAtShowdown": r["won_at_showdown"],
        }])

    # hero decisions (own information only; no observation JSON, no opponents' cards)
    for r in conn.execute(
        "SELECT t.scenario_label, d.decision_id, d.hand_id, d.street, d.position, d.action_type, d.action_amount, d.to_call,"
        " d.pot_before, d.effective_stack, d.big_blind, d.equity_estimate, d.pot_odds, d.action_valid, d.fallback_applied,"
        " d.decision_latency_ms, d.agent_info_json FROM decisions d JOIN hands h ON h.hand_id=d.hand_id"
        " JOIN tournaments t ON t.tournament_id=h.tournament_id WHERE d.participant_label='hero'"
    ):
        _, scen, cand = r["scenario_label"].split("|")
        bb = r["big_blind"] or 1
        info = json.loads(r["agent_info_json"]) if r["agent_info_json"] else {}
        comp_ = info.get("component") or info.get("path") or info.get("method") or info.get("rule")
        t.add("FactDecision", [{
            "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
            "DecisionId": r["decision_id"], "HandId": r["hand_id"], "Street": r["street"], "Position": r["position"],
            "Action": r["action_type"], "AmountBB": (r["action_amount"] or 0) / bb, "ToCallBB": (r["to_call"] or 0) / bb,
            "PotBB": (r["pot_before"] or 0) / bb, "EffectiveStackBB": (r["effective_stack"] or 0) / bb,
            "Equity": r["equity_estimate"], "PotOdds": r["pot_odds"],
            "EquityMinusPotOdds": (r["equity_estimate"] - r["pot_odds"])
            if r["equity_estimate"] is not None and r["pot_odds"] is not None else None,
            "Component": comp_, "Valid": r["action_valid"], "Fallback": r["fallback_applied"],
            "LatencyMs": r["decision_latency_ms"],
        }])

    # ledger and audit
    for r in conn.execute(
        "SELECT l.ledger_id, l.tournament_id, l.entry_id, l.kind, l.entry_number, l.amount, l.currency, e.role"
        " FROM financial_ledger l JOIN tournament_entries e ON e.entry_id=l.entry_id"
    ):
        t.add("FactLedger", [{"RunKey": run_key, "LedgerId": r["ledger_id"], "TournamentId": r["tournament_id"],
                              "EntryId": r["entry_id"], "Role": r["role"], "Kind": r["kind"], "EntryNumber": r["entry_number"],
                              "Amount": r["amount"], "Currency": r["currency"]}])
    for r in conn.execute("SELECT issue_id, issue_type, severity, tournament_id, hand_id, decision_id, created_at FROM audit_issues"):
        t.add("FactAudit", [{"RunKey": run_key, **dict(r)}])

    # ready-made statistics from the frozen report
    for scen, cands in report["scenarios"].items():
        for cand, v in cands.items():
            t.add("FactScenarioSummary", [{
                "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
                "NTournaments": v["n_tournaments"], "TotalCost": v["total_cost"], "TotalPayout": v["total_payout"],
                "TotalNet": v["total_net"], "Entries": v["entries_total"], "Reentries": v["reentries_total"],
                **_ci("Roi", v["roi"]), "RoiVerdict": v["roi_verdict"], **_ci("Itm", v["itm_rate"]),
                **_ci("NetPerTournament", v["net_per_tournament"]), "Wins": v["wins"],
                "MeanRelativePlace": v.get("mean_relative_place"), "MaxDrawdown": v["drawdown"]["max_drawdown"],
                **{f"NetP{q[1:]}": v["net_quantiles"][q] for q in v.get("net_quantiles", {})},
            }])
    tests = {(ch, s): d2 for ch, d in decisions.items() for s, d2 in d["tests"].items()}
    for scen, cands in report["paired_vs_baseline"].items():
        for cand, v in cands.items():
            tt = tests.get((cand, scen), {})
            t.add("FactPairedComparison", [{
                "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
                "BaselineCandidate": baseline, "Metric": "net per tournament, buy-ins (challenger - baseline)",
                **_ci("Diff", v), "Verdict": v.get("verdict"),
                "DecisionTestEstimate": tt.get("estimate"), "DecisionTestCiLow": tt.get("ci_low"),
                "DecisionTestCiHigh": tt.get("ci_high"), "PValue": tt.get("p_value"), "PHolm": tt.get("p_holm"),
                "IsDecisionTest": int(bool(tt)), "PromotionDecision": decisions.get(cand, {}).get("decision"),
            }])
    for cand, dims in report.get("breakdowns", {}).items():
        for dim, groups in dims.items():
            for g, v in groups.items():
                t.add("FactBreakdownCI", [{
                    "RunKey": run_key, "ScenarioKey": f"{run_key}|{primary}", "CandidateKey": f"{run_key}|{cand}",
                    "Dimension": dim, "Group": g, "Hands": v.get("hands"), **_ci("BBPerHand", v), "Flag": v.get("flag"),
                }])
    for cand, v in report.get("allin_luck", {}).items():
        t.add("FactAllinLuck", [{"RunKey": run_key, "ScenarioKey": f"{run_key}|{primary}", "CandidateKey": f"{run_key}|{cand}",
                                 "AllinHands": v["allin_hands"], "LuckBBTotal": v["luck_bb_total"],
                                 "AllinEvBBTotal": v["allin_ev_bb_total"], **_ci("LuckBBMean", v["luck_bb_mean"])}])
    for cand, steps in report.get("progressive", {}).items():
        for st in steps:
            t.add("FactProgressive", [{"RunKey": run_key, "ScenarioKey": f"{run_key}|{primary}", "CandidateKey": f"{run_key}|{cand}",
                                       "SampleN": st["n"], **_ci("Roi", st["roi"]), "RoiVerdict": st.get("roi_verdict"),
                                       "ItmRate": st.get("itm_rate")}])
    if src.steal_path and src.steal_path.exists():
        steal = json.loads(src.steal_path.read_text())
        for scen, cands in steal.items():
            for cand, x in cands.items():
                rr = x.get("resteal_response") or {}
                t.add("FactSteal", [{
                    "RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}", "CandidateKey": f"{run_key}|{cand}",
                    "Opportunities": x["late_first_in_opps"], "StealRate": x["steal_rate"],
                    "WonImmediately": x["steal_won_immediately"], **_ci("NetPerSteal", x.get("steal_net_bb_per_hand")),
                    "EvPerOpportunityBB": x.get("ev_per_opportunity_open_line_bb"), "RestealFaced": x.get("resteal_faced"),
                    "VsRestealFold": rr.get("fold"), "VsRestealCall": rr.get("call"), "VsRestealRaise": rr.get("raise"),
                    "StealRateFirstHalf": x["steal_rate_first_half"], "StealRateSecondHalf": x["steal_rate_second_half"],
                }])
                for dim, groups in (x.get("by_dimension_steal_net_bb") or {}).items():
                    for g, v in groups.items():
                        t.add("FactStealByDimension", [{"RunKey": run_key, "ScenarioKey": f"{run_key}|{scen}",
                                                        "CandidateKey": f"{run_key}|{cand}", "Dimension": dim, "Group": g,
                                                        **_ci("NetPerSteal", v)}])
    rec = reconcile_run(src, conn, report, t)
    conn.close()
    return rec


# ---------------------------------------------------------------------------------------------- reconciliation
def reconcile_run(src: RunSource, conn: sqlite3.Connection, report: dict[str, Any], t: Tables) -> dict[str, Any]:
    """Recompute every headline KPI three ways (SQL / exported rows / frozen report) and compare."""
    run_key = src.label
    problems: list[str] = []
    checks = 0
    sql: dict[tuple[str, str], dict[str, float]] = {}
    for r in conn.execute(
        "SELECT t.scenario_label, COUNT(*) n, SUM(f.net_profit) net, SUM(f.buy_ins_total+f.fees_total) cost,"
        " SUM(f.itm) itm, SUM(f.payout) payout FROM v_entry_financials f JOIN tournaments t ON t.tournament_id=f.tournament_id"
        " WHERE f.role='hero' GROUP BY t.scenario_label"
    ):
        _, scen, cand = r["scenario_label"].split("|")
        sql[(scen, cand)] = {"n": r["n"], "net": r["net"], "cost": r["cost"], "itm": r["itm"], "payout": r["payout"]}
    exp: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"n": 0, "net": 0.0, "cost": 0.0, "itm": 0, "payout": 0.0})
    for row in t.rows["FactEntryResult"]:
        if row["RunKey"] != run_key or row["Role"] != "hero":
            continue
        k = (row["ScenarioKey"].split("|")[1], row["CandidateKey"].split("|")[1])
        e = exp[k]
        e["n"] += 1
        e["net"] += row["NetProfit"]
        e["cost"] += row["Cost"]
        e["itm"] += row["ITM"]
        e["payout"] += row["Payout"]
    for scen, cands in report["scenarios"].items():
        for cand, v in cands.items():
            s, x = sql.get((scen, cand)), exp.get((scen, cand))
            if s is None or x is None:
                problems.append(f"{scen}/{cand}: missing in SQL or export")
                continue
            for name, a, b, c in (
                ("tournaments", s["n"], x["n"], v["n_tournaments"]),
                ("net", s["net"], x["net"], v["total_net"]),
                ("cost", s["cost"], x["cost"], v["total_cost"]),
                ("payout", s["payout"], x["payout"], v["total_payout"]),
                ("roi", s["net"] / s["cost"], x["net"] / x["cost"], v["roi"]["estimate"]),
                ("itm", s["itm"] / s["n"], x["itm"] / x["n"], v["itm_rate"]["estimate"]),
            ):
                checks += 1
                tol = 5e-6 if name in ("roi", "itm") else 1e-6
                if abs(a - b) > tol or abs(a - c) > max(tol, 1e-6 * abs(a)):
                    problems.append(f"{scen}/{cand} {name}: sql={a} export={b} report={c}")
    # bb/hand point estimates of the primary-scenario breakdown
    primary = _primary_scenario(report)
    agg: dict[tuple[str, str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in t.rows["FactHandHero"]:
        if row["RunKey"] != run_key or row["ScenarioKey"] != f"{run_key}|{primary}":
            continue
        cand = row["CandidateKey"].split("|")[1]
        for dim, key in (("phase", row["Phase"]), ("position", row["Position"]), ("stack_bucket", row["StackBucket"])):
            cell = agg[(cand, dim, key)]
            cell[0] += row["NetBB"]
            cell[1] += 1
    for cand, dims in report.get("breakdowns", {}).items():
        for dim, groups in dims.items():
            for g, v in groups.items():
                checks += 1
                got = agg.get((cand, dim, g))
                if got is None or int(got[1]) != v["hands"] or abs(got[0] / got[1] - v["estimate"]) > 5e-6:
                    problems.append(f"breakdown {cand}/{dim}/{g}: export={got} report=({v['hands']}, {v['estimate']})")
    # ledger reconciliation per run: hero cost in ledger == hero cost in entries
    led = conn.execute(
        "SELECT -SUM(CASE WHEN l.kind IN ('buy_in','fee') THEN l.amount END), SUM(CASE WHEN l.kind='payout' THEN l.amount END)"
        " FROM financial_ledger l JOIN tournament_entries e ON e.entry_id=l.entry_id WHERE e.role='hero'"
    ).fetchone()
    checks += 2
    tot_cost = sum(v["cost"] for v in sql.values())
    tot_pay = sum(v["payout"] for v in sql.values())
    if abs((led[0] or 0) - tot_cost) > 1e-6 or abs((led[1] or 0) - tot_pay) > 1e-6:
        problems.append(f"ledger hero cost/payout {led[0]}/{led[1]} != entries {tot_cost}/{tot_pay}")
    return {"run": run_key, "evaluation_run_id": report["evaluation_run_id"], "checks": checks, "problems": problems,
            "ok": not problems}


# ---------------------------------------------------------------------------------------------- static dims & writing
def static_dims(t: Tables) -> None:
    t.add("DimPosition", [{"Position": p, "PositionOrder": i} for i, p in enumerate(POSITIONS)])
    t.add("DimStackBucket", [{"StackBucket": b, "StackBucketOrder": i} for i, b in enumerate(STACK_BUCKETS)])
    t.add("DimPhase", [{"Phase": p, "PhaseOrder": i} for i, p in enumerate(PHASES)])
    t.add("DimFieldClass", [{"FieldClass": k, "FieldClassLabel": v, "FieldClassOrder": i}
                            for i, (k, v) in enumerate(FIELD_CLASS_LABEL.items())])
    seen = {}
    for p in t.rows.pop("_profiles", []):
        seen[p["Profile"]] = profile_class(p["Profile"], p["Algorithm"])
    t.add("DimOpponentProfile", [{"OpponentProfile": k, "OpponentClass": v, "OpponentClassLabel": FIELD_CLASS_LABEL[v]}
                                 for k, v in sorted(seen.items())])


SHARED_TABLES = {"DimPosition", "DimStackBucket", "DimPhase", "DimFieldClass", "DimOpponentProfile"}
# tables that may legitimately be empty still need a stable schema for Power BI
EMPTY_SCHEMAS = {
    "FactAudit": ["RunKey", "issue_id", "issue_type", "severity", "tournament_id", "hand_id", "decision_id", "created_at"],
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_tables(t: Tables, out: Path, fmt: str = "parquet") -> list[dict[str, Any]]:
    files = []
    for table, rows in sorted(t.rows.items()):
        if table.startswith("_"):
            continue
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            groups["all" if table in SHARED_TABLES else r["RunKey"]].append(r)
        if not rows:
            if (out / table).exists():
                continue  # another run already wrote this table
            groups["empty"] = []
        for part, prow in groups.items():
            d = out / table
            d.mkdir(parents=True, exist_ok=True)
            path = d / f"{part}.{fmt}"
            cols = list(dict.fromkeys(k for r in prow for k in r)) if prow else EMPTY_SCHEMAS.get(table, ["RunKey"])
            if fmt == "parquet":
                import pyarrow as pa
                import pyarrow.parquet as pq

                tbl = pa.Table.from_pylist(prow) if prow else pa.table({c: pa.array([], pa.string()) for c in cols})
                pq.write_table(tbl, path, compression="zstd")
            else:
                with path.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=cols)
                    w.writeheader()
                    w.writerows(prow)
            files.append({"table": table, "file": str(path.relative_to(out)), "rows": len(prow), "sha256": _sha256(path)})
    return files


def export_powerbi(sources: list[RunSource], out: Path, fmt: str = "parquet") -> dict[str, Any]:
    """Export run by run (bounded memory) into a staging folder; publish only if every run reconciles."""
    import shutil

    stage = out.parent / f".{out.name}.staging"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    files: list[dict[str, Any]] = []
    recs = []
    shared = Tables()
    for s in sources:
        t = Tables()
        rec = export_run(s, t)
        recs.append(rec)
        shared.rows.setdefault("_profiles", []).extend(t.rows.pop("_profiles", []))
        if rec["ok"]:
            files += write_tables(t, stage, fmt)
        del t
    for empty in list((stage).glob("*/empty.*")):  # a later run filled the table: drop the placeholder
        if len(list(empty.parent.iterdir())) > 1:
            empty.unlink()
            files = [f for f in files if f["file"] != str(empty.relative_to(stage))]
    reconciliation = {"schema_version": SCHEMA_VERSION, "runs": recs, "ok": all(r["ok"] for r in recs)}
    if not reconciliation["ok"]:
        (out.parent / f"{out.name}.reconciliation_FAILED.json").write_text(json.dumps(reconciliation, indent=1))
        shutil.rmtree(stage)
        raise ReconciliationError(json.dumps([r for r in recs if not r["ok"]], indent=1)[:4000])
    static_dims(shared)
    files += write_tables(shared, stage, fmt)
    (stage / "reconciliation.json").write_text(json.dumps(reconciliation, indent=1))
    manifest = {
        "schema_version": SCHEMA_VERSION, "format": fmt,
        "sources": [{"run": s.label, "set_role": s.set_role, "db": s.db_path.name, "report": s.report_path.name} for s in sources],
        "files": files, "reconciliation": {"ok": True, "checks": sum(r["checks"] for r in recs)},
        "notes": "Simulated units (SIM); no real money. CIs/p-values come from frozen reports, not DAX.",
    }
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=1))
    if out.exists():
        shutil.rmtree(out)
    stage.rename(out)
    return manifest
