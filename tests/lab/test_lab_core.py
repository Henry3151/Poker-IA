"""P9-B core: frozen manifest, read-only access, generic integrity, settings without secrets, jobs."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from poker_lab.lab import config as cfg
from poker_lab.lab.frozen import MANIFEST, build_manifest, verify_manifest
from poker_lab.lab.integrity import verify_run
from poker_lab.lab.jobs import JobBusy, JobManager
from poker_lab.lab.readonly import connect_ro
from poker_lab.lab.registry import get_run, load_report, project_root, run_overview
from poker_lab.lab.summary import compare_table, relevance, run_summary

DB = "artifacts/p7c/final.db"


def _snapshot(path: Path) -> tuple[int, bytes]:
    return path.stat().st_mtime_ns, path.read_bytes()


def test_frozen_manifest_detects_changes_and_missing(lab_root):
    assert verify_manifest(lab_root).passed
    (lab_root / "artifacts/checkpoints/model.json").write_text('{"w": 2}')
    rep = verify_manifest(lab_root)
    assert not rep.passed and rep.changed == ["artifacts/checkpoints/model.json"]
    (lab_root / "artifacts/checkpoints/model.json").unlink()
    assert verify_manifest(lab_root).missing == ["artifacts/checkpoints/model.json"]


def test_repository_frozen_manifest_is_intact():
    """The real FROZEN.sha256 must match the repository: frozen results/core were not modified."""
    root = project_root()
    rep = verify_manifest(root)
    assert rep.passed, rep.as_dict()
    assert rep.checked >= 70 and (root / MANIFEST).read_text() == build_manifest(root)


def test_readonly_connection_cannot_write(lab_root):
    conn = connect_ro(lab_root / DB)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM tournaments")
    conn.close()


def test_queries_and_verification_leave_database_bytes_untouched(lab_root):
    db = lab_root / DB
    before = _snapshot(db)
    run = get_run("P7c")
    run_overview(run, lab_root)
    res = verify_run(db, load_report(run, lab_root), quick_check=True)
    assert res["ok"], res
    assert _snapshot(db) == before
    assert not (lab_root / "artifacts/p7c/final.db-wal").exists() or (lab_root / "artifacts/p7c/final.db-wal").stat().st_size == 0


def test_integrity_detects_tampering(lab_root):
    db = lab_root / DB
    conn = sqlite3.connect(db)
    tid = conn.execute("SELECT tournament_id FROM tournaments LIMIT 1").fetchone()[0]
    conn.execute("DELETE FROM financial_ledger WHERE tournament_id=? AND kind='payout'", (tid,))
    conn.commit()
    conn.close()
    res = verify_run(db, load_report(get_run("P7c"), lab_root))
    assert not res["ok"] and not res["checks"]["ledger_reconciliation"]["ok"]


def test_integrity_detects_missing_tournament(lab_root):
    db = lab_root / DB
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("UPDATE tournaments SET status='running' WHERE rowid=(SELECT MIN(rowid) FROM tournaments)")
    conn.commit()
    conn.close()
    res = verify_run(db, load_report(get_run("P7c"), lab_root))
    assert not res["checks"]["all_completed"]["ok"]


def test_settings_defaults_roundtrip_and_validation(lab_root):
    s = cfg.load_settings(lab_root)
    assert s.simulation.concurrent_jobs == 1 and s.online.max_hands == 30
    d = s.model_dump()
    d["simulation"]["max_tournaments_per_job"] = 50
    cfg.save_settings(lab_root, d)
    assert cfg.load_settings(lab_root).simulation.max_tournaments_per_job == 50
    bad = json.loads(json.dumps(d))
    bad["simulation"]["max_tournaments_per_job"] = 0
    with pytest.raises(ValueError):
        cfg.save_settings(lab_root, bad)
    extra = json.loads(json.dumps(d))
    extra["simulation"]["unknown"] = 1
    with pytest.raises(ValueError):
        cfg.save_settings(lab_root, extra)


@pytest.mark.parametrize("field", ["api_key", "OPEN_POKER_API_KEY", "token", "senha", "bearerAuth"])
def test_settings_never_store_secrets(lab_root, field):
    d = cfg.LabSettings().model_dump()
    d["online"][field] = "opk_live_SECRET"
    with pytest.raises(ValueError):
        cfg.save_settings(lab_root, d)
    p = cfg.settings_path(lab_root)
    assert not p.exists() or "SECRET" not in p.read_text()


def test_relevance_rules():
    assert relevance(0.2, 0.5) == "melhora relevante"
    assert relevance(-0.5, -0.2) == "piora relevante"
    assert relevance(-0.05, 0.05) == "equivalência prática"
    assert relevance(0.01, 0.3) == "melhora (relevância incerta)"
    assert relevance(-0.466, -0.022) == "piora (relevância incerta)"
    assert relevance(-0.3, 0.2) == "inconclusivo"


def test_summary_reproduces_frozen_p7c_numbers():
    """Read from the versioned frozen report: the CLI/UI must show exactly the published values."""
    rep = load_report(get_run("P7c"), project_root())
    s = run_summary(rep)
    assert s["baseline"] == "hybrid_v1" and s["primary_scenario"] == "robust_mix"
    assert (round(s["baseline_roi"], 6), round(s["baseline_roi_low"], 6), round(s["baseline_roi_high"], 6)) == (0.764545, 0.532727, 1.004545)
    v2 = next(r for r in compare_table(rep, "robust_mix") if r["candidate"] == "hybrid_v2_adaptive")
    assert round(v2["diff"], 6) == -0.248182 and round(v2["p_holm"], 5) == 0.23394
    assert v2["relevance"] == "piora (relevância incerta)" and v2["decision"] == "keep_champion"


def test_job_manager_runs_one_job_at_a_time():
    jm = JobManager()
    gate = threading.Event()
    job = jm.submit("slow", {}, lambda say: (say("start"), gate.wait(5), "ok")[2])
    with pytest.raises(JobBusy):
        jm.submit("other", {}, lambda say: None)
    gate.set()
    for _ in range(200):
        if jm.get(job.id).status == "done":
            break
        threading.Event().wait(0.01)
    assert jm.get(job.id).result == "ok"
    jm.submit("next", {}, lambda say: 1)  # free again
