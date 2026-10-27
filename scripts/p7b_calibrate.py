"""Calibrate bluff_rate of the postflop betting-range filter on the DEVELOPMENT set only.

For every hero decision facing a postflop bet in artifacts/p7b/dev.db, compare:
- the equity estimate the agent can compute at decision time (only own cards + board),
  for several bluff_rate values, against
- the true equity vs the opponents' actual cards (offline, exact/MC over the runout).
Writes artifacts/p7b/calibration.json.
"""

from __future__ import annotations

import json
import random
import sqlite3
from itertools import combinations
from pathlib import Path

from poker_lab.domain.cards import parse_card
from poker_lab.engine.evaluator import evaluate
from poker_lab.evaluation.stats import bootstrap_ci
from poker_lab.strategy.equity import monte_carlo_equity
from poker_lab.strategy.postflop_ranges import betting_filter

ROOT = Path(__file__).resolve().parents[1]
BETAS = [0.0, 0.1, 0.2, 0.35, 0.5, 1.0]


def true_equity(mine, board, opp_cards, rng):
    dead = set(mine) | set(board) | {c for oc in opp_cards for c in oc}
    deck = [c for c in range(52) if c not in dead]
    need = 5 - len(board)
    runouts = list(combinations(deck, need)) if need <= 2 else [tuple(rng.sample(deck, need)) for _ in range(300)]
    tot = 0.0
    for ro in runouts:
        b = board + list(ro)
        me = evaluate(mine + b)
        scores = [evaluate(oc + b) for oc in opp_cards]
        best = max(scores)
        tot += 1.0 if me > best else (1 / (1 + scores.count(me)) if me == best else 0.0)
    return tot / len(runouts)


def main() -> None:
    conn = sqlite3.connect(f"file:{ROOT / 'artifacts/p7b/dev.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    holes = {
        (r["hand_id"], r["seat"]): [parse_card(x) for x in json.loads(r["hole_cards_json"])]
        for r in conn.execute("SELECT hand_id, seat, hole_cards_json FROM offline_hole_cards")
    }
    rows = conn.execute(
        "SELECT d.hand_id, d.street, d.observation_json FROM decisions d WHERE d.participant_label='hero'"
        " AND d.street != 'preflop' AND d.to_call > 0"
    ).fetchall()
    rng = random.Random(5)
    data = []
    for r in rows:
        obs = json.loads(r["observation_json"])
        opp = [s["seat"] for s in obs["seats"] if not s["folded"] and s["seat"] != obs["seat"]]
        mine, board = list(obs["hole_cards"]), list(obs["board"])
        te = true_equity(mine, board, [holes[(r["hand_id"], s)] for s in opp], rng)
        ests = {}
        for beta in BETAS:
            est_rng = random.Random(11)
            flt = betting_filter(board, beta, est_rng) if beta < 1.0 else None
            ests[beta] = monte_carlo_equity(mine, board, len(opp), 200, est_rng, flt, max_rejections=200).equity
        data.append((r["street"], te, ests))
    out: dict = {"n_decisions": len(data), "by_beta": {}}
    for beta in BETAS:
        per = {}
        for street in ("flop", "turn", "river", "all"):
            diffs = [e[beta] - t for s, t, e in data if street in ("all", s)]
            if diffs:
                ci = bootstrap_ci(diffs, seed=1, resamples=1000)
                per[street] = {"n": len(diffs), "bias": round(ci.estimate, 4), "ci": [round(ci.low, 4), round(ci.high, 4)],
                               "mae": round(sum(abs(x) for x in diffs) / len(diffs), 4)}
        out["by_beta"][str(beta)] = per
    best = min(BETAS, key=lambda b: abs(out["by_beta"][str(b)]["all"]["bias"]))
    out["selected_bluff_rate"] = best
    (ROOT / "artifacts/p7b/calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
