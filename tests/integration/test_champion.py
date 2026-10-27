import random

import pytest

from poker_lab.evaluation.champion import Criteria, bootstrap_pvalue, decide, holm, record_and_apply
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.db import open_db


def test_holm_reference():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03)
    assert adj["c"] == pytest.approx(0.06)
    assert adj["b"] == pytest.approx(0.06)  # monotone


def test_bootstrap_pvalue_behaviour():
    rng = random.Random(1)
    # type-I error under the null is close to nominal
    rejections = sum(bootstrap_pvalue([rng.gauss(0, 1) for _ in range(60)], resamples=300, seed=t) < 0.05 for t in range(200))
    assert 0.01 <= rejections / 200 <= 0.11
    effect = [rng.gauss(0.5, 1) for _ in range(300)]
    assert bootstrap_pvalue(effect, resamples=1000) < 0.01


def _paired(effect, n, seed):
    rng = random.Random(seed)
    return [rng.gauss(effect, 1.0) for _ in range(n)]


def test_decision_rules():
    crit = Criteria(primary_scenario="base", key_scenarios=["lag"], min_n=400)
    paired = {
        "good": {"base": _paired(0.4, 400, 1), "lag": _paired(0.1, 200, 2)},
        "flat": {"base": _paired(0.0, 400, 3), "lag": _paired(0.0, 200, 4)},
        "regress": {"base": _paired(0.4, 400, 5), "lag": _paired(-0.6, 200, 6)},
        "small": {"base": _paired(0.4, 100, 7)},
        "broken": {"base": _paired(0.4, 400, 8)},
    }
    d = decide(paired, {"broken": 3}, crit, seed=1)
    assert d["good"].decision == "promote"
    assert d["flat"].decision == "inconclusive"
    assert d["regress"].decision == "keep_champion" and "regression" in d["regress"].reason
    assert d["small"].decision == "inconclusive"
    assert d["broken"].decision == "challenger_failed"


def test_record_and_apply_promotes_single_best(tmp_path):
    conn = open_db(tmp_path / "c.db")
    champ = repo.get_or_create_agent_version(conn, "pushfold", "policy", "p7", status="champion")
    a = repo.get_or_create_agent_version(conn, "pushfold", "policy", "a")
    b = repo.get_or_create_agent_version(conn, "pushfold", "policy", "b")
    crit = Criteria(primary_scenario="base", key_scenarios=[], min_n=300)
    dec = decide({"a": {"base": _paired(0.5, 300, 1)}, "b": {"base": _paired(0.3, 300, 2)}}, {}, crit)
    assert dec["a"].decision == dec["b"].decision == "promote"
    promoted = record_and_apply(
        conn, experiment_id=None, champion_version_id=champ, challenger_ids={"a": a, "b": b}, decisions=dec, criteria=crit, suite={}
    )
    assert promoted == a
    st = dict(conn.execute("SELECT version_label, status FROM agent_versions").fetchall())
    assert st == {"p7": "retired", "a": "champion", "b": "candidate"}
    rows = conn.execute("SELECT decision FROM evaluations ORDER BY decision").fetchall()
    assert [r[0] for r in rows] == ["keep_champion", "promote"]


def test_failed_challenger_keeps_champion(tmp_path):
    conn = open_db(tmp_path / "c.db")
    champ = repo.get_or_create_agent_version(conn, "pushfold", "policy", "p7", status="champion")
    x = repo.get_or_create_agent_version(conn, "pushfold", "policy", "x")
    crit = Criteria(primary_scenario="base", key_scenarios=[], min_n=100)
    dec = decide({"x": {"base": _paired(0.0, 200, 1)}}, {}, crit)
    assert record_and_apply(conn, experiment_id=None, champion_version_id=champ, challenger_ids={"x": x}, decisions=dec, criteria=crit, suite={}) is None
    assert repo.champion_of(conn, "pushfold")["version_label"] == "p7"
