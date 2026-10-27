import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from poker_lab.agents.registry import AgentSpec
from poker_lab.application.tournament_service import EntrantSpec, run_tournament
from poker_lab.notes.service import (
    NoteIn,
    NoteLinkError,
    create_note,
    delete_note,
    get_note,
    list_notes,
    update_note,
)
from poker_lab.persistence import db as dbmod
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.retention import prune
from poker_lab.tournament.config import TournamentConfig


@pytest.fixture
def conn(tmp_path):
    c = dbmod.open_db(tmp_path / "lab.db")
    yield c
    c.close()


def entrants(n):
    algos = ["random", "heuristic", "equity"]
    return [
        EntrantSpec(f"{algos[i % 3]}-{i}", AgentSpec(algorithm=algos[i % 3], params={"samples": 40} if algos[i % 3] == "equity" else {}))
        for i in range(n)
    ]


@pytest.fixture
def tournament(conn):
    exp = repo.create_experiment(conn, "test", "baselines", {"k": 1}, 7)
    cfg = TournamentConfig(starting_stack=1500, hands_per_level=6)
    tid, res = run_tournament(conn, cfg, entrants(8), seed=7, experiment_id=exp)
    return tid, res, exp


def test_migrations_idempotent_and_checksummed(tmp_path):
    c = dbmod.connect(tmp_path / "m.db")
    assert dbmod.migrate(c) == ["0001_initial.sql", "0002_financials_evaluation.sql"]
    assert dbmod.migrate(c) == []
    assert dbmod.schema_version(c) == 2
    c.execute("UPDATE schema_migrations SET checksum='tampered'")
    with pytest.raises(dbmod.MigrationError):
        dbmod.migrate(c)


def test_foreign_keys_and_checks_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tournament_entries(entry_id,tournament_id,agent_version_id,participant_label) VALUES ('e','missing','x','l')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO experiments(experiment_id,name,algorithm,code_version,config_json,status,created_at)"
            " VALUES ('e','n','a','v','{}','bogus','t')"
        )


def test_single_champion_per_lineage(conn):
    a = repo.get_or_create_agent_version(conn, "pf", "policy", "v1", status="champion")
    b = repo.get_or_create_agent_version(conn, "pf", "policy", "v2")
    with pytest.raises(sqlite3.IntegrityError):
        repo.set_agent_status(conn, b, "champion")
    assert repo.champion_of(conn, "pf")["agent_version_id"] == a


def test_tournament_persisted_consistently(conn, tournament):
    tid, res, exp = tournament
    t = conn.execute("SELECT * FROM tournaments WHERE tournament_id=?", (tid,)).fetchone()
    assert t["status"] == "completed" and t["hands_played"] == res.hands_played
    assert conn.execute("SELECT COUNT(*) FROM hands WHERE tournament_id=?", (tid,)).fetchone()[0] == res.hands_played
    places = [r[0] for r in conn.execute("SELECT final_place FROM tournament_entries WHERE tournament_id=? ORDER BY final_place", (tid,))]
    assert places == list(range(1, 9))
    # chip conservation per hand in the database
    bad = conn.execute(
        "SELECT hand_id FROM hand_players GROUP BY hand_id HAVING SUM(starting_stack) != SUM(ending_stack)"
    ).fetchall()
    assert bad == []
    assert conn.execute("SELECT COUNT(*) FROM hands WHERE chips_conserved=0").fetchone()[0] == 0
    # every decision references an existing agent version and hand; zero invalid actions with baselines
    assert conn.execute("SELECT COUNT(*) FROM decisions WHERE action_valid=0").fetchone()[0] == 0
    assert conn.execute("SELECT SUM(simulated_payout) FROM tournament_entries WHERE tournament_id=?", (tid,)).fetchone()[0] == res.prize_pool
    ev_types = {r[0] for r in conn.execute("SELECT DISTINCT event_type FROM tournament_events WHERE tournament_id=?", (tid,))}
    assert {"tournament_started", "player_eliminated", "tournament_completed"} <= ev_types
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_decision_observation_never_contains_other_players_cards(conn, tournament):
    rows = conn.execute(
        "SELECT d.hand_id, d.seat, d.observation_json FROM decisions d"
    ).fetchall()
    holes = {}
    for r in conn.execute("SELECT hand_id, seat, hole_cards_json FROM offline_hole_cards"):
        holes[(r[0], r[1])] = json.loads(r[2])
    from poker_lab.domain.cards import card_to_str

    checked = 0
    for hand_id, seat, obs_json in rows:
        obs = json.loads(obs_json)
        own = [card_to_str(c) for c in obs["hole_cards"]]
        assert own == holes[(hand_id, seat)]
        visible = {card_to_str(c) for c in obs["hole_cards"] + obs["board"]}
        others = {c for (h, s), cards in holes.items() if h == hand_id and s != seat for c in cards}
        assert not (visible & others)
        assert "hole_cards_dealt" not in obs_json
        checked += 1
    assert checked > 50


def test_hand_insert_is_atomic(conn, tournament):
    tid, res, exp = tournament
    before = conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    from poker_lab.agents.random_agent import RandomAgent
    from poker_lab.application.hand_runner import play_hand
    from poker_lab.engine.hand import HandEngine

    e = HandEngine([("a", 100), ("b", 100)], 0, 1, 2, seed=1)
    rec = play_hand(e, [RandomAgent("a"), RandomAgent("b")])
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_hand(
            conn,
            rec,
            seat_agent_version_ids=["missing-version", "missing-version"],
            seat_entry_ids=[None, None],
            tournament_id=tid,
            experiment_id=exp,
            table_number=1,
            hand_number=10**6,
            round_=0,
            level_index=0,
            started_at=dbmod.now_iso(),
        )
    assert conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0] == before
    assert conn.execute("SELECT COUNT(*) FROM hands WHERE hand_id=?", (rec.hand_id,)).fetchone()[0] == 0


def test_notes_crud_and_link_validation(conn, tournament):
    tid, res, exp = tournament
    dec = conn.execute("SELECT decision_id, hand_id FROM decisions LIMIT 1").fetchone()
    nid = create_note(conn, NoteIn(title="Suspicious call", body_markdown="**why?**", category="decision_review", tags=["Call", "river"], decision_id=dec[0]))
    n = get_note(conn, nid)
    assert n["hand_id"] == dec[1] and n["tournament_id"] == tid and n["experiment_id"] == exp
    assert json.loads(n["tags_json"]) == ["call", "river"]
    update_note(conn, nid, NoteIn(title="Reviewed", status="resolved", decision_id=dec[0]))
    assert get_note(conn, nid)["status"] == "resolved"
    assert [x["note_id"] for x in list_notes(conn, hand_id=dec[1])] == [nid]
    with pytest.raises(NoteLinkError):
        create_note(conn, NoteIn(title="bad", hand_id="does-not-exist"))
    with pytest.raises(ValueError):
        NoteIn(title="")
    assert delete_note(conn, nid) and get_note(conn, nid) is None


def test_backup_and_restore(conn, tournament, tmp_path):
    tid, _, _ = tournament
    dest = dbmod.backup(conn, tmp_path / "backup" / "copy.db")
    c2 = dbmod.open_db(dest)
    assert c2.execute("SELECT COUNT(*) FROM hands").fetchone()[0] == conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    assert c2.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_retention_keeps_noted_hands(conn, tournament):
    hands = [r[0] for r in conn.execute("SELECT hand_id FROM hands ORDER BY hand_number")]
    keep = hands[0]
    create_note(conn, NoteIn(title="keep this one", hand_id=keep))
    out = prune(conn, 0, now=datetime.now(UTC) + timedelta(days=1))
    assert out["action_events_deleted"] > 0
    assert conn.execute("SELECT COUNT(*) FROM action_events WHERE hand_id=?", (keep,)).fetchone()[0] > 0
    assert conn.execute("SELECT COUNT(*) FROM action_events WHERE hand_id != ?", (keep,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] > 0  # decisions are kept


def test_allin_ev_offline():
    from poker_lab.analytics.allin import allin_ev
    from poker_lab.domain.actions import Action
    from poker_lab.engine.hand import HandEngine
    from tests.engine.helpers import make_deck

    e = HandEngine([("a", 1000), ("b", 1000)], 0, 50, 100, deck=make_deck(["AsAd", "KsKd"], "2c7h9dJc3s"))
    e.apply(0, Action.raise_to(1000))
    e.apply(1, Action.call())
    est = allin_ev(e, samples=3000, seed=1)
    assert abs(est[0][0] - 0.82) < 0.03 and abs(est[1][0] - 0.18) < 0.03
    assert abs(est[0][1] - (0.82 * 2000 - 1000)) < 70
    assert abs(est[0][1] + est[1][1]) < 1e-6  # zero-sum heads-up
