"""Migration 0002: fresh DB, copy of an existing v1 DB, backup verification, failure recovery."""

import shutil

import pytest

from poker_lab.agents.registry import AgentSpec
from poker_lab.application.tournament_service import EntrantSpec, run_tournament
from poker_lab.persistence import db as dbmod
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.migration_safety import (
    MigrationFailed,
    make_verified_backup,
    restore_backup,
    safe_migrate,
    table_counts,
)
from poker_lab.tournament.config import TournamentConfig


def _v1_database(path):
    """Build a realistic schema-v1 database the way P5 produced it (raw SQL inserts)."""
    conn = dbmod.connect(path)
    dbmod.migrate(conn, target=1)
    assert dbmod.schema_version(conn) == 1
    ts = dbmod.now_iso()
    conn.execute(
        "INSERT INTO experiments(experiment_id,name,algorithm,code_version,config_json,seed,status,created_at)"
        " VALUES ('exp1','legacy','baselines','0.1.0','{}',1,'completed',?)",
        (ts,),
    )
    for i, algo in enumerate(["random", "heuristic"]):
        conn.execute(
            "INSERT INTO agent_versions(agent_version_id,name,algorithm,version_label,status,created_at) VALUES (?,?,?,?,?,?)",
            (f"av{i}", algo, algo, "v1", "baseline", ts),
        )
    conn.execute(
        "INSERT INTO tournaments(tournament_id,experiment_id,name,config_json,seed,entrant_count,table_size,starting_stack,buy_in,"
        "prize_pool,status,hands_played,started_at,completed_at) VALUES ('t1','exp1','legacy','{}',1,2,6,1000,100,200,'completed',1,?,?)",
        (ts, ts),
    )
    for i in range(2):
        conn.execute(
            "INSERT INTO tournament_entries(entry_id,tournament_id,agent_version_id,participant_label,final_place,final_stack,"
            "simulated_payout) VALUES (?,?,?,?,?,?,?)",
            (f"e{i}", "t1", f"av{i}", f"p{i}", i + 1, 2000 if i == 0 else 0, 200 if i == 0 else 0),
        )
    conn.execute(
        "INSERT INTO notes(note_id,title,created_at,updated_at,tournament_id) VALUES ('n1','legacy note',?,?, 't1')", (ts, ts)
    )
    conn.close()


def test_fresh_database_gets_all_migrations(tmp_path):
    out = safe_migrate(tmp_path / "new.db")
    assert out["fresh"] and out["applied"] == ["0001_initial.sql", "0002_financials_evaluation.sql"]
    c = dbmod.connect(tmp_path / "new.db")
    assert dbmod.schema_version(c) == 2
    assert {"financial_ledger", "decision_metrics", "evaluation_runs", "entry_reentries"} <= set(table_counts(c))


def test_existing_v1_copy_migrates_additively_with_verified_backup(tmp_path):
    live = tmp_path / "live.db"
    _v1_database(live)
    copy = tmp_path / "copy.db"
    shutil.copyfile(live, copy)
    c0 = dbmod.connect(copy)
    before = table_counts(c0)
    c0.close()
    out = safe_migrate(copy, tmp_path / "backups")
    assert out["applied"] == ["0002_financials_evaluation.sql"] and out["backup"]
    c = dbmod.connect(copy)
    after = table_counts(c)
    for t, n in before.items():
        if t != "schema_migrations":
            assert after[t] == n, t  # nothing lost or rewritten
    # backfill: one buy-in per entry and one payout for the winner; legacy data reconciles
    assert c.execute("SELECT COUNT(*) FROM financial_ledger WHERE kind='buy_in'").fetchone()[0] == 2
    assert repo.reconcile_tournament_ledger(c, "t1") == []
    fin = {r["participant_label"]: dict(r) for r in c.execute("SELECT * FROM v_entry_financials")}
    assert fin["p0"]["net_profit"] == 100 and fin["p1"]["net_profit"] == -100
    assert c.execute("SELECT entries_count, role FROM tournament_entries WHERE entry_id='e0'").fetchone()[:] == (1, "field")
    assert c.execute("SELECT title FROM notes").fetchone()[0] == "legacy note"
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    c.close()
    # the original live DB is untouched
    lc = dbmod.connect(live)
    assert dbmod.schema_version(lc) == 1


def test_backup_manifest_and_restore(tmp_path):
    live = tmp_path / "live.db"
    _v1_database(live)
    c = dbmod.connect(live)
    bpath, manifest = make_verified_backup(c, live, tmp_path / "b")
    c.execute("DELETE FROM notes")
    c.close()
    restore_backup(bpath, live)
    c2 = dbmod.connect(live)
    assert c2.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1
    # tampered backup is refused
    with open(bpath, "ab") as f:
        f.write(b"x")
    with pytest.raises(RuntimeError, match="checksum"):
        restore_backup(bpath, live)


def test_failed_migration_restores_backup(tmp_path, monkeypatch):
    live = tmp_path / "live.db"
    _v1_database(live)
    real = dbmod._migration_files

    def broken():
        files = real()
        return [*files, (3, "0003_broken.sql", "CREATE TABLE ok_table(x INTEGER); INSERT INTO nope VALUES (1);")]

    monkeypatch.setattr(dbmod, "_migration_files", broken)
    with pytest.raises(MigrationFailed) as ei:
        safe_migrate(live, tmp_path / "b")
    assert ei.value.restored
    c = dbmod.connect(live)
    assert dbmod.schema_version(c) == 1  # restored to the pre-migration state
    assert "ok_table" not in table_counts(c)
    assert c.execute("SELECT COUNT(*) FROM tournament_entries").fetchone()[0] == 2


def test_new_tournaments_write_reconciled_ledger(tmp_path):
    conn = dbmod.open_db(tmp_path / "l.db")
    cfg = TournamentConfig(starting_stack=600, hands_per_level=4, buy_in=100, fee=10, reentry_levels=3, max_entries=3)
    ents = [EntrantSpec(f"r{i}", AgentSpec(algorithm="random")) for i in range(6)]
    tid, res = run_tournament(conn, cfg, ents, seed=11, hero_labels=frozenset({"r0"}))
    assert repo.reconcile_tournament_ledger(conn, tid) == []
    total_entries = conn.execute("SELECT total_entries FROM tournaments WHERE tournament_id=?", (tid,)).fetchone()[0]
    assert total_entries == res.total_entries > 6  # random agents bust early -> re-entries happened
    assert conn.execute("SELECT COUNT(*) FROM entry_reentries WHERE tournament_id=?", (tid,)).fetchone()[0] == total_entries - 6
    led = conn.execute(
        "SELECT SUM(CASE WHEN kind='buy_in' THEN -amount END), SUM(CASE WHEN kind='fee' THEN -amount END),"
        " SUM(CASE WHEN kind='payout' THEN amount END) FROM financial_ledger WHERE tournament_id=?",
        (tid,),
    ).fetchone()
    assert led[0] == 100 * total_entries and led[1] == 10 * total_entries and led[2] == res.prize_pool == 100 * total_entries
    # net across all players = -fees (fees leave the prize pool)
    assert conn.execute("SELECT SUM(net_profit) FROM v_entry_financials WHERE tournament_id=?", (tid,)).fetchone()[0] == -10 * total_entries
    assert conn.execute("SELECT role FROM tournament_entries WHERE participant_label='r0'").fetchone()[0] == "hero"
    # duplicate protection: writing the ledger again fails atomically, nothing is double counted
    rows = [dict(r) for r in conn.execute("SELECT entry_id, agent_version_id, entries_count, simulated_payout AS payout FROM tournament_entries WHERE tournament_id=?", (tid,))]
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError), dbmod.transaction(conn):
        repo.record_tournament_ledger(conn, tid, rows, 100, 10)
    assert repo.reconcile_tournament_ledger(conn, tid) == []
