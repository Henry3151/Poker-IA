"""Summaries of frozen evaluations, read from the versioned reports (never recomputed)."""

from __future__ import annotations

from typing import Any

DELTA = 0.10  # pre-registered practical relevance (buy-ins per tournament)


def relevance(lo: float, hi: float, delta: float = DELTA) -> str:
    if lo > delta:
        return "melhora relevante"
    if hi < -delta:
        return "piora relevante"
    if lo > -delta and hi < delta:
        return "equivalência prática"
    if lo > 0:
        return "melhora (relevância incerta)"
    if hi < 0:
        return "piora (relevância incerta)"
    return "inconclusivo"


def baseline_candidate(report: dict[str, Any]) -> str:
    cands = [c["label"] for c in report["protocol"]["candidates"]]
    first = next(iter(report["paired_vs_baseline"].values()))
    missing = [c for c in cands if c not in first]
    return str(missing[0]) if len(missing) == 1 else str(cands[0])


def primary_scenario(report: dict[str, Any]) -> str:
    cc = report.get("champion_challenger")
    return str(cc["criteria"]["primary_scenario"]) if cc else str(report["protocol"]["scenarios"][0]["label"])


def scenario_table(report: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    rows = []
    for cand, v in report["scenarios"][scenario].items():
        r = v["roi"]
        rows.append({"candidate": cand, "n": v["n_tournaments"], "roi": r["estimate"], "roi_low": r["ci_low"],
                     "roi_high": r["ci_high"], "verdict": v["roi_verdict"], "itm": v["itm_rate"]["estimate"],
                     "wins": v["wins"]})
    return sorted(rows, key=lambda x: -x["roi"])


def compare_table(report: dict[str, Any], scenario: str) -> list[dict[str, Any]]:
    """Paired differences vs the run's baseline; frozen decision-test values when they exist."""
    decisions = (report.get("champion_challenger") or {}).get("decisions", {})
    rows = []
    for cand, v in report["paired_vs_baseline"][scenario].items():
        t = decisions.get(cand, {}).get("tests", {}).get(scenario)
        est, lo, hi = (t["estimate"], t["ci_low"], t["ci_high"]) if t else (v["estimate"], v["ci_low"], v["ci_high"])
        rows.append({"candidate": cand, "diff": est, "low": lo, "high": hi, "n": v["n"],
                     "p_holm": t.get("p_holm") if t else None, "decision_test": bool(t),
                     "relevance": relevance(lo, hi), "decision": decisions.get(cand, {}).get("decision")})
    return rows


def run_summary(report: dict[str, Any]) -> dict[str, Any]:
    primary = primary_scenario(report)
    base = baseline_candidate(report)
    cc = report.get("champion_challenger") or {}
    head = report["scenarios"][primary][base]["roi"]
    return {
        "evaluation_run_id": report["evaluation_run_id"],
        "seed": report["protocol"]["seed"],
        "primary_scenario": primary,
        "baseline": base,
        "baseline_roi": head["estimate"], "baseline_roi_low": head["ci_low"], "baseline_roi_high": head["ci_high"],
        "scenarios": [s["label"] for s in report["protocol"]["scenarios"]],
        "decisions": {k: {"decision": v["decision"], "reason": v["reason"]} for k, v in cc.get("decisions", {}).items()},
        "criteria": cc.get("criteria"),
        "table": scenario_table(report, primary),
        "compare": compare_table(report, primary),
    }
