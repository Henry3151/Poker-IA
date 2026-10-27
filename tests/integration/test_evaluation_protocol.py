import pytest

from poker_lab.agents.registry import AgentSpec
from poker_lab.analytics.decision_metrics import compute_for_tournament, pot_type, stack_bucket
from poker_lab.evaluation.protocol import Candidate, Protocol, Scenario, merge_shards, run_shard
from poker_lab.evaluation.report import build_report, cluster_ratio_ci
from poker_lab.persistence.db import open_db


def small_protocol():
    return Protocol(
        name="test",
        seed=99,
        candidates=[
            Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
            Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": 30})),
        ],
        scenarios=[
            Scenario(label="base", entrants=6, starting_stack=800, hands_per_level=4, n_tournaments=4),
            Scenario(label="reentry", entrants=6, starting_stack=600, hands_per_level=4, reentry_levels=2, max_entries=2, n_tournaments=2),
        ],
        progressive_n=[2, 4],
        min_n_claim=200,
    )


@pytest.fixture(scope="module")
def merged(tmp_path_factory):
    d = tmp_path_factory.mktemp("eval")
    p = small_protocol()
    for i in range(2):
        run_shard(d / f"s{i}.db", p, i, 2, log_every=0)
    merge_shards(d / "main.db", [d / "s0.db", d / "s1.db"])
    run_shard(d / "single.db", p, 0, 1, log_every=0)
    return d, p


def _results(db):
    conn = open_db(db)
    rows = conn.execute(
        "SELECT t.scenario_label, t.seed, f.net_profit, f.final_place FROM v_entry_financials f JOIN tournaments t"
        " ON t.tournament_id=f.tournament_id WHERE f.role='hero' ORDER BY t.scenario_label, t.seed"
    ).fetchall()
    return [tuple(r) for r in rows]


def test_shards_merge_equals_single_process(merged):
    d, p = merged
    a = _results(d / "main.db")
    b = _results(d / "single.db")
    assert a == b and len(a) == len(p.jobs())


def test_common_random_numbers_and_resume(merged):
    d, p = merged
    conn = open_db(d / "main.db")
    seeds = conn.execute(
        "SELECT scenario_label, seed FROM tournaments WHERE scenario_label LIKE '%|base|%' ORDER BY seed"
    ).fetchall()
    by_cand: dict[str, list[int]] = {}
    for lbl, seed in seeds:
        by_cand.setdefault(lbl.split("|")[2], []).append(seed)
    assert by_cand["heuristic"] == by_cand["equity"]  # identical tournament seeds per candidate
    # resuming a finished shard runs nothing new
    assert run_shard(d / "single.db", p, 0, 1, log_every=0)["ran"] == 0


def test_report_structure_and_conservative_verdicts(merged):
    d, p = merged
    conn = open_db(d / "main.db")
    for (tid,) in conn.execute("SELECT tournament_id FROM tournaments WHERE scenario_label LIKE '%|base|%'").fetchall():
        compute_for_tournament(conn, tid, samples=30)
    rep = build_report(conn, p, "heuristic", "base")
    s = rep["scenarios"]["base"]["equity"]
    assert s["n_tournaments"] == 4
    assert s["roi_verdict"] == "insufficient_sample"  # never a claim with n < min_n_claim
    assert rep["paired_vs_baseline"]["base"]["equity"]["verdict"] == "insufficient_sample"
    assert [x["n"] for x in rep["progressive"]["equity"]] == [2, 4]
    assert rep["scenarios"]["reentry"]["heuristic"]["entries_total"] >= 2
    for cand in ("heuristic", "equity"):
        for bucket in rep["breakdowns"][cand]["phase"].values():
            assert bucket["flag"] == "insufficient_sample" or bucket["hands"] >= 100
    assert rep["decision_quality"]["equity"]["decisions"] > 0
    basis = rep["decision_quality"]["heuristic"]["equity_basis_counts"]
    assert set(basis) <= {"vs_uniform_random_hands_mc30", "agent_estimate"}


def test_decision_metric_helpers():
    assert stack_bucket(5) == "<10bb" and stack_bucket(25) == "20-40bb" and stack_bucket(80) == "40bb+"
    obs = {"street": "preflop", "seats": [{"folded": False}] * 3, "history": [{"street": "preflop", "kind": "raise"}, {"street": "preflop", "kind": "raise"}]}
    assert pot_type(obs) == "three_bet_plus"
    obs["history"] = [{"street": "preflop", "kind": "call"}]
    assert pot_type(obs) == "limped"


def test_cluster_bootstrap_ratio():
    ci = cluster_ratio_ci([(10.0, 10.0)] * 50, seed=1)
    assert ci.estimate == 1.0 and ci.low == 1.0 and ci.high == 1.0
