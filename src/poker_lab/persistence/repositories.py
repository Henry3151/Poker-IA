"""Repository functions. All writes go through parameterised SQL."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from poker_lab.application.hand_runner import HandRecord
from poker_lab.domain.cards import card_to_str
from poker_lab.domain.seeds import validate_seed
from poker_lab.persistence.db import code_version, dumps, now_iso, transaction


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------- experiments
def create_experiment(
    conn: sqlite3.Connection,
    name: str,
    algorithm: str,
    config: dict[str, Any],
    seed: int | None,
    hypothesis: str | None = None,
    experiment_id: str | None = None,
) -> str:
    eid = experiment_id or new_id()
    conn.execute(
        "INSERT INTO experiments(experiment_id,name,hypothesis,algorithm,code_version,config_json,seed,status,created_at)"
        " VALUES (?,?,?,?,?,?,?, 'created', ?)",
        (eid, name, hypothesis, algorithm, code_version(), dumps(config), None if seed is None else validate_seed(seed), now_iso()),
    )
    return eid


def set_experiment_status(conn: sqlite3.Connection, experiment_id: str, status: str) -> None:
    conn.execute(
        "UPDATE experiments SET status=?, completed_at=CASE WHEN ? IN ('completed','failed') THEN ? ELSE completed_at END"
        " WHERE experiment_id=?",
        (status, status, now_iso(), experiment_id),
    )


# ---------------------------------------------------------------- artifacts
def register_artifact(
    conn: sqlite3.Connection, artifact_type: str, path: str, sha256: str, size_bytes: int, metadata: dict[str, Any] | None = None
) -> str:
    aid = new_id()
    conn.execute(
        "INSERT INTO artifacts(artifact_id,artifact_type,path,sha256,size_bytes,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",
        (aid, artifact_type, path, sha256, size_bytes, dumps(metadata or {}), now_iso()),
    )
    return aid


# ---------------------------------------------------------------- agent versions
def get_or_create_agent_version(
    conn: sqlite3.Connection,
    name: str,
    algorithm: str,
    version_label: str,
    config: dict[str, Any] | None = None,
    checkpoint_artifact_id: str | None = None,
    checkpoint_sha256: str | None = None,
    status: str = "candidate",
    parent_version_id: str | None = None,
) -> str:
    row = conn.execute(
        "SELECT agent_version_id, checkpoint_sha256 FROM agent_versions WHERE name=? AND version_label=?", (name, version_label)
    ).fetchone()
    if row:
        if checkpoint_sha256 and row["checkpoint_sha256"] and row["checkpoint_sha256"] != checkpoint_sha256:
            raise ValueError(f"agent version {name}@{version_label} already exists with a different checkpoint")
        return str(row["agent_version_id"])
    vid = new_id()
    conn.execute(
        "INSERT INTO agent_versions(agent_version_id,name,algorithm,version_label,checkpoint_artifact_id,checkpoint_sha256,"
        "config_json,code_version,parent_version_id,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            vid,
            name,
            algorithm,
            version_label,
            checkpoint_artifact_id,
            checkpoint_sha256,
            dumps(config or {}),
            code_version(),
            parent_version_id,
            status,
            now_iso(),
        ),
    )
    return vid


def set_agent_status(conn: sqlite3.Connection, agent_version_id: str, status: str) -> None:
    conn.execute("UPDATE agent_versions SET status=? WHERE agent_version_id=?", (status, agent_version_id))


def champion_of(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM agent_versions WHERE name=? AND status='champion'", (name,)
    ).fetchone()
    return row


# ---------------------------------------------------------------- tournaments
def create_tournament(
    conn: sqlite3.Connection,
    tournament_id: str,
    experiment_id: str | None,
    name: str,
    config: dict[str, Any],
    seed: int,
    entrant_count: int,
    table_size: int,
    starting_stack: int,
    buy_in: int,
) -> None:
    conn.execute(
        "INSERT INTO tournaments(tournament_id,experiment_id,name,config_json,seed,entrant_count,table_size,starting_stack,"
        "buy_in,prize_pool,status,started_at) VALUES (?,?,?,?,?,?,?,?,?,?, 'running', ?)",
        (
            tournament_id,
            experiment_id,
            name,
            dumps(config),
            validate_seed(seed),
            entrant_count,
            table_size,
            starting_stack,
            buy_in,
            buy_in * entrant_count,
            now_iso(),
        ),
    )


def insert_entry(
    conn: sqlite3.Connection, entry_id: str, tournament_id: str, agent_version_id: str, label: str
) -> None:
    conn.execute(
        "INSERT INTO tournament_entries(entry_id,tournament_id,agent_version_id,participant_label) VALUES (?,?,?,?)",
        (entry_id, tournament_id, agent_version_id, label),
    )


def insert_tournament_event(
    conn: sqlite3.Connection, tournament_id: str, seq: int, round_: int, etype: str, payload: dict[str, Any]
) -> None:
    conn.execute(
        "INSERT INTO tournament_events(event_id,tournament_id,sequence_number,round,event_type,payload_json,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (new_id(), tournament_id, seq, round_, etype, dumps(payload), now_iso()),
    )


# ---------------------------------------------------------------- hands
def insert_hand(
    conn: sqlite3.Connection,
    rec: HandRecord,
    *,
    seat_agent_version_ids: list[str],
    seat_entry_ids: list[str | None],
    tournament_id: str | None,
    experiment_id: str | None,
    table_number: int | None,
    hand_number: int,
    round_: int | None,
    level_index: int | None,
    started_at: str,
    allin_estimates: dict[int, tuple[float, float]] | None = None,
) -> None:
    """Write a complete hand (hand, players, offline cards, decisions, events) atomically."""
    e = rec.engine
    r = rec.result
    completed = now_iso()
    showdown = set(r.showdown_seats)
    winners = {w for p in r.pots if not p.uncalled for w in p.winners}
    from poker_lab.domain.observation import position_label

    with transaction(conn):
        conn.execute(
            "INSERT INTO hands(hand_id,tournament_id,experiment_id,table_number,hand_number,round,level_index,small_blind,big_blind,"
            "ante,button_seat,player_count,final_street,board_json,pot_total,chips_conserved,seed,started_at,completed_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec.hand_id,
                tournament_id,
                experiment_id,
                table_number,
                hand_number,
                round_,
                level_index,
                e.sb_amount,
                e.bb_amount,
                e.ante,
                e.button,
                e.n,
                r.final_street.label,
                dumps([card_to_str(c) for c in r.board]),
                r.pot_total,
                int(sum(r.ending_stacks) == sum(r.starting_stacks)),
                e.seed,
                started_at,
                completed,
            ),
        )
        for i in range(e.n):
            eq = (allin_estimates or {}).get(i)
            conn.execute(
                "INSERT INTO hand_players(hand_id,seat,entry_id,agent_version_id,participant_label,position,starting_stack,"
                "ending_stack,net_chips,went_to_showdown,won_at_showdown,eliminated,allin_equity,allin_ev_chips)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rec.hand_id,
                    i,
                    seat_entry_ids[i],
                    seat_agent_version_ids[i],
                    rec.seat_agents[i].name if rec.seat_agents else f"seat{i}",
                    position_label((i - e.button) % e.n, e.n),
                    r.starting_stacks[i],
                    r.ending_stacks[i],
                    r.net[i],
                    int(i in showdown),
                    int(i in showdown and i in winners),
                    int(r.ending_stacks[i] == 0),
                    eq[0] if eq else None,
                    eq[1] if eq else None,
                ),
            )
            conn.execute(
                "INSERT INTO offline_hole_cards(hand_id,seat,hole_cards_json,shown_at_showdown) VALUES (?,?,?,?)",
                (rec.hand_id, i, dumps([card_to_str(c) for c in e.hole_cards_offline(i)]), int(i in showdown)),
            )
        for d in rec.decisions:
            info = d.info or {}
            eq_val = info.get("equity")
            conn.execute(
                "INSERT INTO decisions(decision_id,hand_id,seq_in_hand,agent_version_id,participant_label,seat,street,position,"
                "own_hole_cards_json,board_json,pot_before,to_call,stack_before,effective_stack,big_blind,observation_json,"
                "legal_actions_json,requested_action_json,applied_action_json,action_type,action_amount,chips_added,action_valid,"
                "fallback_applied,issue,error_message,equity_estimate,equity_method,equity_samples,equity_stderr,pot_odds,"
                "agent_info_json,decision_latency_ms,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    d.decision_id,
                    d.hand_id,
                    d.seq_in_hand,
                    seat_agent_version_ids[d.seat],
                    d.player_id,
                    d.seat,
                    d.street,
                    d.position,
                    dumps([card_to_str(c) for c in d.observation["hole_cards"]]),
                    dumps([card_to_str(c) for c in d.observation["board"]]),
                    d.pot_before,
                    d.to_call,
                    d.stack_before,
                    d.effective_stack,
                    d.big_blind,
                    dumps(d.observation),
                    dumps(d.legal),
                    dumps(d.requested) if d.requested is not None else None,
                    dumps(d.applied),
                    d.applied["kind"],
                    d.applied.get("amount"),
                    d.chips_added,
                    int(d.valid),
                    int(d.fallback_applied),
                    d.issue,
                    d.error,
                    float(eq_val) if isinstance(eq_val, (int, float)) else None,
                    info.get("method"),
                    info.get("samples"),
                    info.get("stderr"),
                    info.get("pot_odds"),
                    dumps(info),
                    d.latency_ms,
                    completed,
                ),
            )
            if not d.valid:
                conn.execute(
                    "INSERT INTO audit_issues(issue_id,issue_type,severity,tournament_id,hand_id,decision_id,detail_json,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        new_id(),
                        d.issue,
                        "warning",
                        tournament_id,
                        d.hand_id,
                        d.decision_id,
                        dumps({"error": d.error, "requested": d.requested, "applied": d.applied, "participant": d.player_id}),
                        completed,
                    ),
                )
        for ev in e.events:
            conn.execute(
                "INSERT INTO action_events(event_id,hand_id,sequence_number,event_type,visibility,payload_json,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (new_id(), rec.hand_id, ev.seq, ev.type, ev.visibility, dumps(ev.payload), completed),
            )
        if sum(r.ending_stacks) != sum(r.starting_stacks):  # pragma: no cover - engine asserts first
            conn.execute(
                "INSERT INTO audit_issues(issue_id,issue_type,severity,tournament_id,hand_id,detail_json,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (new_id(), "chip_inconsistency", "critical", tournament_id, rec.hand_id, dumps({}), completed),
            )


# ---------------------------------------------------------------- training / evaluation
def start_training_run(
    conn: sqlite3.Connection, experiment_id: str, algorithm: str, game: str, seed: int, config: dict[str, Any], iteration_start: int = 0
) -> str:
    rid = new_id()
    conn.execute(
        "INSERT INTO training_runs(training_run_id,experiment_id,algorithm,game,status,seed,config_json,iteration_start,started_at)"
        " VALUES (?,?,?,?, 'running', ?,?,?,?)",
        (rid, experiment_id, algorithm, game, validate_seed(seed), dumps(config), iteration_start, now_iso()),
    )
    return rid


def finish_training_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    iteration_end: int | None,
    elapsed_seconds: float,
    peak_memory_mb: float | None,
    throughput: float | None,
    metrics: dict[str, Any],
    checkpoint_artifact_id: str | None = None,
    agent_version_id: str | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE training_runs SET status=?, iteration_end=?, elapsed_seconds=?, peak_memory_mb=?, throughput_per_second=?,"
        " metrics_json=?, checkpoint_artifact_id=?, agent_version_id=?, error_message=?, completed_at=? WHERE training_run_id=?",
        (
            status,
            iteration_end,
            elapsed_seconds,
            peak_memory_mb,
            throughput,
            dumps(metrics),
            checkpoint_artifact_id,
            agent_version_id,
            error,
            now_iso(),
            run_id,
        ),
    )


def insert_explanation(
    conn: sqlite3.Connection,
    *,
    scope: str,
    category: str,
    origin: str,
    evidence_kind: str,
    summary: str,
    evidence: dict[str, Any],
    confidence: float | None,
    limitations: str,
    tournament_id: str | None = None,
    entry_id: str | None = None,
    hand_id: str | None = None,
    decision_id: str | None = None,
    agent_version_id: str | None = None,
    reviewer: str | None = None,
) -> str:
    xid = new_id()
    conn.execute(
        "INSERT INTO explanations(explanation_id,scope,tournament_id,entry_id,hand_id,decision_id,agent_version_id,category,origin,"
        "evidence_kind,summary,evidence_json,confidence,limitations,reviewer,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            xid,
            scope,
            tournament_id,
            entry_id,
            hand_id,
            decision_id,
            agent_version_id,
            category,
            origin,
            evidence_kind,
            summary,
            dumps(evidence),
            confidence,
            limitations,
            reviewer,
            now_iso(),
        ),
    )
    return xid
