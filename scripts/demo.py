"""Demo: one 12-player 6-max MTT with mixed agents, persisted to artifacts/demo.db.

Run:  python scripts/demo.py   (Windows: run_demo.bat)
"""

from __future__ import annotations

from pathlib import Path

from poker_lab.agents.registry import OPPONENT_PROFILES, AgentSpec
from poker_lab.application.tournament_service import EntrantSpec, run_tournament
from poker_lab.evaluation.finance import entry_rows
from poker_lab.notes.service import NoteIn, create_note
from poker_lab.persistence.db import open_db
from poker_lab.persistence.migration_safety import safe_migrate
from poker_lab.tournament.config import TournamentConfig

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "artifacts" / "demo.db"


def main() -> None:
    print("migrations:", safe_migrate(DB, ROOT / "artifacts" / "backups")["applied"] or "up to date")
    conn = open_db(DB)
    entrants = [
        EntrantSpec("hero_equity", AgentSpec(algorithm="equity", params={"samples": 120, "icm": True}), "equity_icm"),
        EntrantSpec("heuristic", AgentSpec(algorithm="heuristic")),
        EntrantSpec("random", AgentSpec(algorithm="random")),
    ] + [EntrantSpec(f"{p}_{i}", OPPONENT_PROFILES[p], f"field_{p}") for i, p in enumerate(["tag", "lag", "nit", "station"] * 2 + ["tag"])]
    cfg = TournamentConfig(starting_stack=3000, hands_per_level=8, buy_in=100, fee=10)
    seed = int(conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]) + 1
    tid, res = run_tournament(conn, cfg, entrants, seed=seed, hero_labels=frozenset({"hero_equity"}))
    print(f"tournament {tid}: {res.hands_played} hands, prize pool {res.prize_pool} SIM")
    for e in res.standings():
        print(f"  {e.place:>2}. {e.label:<14} payout={e.payout:>5}")
    hero = [r for r in entry_rows(conn, role="hero") if r["tournament_id"] == tid][0]
    print(f"hero net={hero['net_profit']} SIM, ROI={hero['roi']:.2%} (ONE tournament: not evidence of anything)")
    create_note(conn, NoteIn(title="demo run", body_markdown="Single tournament; variance dominates.", tournament_id=tid, tags=["demo"]))
    print(f"database: {DB}")


if __name__ == "__main__":
    main()
