"""P8 Power BI export: star schema, reconciliation that blocks on divergence, no hidden info."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from poker_lab.agents.registry import AgentSpec
from poker_lab.analytics.powerbi_export import (
    ReconciliationError,
    RunSource,
    export_powerbi,
    profile_class,
    scenario_class,
)
from poker_lab.evaluation.protocol import Candidate, Protocol, Scenario, run_shard
from poker_lab.evaluation.report import build_report
from poker_lab.persistence.db import open_db


def _protocol() -> Protocol:
    return Protocol(
        name="p8-test",
        seed=4242,
        candidates=[
            Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
            Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": 20})),
        ],
        scenarios=[
            Scenario(label="base", entrants=6, starting_stack=800, hands_per_level=4, n_tournaments=3),
            Scenario(label="lagfield", field_profile="lag", entrants=6, starting_stack=800, hands_per_level=4, n_tournaments=2),
        ],
        progressive_n=[3],
        min_n_claim=200,
    )


@pytest.fixture(scope="module")
def run_source(tmp_path_factory) -> RunSource:
    d = tmp_path_factory.mktemp("p8")
    p = _protocol()
    run_shard(d / "run.db", p, 0, 1, log_every=0)
    rep = build_report(open_db(d / "run.db"), p, "heuristic", "base")
    (d / "report.json").write_text(json.dumps(rep, default=str))
    return RunSource("T1", "final", d / "run.db", d / "report.json")


def _read(out: Path, table: str) -> list[dict]:
    rows: list[dict] = []
    for f in sorted((out / table).glob("*.parquet")):
        rows += pq.read_table(f).to_pylist()
    return rows


def test_export_star_schema_and_reconciliation(run_source, tmp_path):
    out = tmp_path / "pbi"
    man = export_powerbi([run_source], out)
    rec = json.loads((out / "reconciliation.json").read_text())
    assert rec["ok"] and rec["runs"][0]["checks"] > 10 and man["reconciliation"]["ok"]
    for table in ("DimRun", "DimScenario", "DimCandidate", "DimPosition", "DimStackBucket", "DimPhase", "DimFieldClass",
                  "DimOpponentProfile", "FactEntryResult", "FactHandHero", "FactDecision", "FactLedger", "FactAudit",
                  "FactScenarioSummary", "FactPairedComparison", "FactBreakdownCI", "FactAllinLuck", "FactProgressive"):
        assert (out / table).is_dir(), table
    # every file in the manifest exists with the recorded hash
    import hashlib

    for f in man["files"]:
        assert hashlib.sha256((out / f["file"]).read_bytes()).hexdigest() == f["sha256"]
    entries = _read(out, "FactEntryResult")
    hero = [r for r in entries if r["Role"] == "hero"]
    assert len(hero) == len(_protocol().jobs())
    summ = {(r["ScenarioKey"], r["CandidateKey"]): r for r in _read(out, "FactScenarioSummary")}
    for key, s in summ.items():
        rows = [r for r in hero if (r["ScenarioKey"], r["CandidateKey"]) == key]
        assert len(rows) == s["NTournaments"]
        assert sum(r["NetProfit"] for r in rows) / sum(r["Cost"] for r in rows) == pytest.approx(s["Roi"], abs=1e-6)
    paired = _read(out, "FactPairedComparison")
    assert {r["CandidateKey"] for r in paired} == {"T1|equity"} and all(r["BaselineCandidate"] == "heuristic" for r in paired)
    scen = {r["Scenario"]: r for r in _read(out, "DimScenario")}
    assert scen["lagfield"]["FieldClass"] == "aggressive_static" and scen["lagfield"]["ShareAggressive"] == 1.0
    assert scen["base"]["IsPrimary"] is True


def test_decisions_export_contains_no_hidden_information(run_source, tmp_path):
    out = tmp_path / "pbi"
    export_powerbi([run_source], out)
    cols = set(pq.read_schema(next((out / "FactDecision").glob("*.parquet"))).names)
    for forbidden in ("own_hole_cards_json", "HoleCards", "observation_json", "Observation", "OpponentCards", "Board"):
        assert forbidden not in cols
    hands = set(pq.read_schema(next((out / "FactHandHero").glob("*.parquet"))).names)
    assert not any("card" in c.lower() for c in hands)


def test_divergent_report_blocks_export_and_publishes_nothing(run_source, tmp_path):
    bad = json.loads(run_source.report_path.read_text())
    first = next(iter(bad["scenarios"]["base"].values()))
    first["total_net"] += 110  # one buy-in of drift
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad))
    out = tmp_path / "pbi"
    with pytest.raises(ReconciliationError):
        export_powerbi([RunSource("T1", "final", run_source.db_path, bad_path)], out)
    assert not out.exists()
    assert (tmp_path / "pbi.reconciliation_FAILED.json").exists()


def test_report_from_other_run_is_rejected(run_source, tmp_path):
    other = json.loads(run_source.report_path.read_text())
    other["evaluation_run_id"] = "not-this-run"
    p = tmp_path / "other.json"
    p.write_text(json.dumps(other))
    with pytest.raises(ReconciliationError):
        export_powerbi([RunSource("T1", "final", run_source.db_path, p)], tmp_path / "pbi")


def test_source_database_is_not_modified(run_source, tmp_path):
    before = run_source.db_path.stat().st_mtime_ns, run_source.db_path.read_bytes()[:4096]
    export_powerbi([run_source], tmp_path / "pbi")
    assert (run_source.db_path.stat().st_mtime_ns, run_source.db_path.read_bytes()[:4096]) == before


def test_csv_format(run_source, tmp_path):
    out = tmp_path / "csv"
    man = export_powerbi([run_source], out, fmt="csv")
    assert man["format"] == "csv" and list((out / "FactEntryResult").glob("*.csv"))
    assert (out / "FactAudit").is_dir()  # empty table keeps a header for Power BI


def test_field_classes():
    assert profile_class("tag", "heuristic") == "exploitable_static"
    assert profile_class("bluffer60", "heuristic") == "aggressive_static"
    assert profile_class("adaptive_lag", "heuristic") == "adaptive"
    assert profile_class("hybrid-v1", "policy") == "self_play"
    assert scenario_class({"adaptive": 0.8, "exploitable_static": 0.2}) == "adaptive"
    assert scenario_class({"adaptive": 0.5, "exploitable_static": 0.5}) == "mixed"
