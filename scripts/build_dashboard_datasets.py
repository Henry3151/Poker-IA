"""Build the web-dashboard datasets (small JSON row files) from the reconciled Power BI export.

    python scripts/build_dashboard_datasets.py [artifacts/powerbi/latest] [artifacts/powerbi/dashboard]

Every number comes from the export (which already reconciled SQL x files x frozen reports).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "artifacts/powerbi/latest"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "artifacts/powerbi/dashboard"
DELTA = 0.10
CAND_LABEL = {
    "hybrid_v1": "hybrid-v1", "hybrid_v2_adaptive": "v2 adaptativo", "hybrid_v1_bluffcatch": "v1 + bluff-catch",
    "pushfold_p7": "push/fold P7", "pushfold_v2_ante": "push/fold v2", "lag": "LAG (ref.)", "random": "aleatório",
    "heuristic": "heurístico", "equity": "equity MC", "equity_icm_adaptive": "equity ICM adapt.", "pushfold_policy": "push/fold (MCCFR)",
}


def read(table: str) -> list[dict]:
    rows: list[dict] = []
    for f in sorted((SRC / table).glob("*.parquet")):
        rows += pq.read_table(f).to_pylist()
    return rows


def r(x: float | None, n: int = 4) -> float | None:
    return None if x is None else round(float(x), n)


def relevance(lo: float, hi: float) -> str:
    if lo > DELTA:
        return "melhora relevante"
    if hi < -DELTA:
        return "piora relevante"
    if lo > -DELTA and hi < DELTA:
        return "equivalência prática"
    if lo > 0:
        return "melhora (relevância incerta)"
    if hi < 0:
        return "piora (relevância incerta)"
    return "inconclusivo"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scen = {s["ScenarioKey"]: s for s in read("DimScenario")}
    cand = {c["CandidateKey"]: c for c in read("DimCandidate")}
    runs = read("DimRun")
    out: dict[str, list[dict]] = {}

    out["scenario_roi"] = [
        {
            "run": s["RunKey"], "scenario": scen[s["ScenarioKey"]]["Scenario"],
            "field_class": scen[s["ScenarioKey"]]["FieldClassLabel"],
            "primary": bool(scen[s["ScenarioKey"]]["IsPrimary"]),
            "candidate": cand[s["CandidateKey"]]["Candidate"],
            "candidate_label": CAND_LABEL.get(cand[s["CandidateKey"]]["Candidate"], cand[s["CandidateKey"]]["Candidate"]),
            "role": cand[s["CandidateKey"]]["RoleInRun"],
            "n": s["NTournaments"], "roi": r(s["Roi"]), "roi_low": r(s["RoiCiLow"]), "roi_high": r(s["RoiCiHigh"]),
            "verdict": s["RoiVerdict"], "itm": r(s["Itm"]), "wins": s["Wins"], "max_drawdown": s["MaxDrawdown"],
        }
        for s in read("FactScenarioSummary")
    ]
    paired = []
    for p in read("FactPairedComparison"):
        dec = bool(p["IsDecisionTest"])
        est = p["DecisionTestEstimate"] if dec else p["Diff"]
        lo = p["DecisionTestCiLow"] if dec else p["DiffCiLow"]
        hi = p["DecisionTestCiHigh"] if dec else p["DiffCiHigh"]
        c = cand[p["CandidateKey"]]
        paired.append({
            "run": p["RunKey"], "scenario": scen[p["ScenarioKey"]]["Scenario"],
            "field_class": scen[p["ScenarioKey"]]["FieldClassLabel"],
            "candidate": c["Candidate"], "candidate_label": CAND_LABEL.get(c["Candidate"], c["Candidate"]),
            "baseline": p["BaselineCandidate"], "baseline_label": CAND_LABEL.get(p["BaselineCandidate"], p["BaselineCandidate"]),
            "decision_test": dec, "diff": r(est), "low": r(lo), "high": r(hi), "n": p["DiffN"],
            "p_holm": r(p["PHolm"]), "relevance": relevance(lo, hi), "decision": c["PromotionDecision"],
        })
    out["paired"] = paired
    out["breakdown"] = [
        {"run": b["RunKey"], "candidate": cand[b["CandidateKey"]]["Candidate"],
         "candidate_label": CAND_LABEL.get(cand[b["CandidateKey"]]["Candidate"], cand[b["CandidateKey"]]["Candidate"]),
         "dimension": b["Dimension"], "group": b["Group"], "hands": b["Hands"],
         "bb100": r(b["BBPerHand"] * 100, 2), "bb100_low": r(b["BBPerHandCiLow"] * 100, 2),
         "bb100_high": r(b["BBPerHandCiHigh"] * 100, 2), "flag": b["Flag"]}
        for b in read("FactBreakdownCI")
    ]
    out["steal"] = [
        {"run": s["RunKey"], "scenario": scen[s["ScenarioKey"]]["Scenario"], "candidate": cand[s["CandidateKey"]]["Candidate"],
         "candidate_label": CAND_LABEL.get(cand[s["CandidateKey"]]["Candidate"], cand[s["CandidateKey"]]["Candidate"]),
         "row_id": f"{scen[s['ScenarioKey']]['Scenario']}|{cand[s['CandidateKey']]['Candidate']}",
         "opportunities": s["Opportunities"], "steal_rate": r(s["StealRate"]), "won_immediately": r(s["WonImmediately"]),
         "net_per_steal": r(s["NetPerSteal"], 3), "net_low": r(s["NetPerStealCiLow"], 3), "net_high": r(s["NetPerStealCiHigh"], 3),
         "vs_resteal_call": r(s["VsRestealCall"]), "vs_resteal_fold": r(s["VsRestealFold"]),
         "rate_first_half": r(s["StealRateFirstHalf"]), "rate_second_half": r(s["StealRateSecondHalf"])}
        for s in read("FactSteal")
    ]
    rec = json.loads((SRC / "reconciliation.json").read_text())
    rec_by = {x["run"]: x for x in rec["runs"]}
    champion = {}
    for c in cand.values():
        if c["RoleInRun"] == "baseline_champion":
            champion[c["RunKey"]] = c["Candidate"]
    out["runs"] = [
        {"run": x["RunKey"], "seed": x["SeedRoot"], "primary_scenario": x["PrimaryScenario"],
         "baseline": CAND_LABEL.get(x["BaselineCandidate"], x["BaselineCandidate"]),
         "tournaments": sum(1 for _ in []) or None, "checks": rec_by[x["RunKey"]]["checks"],
         "problems": len(rec_by[x["RunKey"]]["problems"]), "reconciled": "sim" if rec_by[x["RunKey"]]["ok"] else "não"}
        for x in sorted(runs, key=lambda x: x["RunKey"])
    ]
    tcount: dict[str, int] = {}
    for s in out["scenario_roi"]:
        tcount[s["run"]] = tcount.get(s["run"], 0) + s["n"]
    for x in out["runs"]:
        x["tournaments"] = tcount.get(x["run"], 0)
    out["candidates"] = [
        {"run": c["RunKey"], "candidate": c["Candidate"], "candidate_label": CAND_LABEL.get(c["Candidate"], c["Candidate"]),
         "row_id": f"{c['RunKey']}|{c['Candidate']}", "role": c["RoleInRun"], "version": c["VersionLabel"],
         "algorithm": c["Algorithm"], "bluff_rate": c["BluffRate"], "decision": c["PromotionDecision"] or "—"}
        for c in sorted(cand.values(), key=lambda c: (c["RunKey"], c["Candidate"]))
    ]
    for name, rows in out.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        print(name, len(rows), (OUT / f"{name}.json").stat().st_size)


if __name__ == "__main__":
    main()
