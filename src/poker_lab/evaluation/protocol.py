"""Evaluation protocol: candidates x scenarios x independent seeded tournaments.

Design (docs/EVALUATION_PROTOCOL.md):
- One *hero* seat per tournament plays the candidate; the other seats are a fixed field.
- Common random numbers: for scenario s and index k, every candidate plays the tournament
  with the same seed (same seating, same field agents/seeds, same deck seeds). Differences
  between candidates are therefore paired comparisons, which reduces variance.
- Tournaments are independent units: CIs bootstrap over tournaments (or seed-paired
  differences), never over hands within a tournament.
- Work is split into shards (job index % shard_count) that write separate SQLite files;
  shards are merged afterwards. Results do not depend on the number of shards.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from poker_lab.agents.registry import OPPONENT_PROFILES, AgentSpec
from poker_lab.application.tournament_service import EntrantSpec, run_tournament
from poker_lab.domain.seeds import derive_seed
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.db import code_version, now_iso, open_db, transaction
from poker_lab.tournament.config import DEFAULT_LEVELS, BlindLevel, TournamentConfig

FIELD_MIX = ["tag", "lag", "nit", "station"]


class Scenario(BaseModel):
    label: str
    field_profile: str = "mixed"  # mixed | tag | lag | nit | station | random
    entrants: int = Field(default=12, ge=2)
    starting_stack: int = 3000
    hands_per_level: int = 8
    blind_scale: float = 1.0  # multiplies every level (turbo-like starts)
    buy_in: int = 100
    fee: int = 10
    reentry_levels: int = 0
    max_entries: int = 1
    payout_percentages: list[float] = Field(default_factory=lambda: [50.0, 30.0, 20.0])
    n_tournaments: int = Field(default=100, ge=1)

    def tournament_config(self) -> TournamentConfig:
        levels = [
            BlindLevel(
                small_blind=max(1, int(lv.small_blind * self.blind_scale)),
                big_blind=max(1, int(lv.big_blind * self.blind_scale)),
                ante=int(lv.ante * self.blind_scale),
            )
            for lv in DEFAULT_LEVELS
        ]
        return TournamentConfig(
            name=f"eval:{self.label}",
            starting_stack=self.starting_stack,
            hands_per_level=self.hands_per_level,
            levels=levels,
            buy_in=self.buy_in,
            fee=self.fee,
            reentry_levels=self.reentry_levels,
            max_entries=self.max_entries,
            payout_percentages=self.payout_percentages,
        )

    def field(self) -> list[EntrantSpec]:
        out = []
        for i in range(self.entrants - 1):
            prof = FIELD_MIX[i % len(FIELD_MIX)] if self.field_profile == "mixed" else self.field_profile
            out.append(EntrantSpec(f"field{i:02d}_{prof}", OPPONENT_PROFILES[prof], lineage=f"field_{prof}"))
        return out


class Candidate(BaseModel):
    label: str
    spec: AgentSpec
    lineage: str | None = None


class Protocol(BaseModel):
    name: str
    seed: int
    candidates: list[Candidate]
    scenarios: list[Scenario]
    progressive_n: list[int] = Field(default_factory=lambda: [25, 50, 100, 200, 400])
    bootstrap_resamples: int = 2000
    min_n_claim: int = 200

    def run_id(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"poker_lab/eval/{self.name}/{self.seed}"))

    def seed_for(self, scenario: Scenario, k: int) -> int:
        return derive_seed(self.seed, "scenario", scenario.label, k)

    def jobs(self) -> list[tuple[Scenario, Candidate, int]]:
        return [(s, c, k) for s in self.scenarios for k in range(s.n_tournaments) for c in self.candidates]


HERO = "hero"


def _ensure_run(conn: sqlite3.Connection, protocol: Protocol) -> str:
    rid = protocol.run_id()
    exp_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"poker_lab/eval-exp/{rid}"))
    with transaction(conn):
        conn.execute(
            "INSERT OR IGNORE INTO experiments(experiment_id,name,hypothesis,algorithm,code_version,config_json,seed,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                exp_id, f"evaluation:{protocol.name}", "Does any candidate show a statistically supported ROI edge vs the field?",
                "evaluation_protocol", code_version(), protocol.model_dump_json(), protocol.seed, "running", now_iso(),
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO evaluation_runs(evaluation_run_id,name,protocol_json,code_version,seed,status,started_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (rid, protocol.name, protocol.model_dump_json(), code_version(), protocol.seed, "running", now_iso()),
        )
    return exp_id


def run_shard(
    db_path: str | Path,
    protocol: Protocol,
    shard_index: int = 0,
    shard_count: int = 1,
    log_every: int = 50,
    record_level: str = "hero",
) -> dict[str, Any]:
    conn = open_db(db_path)
    exp_id = _ensure_run(conn, protocol)
    rid = protocol.run_id()
    done = {r[0] for r in conn.execute("SELECT tournament_id FROM tournaments WHERE status='completed'")}
    jobs = [j for i, j in enumerate(protocol.jobs()) if i % shard_count == shard_index]
    t0 = time.perf_counter()
    ran = 0
    for n, (scen, cand, k) in enumerate(jobs):
        tid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{rid}/{scen.label}/{cand.label}/{k}"))
        if tid in done:
            continue  # resumable
        seed = protocol.seed_for(scen, k)  # same for every candidate (common random numbers)
        entrants = [EntrantSpec(HERO, cand.spec, cand.lineage or cand.label), *scen.field()]
        run_tournament(
            conn, scen.tournament_config(), entrants, seed, exp_id,
            tournament_id=tid, evaluation_run_id=rid, scenario_label=f"{scen.field_profile}|{scen.label}|{cand.label}",
            hero_labels=frozenset({HERO}), record_level=record_level, allin_samples=300,
        )
        ran += 1
        if log_every and ran % log_every == 0:
            el = time.perf_counter() - t0
            print(f"[shard {shard_index}] {n + 1}/{len(jobs)} jobs, {el:.0f}s", flush=True)
    conn.close()
    return {"shard": shard_index, "jobs": len(jobs), "ran": ran, "elapsed_s": round(time.perf_counter() - t0, 1)}


MERGE_ORDER = [
    "experiments", "artifacts", "agent_versions", "evaluation_runs", "tournaments", "tournament_entries", "tournament_events",
    "hands", "hand_players", "offline_hole_cards", "decisions", "action_events", "financial_ledger", "entry_reentries",
    "decision_metrics", "training_runs", "evaluations", "explanations", "audit_issues", "notes",
]


def merge_shards(main_db: str | Path, shard_paths: list[str | Path]) -> dict[str, int]:
    conn = open_db(main_db)
    added: dict[str, int] = {}
    for sp in shard_paths:
        conn.execute("ATTACH DATABASE ? AS shard", (str(sp),))
        try:
            with transaction(conn):
                for t in MERGE_ORDER:
                    cols = [r[1] for r in conn.execute(f"PRAGMA main.table_info({t})")]
                    collist = ",".join(cols)
                    cur = conn.execute(f"INSERT OR IGNORE INTO main.{t}({collist}) SELECT {collist} FROM shard.{t}")  # noqa: S608
                    added[t] = added.get(t, 0) + max(cur.rowcount, 0)
        finally:
            conn.execute("DETACH DATABASE shard")
    problems = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.close()
    if problems:
        raise RuntimeError(f"foreign key problems after merge: {len(problems)}")
    return added


def finish_run(conn: sqlite3.Connection, protocol: Protocol, report: dict[str, Any], report_path: str | Path) -> None:
    from poker_lab.util import file_sha256

    p = Path(report_path)
    with transaction(conn):
        aid = repo.register_artifact(conn, "report", str(p), file_sha256(p), p.stat().st_size, {"kind": "p7_evaluation"})
        conn.execute(
            "UPDATE evaluation_runs SET status='completed', completed_at=?, report_artifact_id=? WHERE evaluation_run_id=?",
            (now_iso(), aid, protocol.run_id()),
        )
        conn.execute(
            "UPDATE experiments SET status='completed', completed_at=? WHERE name=?", (now_iso(), f"evaluation:{protocol.name}")
        )
