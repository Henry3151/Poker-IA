"""Fixture: a miniature project root with one evaluation run laid out like P7c
(artifacts/p7c/final.db + docs/p7c_artifacts/p7c_final_report.json) and a FROZEN manifest."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from poker_lab.agents.registry import AgentSpec
from poker_lab.evaluation.protocol import Candidate, Protocol, Scenario, run_shard
from poker_lab.evaluation.report import build_report
from poker_lab.lab.frozen import build_manifest
from poker_lab.persistence.db import open_db


def _protocol() -> Protocol:
    return Protocol(
        name="p9-test", seed=31337,
        candidates=[Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
                    Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": 20}))],
        scenarios=[Scenario(label="base", entrants=6, starting_stack=800, hands_per_level=4, n_tournaments=3),
                   Scenario(label="lagfield", field_profile="lag", entrants=6, starting_stack=800, hands_per_level=4, n_tournaments=2)],
        progressive_n=[3], min_n_claim=200,
    )


@pytest.fixture(scope="session")
def lab_template(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("labroot")
    db = root / "artifacts/p7c/final.db"
    db.parent.mkdir(parents=True)
    p = _protocol()
    run_shard(db, p, 0, 1, log_every=0)
    conn = open_db(db)
    rep = build_report(conn, p, "heuristic", "base")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    (root / "docs/p7c_artifacts").mkdir(parents=True)
    (root / "docs/p7c_artifacts/p7c_final_report.json").write_text(json.dumps(rep, default=str))
    (root / "artifacts/checkpoints").mkdir(parents=True)
    (root / "artifacts/checkpoints/model.json").write_text('{"w": 1}')
    (root / "FROZEN.sha256").write_text(build_manifest(root))
    return root


@pytest.fixture()
def lab_root(lab_template, tmp_path) -> Path:
    dst = tmp_path / "root"
    shutil.copytree(lab_template, dst)
    return dst
