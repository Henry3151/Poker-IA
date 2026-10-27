"""Use case: run a tournament and persist everything (hands, decisions, events, results)."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from poker_lab.agents.registry import AgentSpec, create_agent
from poker_lab.analytics.allin import allin_ev
from poker_lab.application.hand_runner import HandRecord
from poker_lab.domain.seeds import derive_seed, validate_seed
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.db import dumps, now_iso, transaction
from poker_lab.tournament.config import TournamentConfig
from poker_lab.tournament.director import HandContext, TournamentDirector, TournamentEvent, TournamentResult

log = logging.getLogger("poker_lab.tournament")


@dataclass(frozen=True, slots=True)
class EntrantSpec:
    label: str
    spec: AgentSpec
    lineage: str | None = None  # agent_versions.name; defaults to algorithm


def register_agent_version(conn: sqlite3.Connection, spec: AgentSpec, lineage: str | None = None) -> str:
    sha = None
    artifact_id = None
    if spec.checkpoint_path:
        from poker_lab.training.checkpoints import load_checkpoint_meta

        meta = load_checkpoint_meta(spec.checkpoint_path)
        sha = meta["sha256"]
        row = conn.execute("SELECT artifact_id FROM artifacts WHERE sha256=? AND artifact_type='checkpoint'", (sha,)).fetchone()
        artifact_id = row["artifact_id"] if row else None
    status = "baseline" if spec.algorithm in ("random", "heuristic", "equity") else "candidate"
    return repo.get_or_create_agent_version(
        conn,
        lineage or spec.algorithm,
        spec.algorithm,
        spec.version_label,
        config={"params": spec.params, "checkpoint_path": spec.checkpoint_path},
        checkpoint_artifact_id=artifact_id,
        checkpoint_sha256=sha,
        status=status,
    )


def run_tournament(
    conn: sqlite3.Connection,
    cfg: TournamentConfig,
    entrants: list[EntrantSpec],
    seed: int,
    experiment_id: str | None = None,
    *,
    analyze: bool = False,
    allin_samples: int = 600,
    tournament_id: str | None = None,
    evaluation_run_id: str | None = None,
    scenario_label: str | None = None,
    hero_labels: frozenset[str] = frozenset(),
) -> tuple[str, TournamentResult]:
    validate_seed(seed)
    version_ids = {e.label: register_agent_version(conn, e.spec, e.lineage) for e in entrants}
    agents = [
        (e.label, create_agent(e.spec, e.label, derive_seed(seed, "agent", i, e.label))) for i, e in enumerate(entrants)
    ]

    def on_hand(ctx: HandContext, rec: HandRecord) -> None:
        est = allin_ev(rec.engine, samples=allin_samples, seed=derive_seed(seed, "allin", ctx.hand_number))
        repo.insert_hand(
            conn,
            rec,
            seat_agent_version_ids=[version_ids[a.name] for a in rec.seat_agents],
            seat_entry_ids=list(ctx.seat_entry_ids),
            tournament_id=ctx.tournament_id,
            experiment_id=experiment_id,
            table_number=ctx.table_number,
            hand_number=ctx.hand_number,
            round_=ctx.round,
            level_index=ctx.level_index,
            started_at=rec.started_at,
            allin_estimates=est,
            phase=ctx.phase,
            players_remaining=ctx.players_remaining,
        )

    events: list[TournamentEvent] = []
    director = TournamentDirector(cfg, agents, seed, tournament_id=tournament_id, on_hand=on_hand, on_event=events.append)
    tid = director.tournament_id
    with transaction(conn):
        repo.create_tournament(
            conn, tid, experiment_id, cfg.name, cfg.model_dump(), seed, len(entrants), cfg.table_size, cfg.starting_stack, cfg.buy_in
        )
        conn.execute(
            "UPDATE tournaments SET fee_per_entry=?, reentry_levels=?, max_entries_per_player=?, evaluation_run_id=?,"
            " scenario_label=? WHERE tournament_id=?",
            (cfg.fee, cfg.reentry_levels, cfg.max_entries, evaluation_run_id, scenario_label, tid),
        )
        for e in director.entries_list:
            repo.insert_entry(conn, e.entry_id, tid, version_ids[e.label], e.label)
            if e.label in hero_labels:
                conn.execute("UPDATE tournament_entries SET role='hero' WHERE entry_id=?", (e.entry_id,))
    log.info("tournament_started", extra={"tournament_id": tid, "entrants": len(entrants), "seed": seed})
    try:
        result = director.run()
    except Exception as exc:
        conn.execute(
            "UPDATE tournaments SET status='failed', error_message=?, completed_at=? WHERE tournament_id=?",
            (f"{type(exc).__name__}: {exc}", now_iso(), tid),
        )
        conn.execute(
            "INSERT INTO audit_issues(issue_id,issue_type,severity,tournament_id,detail_json,created_at) VALUES (?,?,?,?,?,?)",
            (repo.new_id(), "engine_error", "critical", tid, dumps({"error": str(exc)}), now_iso()),
        )
        log.exception("tournament_failed", extra={"tournament_id": tid})
        raise
    with transaction(conn):
        start_seat = {}
        for ev in events:
            if ev.type == "tournament_started":
                start_seat = ev.payload["seating"]
            if ev.type == "player_reentered":
                continue  # stored in entry_reentries (additive schema; event CHECK list unchanged)
            repo.insert_tournament_event(conn, tid, ev.seq, ev.round, ev.type, ev.payload)
        for e in result.entries:
            t, s = start_seat.get(e.label, (None, None))
            conn.execute(
                "UPDATE tournament_entries SET final_place=?, final_stack=?, simulated_payout=?, hands_played=?, eliminated_round=?,"
                " eliminated_hand_id=?, starting_table=?, starting_seat=?, entries_count=? WHERE entry_id=?",
                (e.place, e.stack, e.payout, e.hands_played, e.eliminated_round, e.eliminated_hand_id, t, s, e.entries_count, e.entry_id),
            )
            for r in e.reentries:
                conn.execute(
                    "INSERT INTO entry_reentries(tournament_id,entry_id,entry_number,round,level,busted_hand_id,created_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (tid, e.entry_id, r["entry_number"], r["round"], r["level"], r["hand_id"], now_iso()),
                )
        conn.execute(
            "UPDATE tournaments SET status='completed', hands_played=?, rounds_played=?, prize_pool=?, total_entries=?,"
            " completed_at=? WHERE tournament_id=?",
            (result.hands_played, result.rounds, result.prize_pool, result.total_entries, now_iso(), tid),
        )
        repo.record_tournament_ledger(
            conn,
            tid,
            [
                {"entry_id": e.entry_id, "agent_version_id": version_ids[e.label], "entries_count": e.entries_count, "payout": e.payout}
                for e in result.entries
            ],
            cfg.buy_in,
            cfg.fee,
        )
        problems = repo.reconcile_tournament_ledger(conn, tid)
        if problems:
            raise RuntimeError(f"financial reconciliation failed for {tid}: {problems}")
    log.info("tournament_completed", extra={"tournament_id": tid, "hands": result.hands_played, "winner": result.winner.label})
    if analyze:
        from poker_lab.analytics.explanations import explain_tournament

        explain_tournament(conn, tid)
    return tid, result
