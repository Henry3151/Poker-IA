"""Build the 169-class preflop equity-vs-one-random-hand table (deterministic, seeded).

Usage: python scripts/build_preflop_table.py [samples]
Writes src/poker_lab/strategy/data/preflop_equity_vs_random.json
"""

import json
import random
import sys
import time
from pathlib import Path

from poker_lab.domain.cards import all_hand_classes
from poker_lab.strategy.equity import monte_carlo_equity
from poker_lab.strategy.ranges import representative_cards

samples = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
seed = 20261026
rng = random.Random(seed)
t0 = time.perf_counter()
table = {}
for cls in all_hand_classes():
    est = monte_carlo_equity(representative_cards(cls), [], 1, samples, rng)
    table[cls] = {"equity": round(est.equity, 5), "stderr": round(est.stderr, 5)}
out = {
    "description": "Preflop all-in equity of each 169 class vs one uniformly random hand (Monte Carlo).",
    "method": "monte_carlo",
    "samples_per_class": samples,
    "seed": seed,
    "elapsed_seconds": round(time.perf_counter() - t0, 1),
    "classes": table,
}
p = Path(__file__).resolve().parents[1] / "src/poker_lab/strategy/data/preflop_equity_vs_random.json"
p.write_text(json.dumps(out, indent=1))
print(f"wrote {p} in {out['elapsed_seconds']}s")
