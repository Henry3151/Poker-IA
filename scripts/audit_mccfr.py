"""P7 audit of the MCCFR implementation and the push/fold policy.

Writes artifacts/p7/mccfr_audit.json. Measurements:
1. Kuhn poker: exploitability and game value vs. the known equilibrium value -1/18, and the
   known structure of the equilibrium family (P1: bet K = 3x bet J; call Q = bet J + 1/3).
2. Push/fold 10bb: exploitability vs iterations (equity table with 200 samples/pair).
3. Equity-table noise: re-solve on an independent 600-samples/pair table and measure
   (a) frequency differences, (b) exploitability of the 200-table policy inside the
   600-table game (cross-exploitability).
4. Published reference (PokerStrategy.com, "Nash Ranges for the Push-or-Fold Play", Table 1,
   heads-up, no ante, ES = 10): SB push 56.6%, BB call 38.5%, with explicit ranges. We compare
   combo-weighted overlap of the ranges, not only the percentages.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from poker_lab.domain.cards import RANK_CHARS, all_hand_classes
from poker_lab.strategy.ranges import combos_of
from poker_lab.training.games import KuhnPoker, PushFoldGame
from poker_lab.training.mccfr import ExternalSamplingMCCFR, exploitability, policy_value
from poker_lab.training.pushfold_tables import get_or_build

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "p7"

PUBLISHED_10BB = {
    "source": "https://www.pokerstrategy.com/strategy/sit-and-go/1779/ (Table 1, ES=10, no ante, push-or-fold, 0% edge)",
    "push_pct": 56.6,
    "call_pct": 38.5,
    "push_range": "22+, Kx+, Q2s+, Q7o+, J3s+, J8o+, T5s+, T8o+, 95s+, 97o+, 85s+, 87o, 74s+, 64s+, 53s+",
    "call_range": "22+, Ax+, K2s+, K6o+, Q6s+, Q8o+, J8s+, J9o+, T9s",
}


def parse_range(text: str) -> set[str]:
    """Parse the notation used by the source: 22+, Kx+, Q2s+, Q7o+, 87o, T9s, Ax+."""
    out: set[str] = set()
    classes = all_hand_classes()
    for tok in (t.strip() for t in text.split(",")):
        if re.fullmatch(r"([2-9TJQKA])\1\+", tok):
            lo = RANK_CHARS.index(tok[0])
            out |= {c for c in classes if len(c) == 2 and RANK_CHARS.index(c[0]) >= lo}
        elif re.fullmatch(r"[2-9TJQKA]x\+", tok):
            hi = RANK_CHARS.index(tok[0])
            out |= {c for c in classes if RANK_CHARS.index(c[0]) >= hi}
        elif m := re.fullmatch(r"([2-9TJQKA])([2-9TJQKA])([so])\+", tok):
            hi, lo, s = RANK_CHARS.index(m[1]), RANK_CHARS.index(m[2]), m[3]
            out |= {f"{m[1]}{RANK_CHARS[k]}{s}" for k in range(lo, hi)}
        elif re.fullmatch(r"[2-9TJQKA][2-9TJQKA][so]", tok):
            out.add(tok)
        else:
            raise ValueError(f"unparsed token {tok!r}")
    return out


def pct(classes: set[str]) -> float:
    return round(sum(combos_of(c) for c in classes) / 1326 * 100, 2)


def solve(table: dict, stack: float, iters: int, seed: int) -> tuple[PushFoldGame, dict[str, list[float]]]:
    g = PushFoldGame(stack, table["classes"], table["equity"], table["weights"])
    m = ExternalSamplingMCCFR(g, seed)
    m.run(iters)
    return g, m.average_strategy()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rep: dict = {}
    t0 = time.perf_counter()
    # 1. Kuhn
    g = KuhnPoker()
    m = ExternalSamplingMCCFR(g, seed=2026)
    kuhn = []
    for n in (1_000, 10_000, 100_000):
        m.run(n - m.state.iterations)
        avg = m.average_strategy()
        kuhn.append({"iterations": n, "exploitability": round(exploitability(g, avg), 6), "value_p1": round(policy_value(g, avg), 6)})
    alpha = avg["J:"][1]
    rep["kuhn"] = {
        "known_value_p1": round(-1 / 18, 6),
        "convergence": kuhn,
        "equilibrium_structure": {
            "bet_J_alpha": round(alpha, 4),
            "bet_K_should_be_3alpha": round(3 * alpha, 4),
            "bet_K_observed": round(avg["K:"][1], 4),
            "call_Q_should_be_alpha_plus_1_3": round(alpha + 1 / 3, 4),
            "call_Q_observed": round(avg["Q:pb"][1], 4),
        },
    }
    # 2. convergence at 10bb
    t200 = get_or_build(ROOT / "artifacts/tables/hu_class_equity_s200_seed20261026.json", 200, 20261026)
    conv = []
    for n in (2_000, 20_000, 100_000, 200_000):
        g10, pol = solve(t200, 10.0, n, seed=11)
        conv.append({"iterations": n, "exploitability_bb": round(exploitability(g10, pol), 6)})
    rep["pushfold_10bb_convergence"] = conv
    # 3. table noise
    t600 = get_or_build(ROOT / "artifacts/tables/hu_class_equity_s600_seed777.json", 600, 777)
    g600, pol600 = solve(t600, 10.0, 200_000, seed=11)
    classes = t200["classes"]
    push200 = {c: pol.get(f"SB:{c}", [1, 0])[1] for c in classes}
    push600 = {c: pol600.get(f"SB:{c}", [1, 0])[1] for c in classes}
    call200 = {c: pol.get(f"BB:{c}", [1, 0])[1] for c in classes}
    call600 = {c: pol600.get(f"BB:{c}", [1, 0])[1] for c in classes}

    def wpct(p: dict[str, float]) -> float:
        return round(sum(p[c] * combos_of(c) for c in classes) / 1326 * 100, 2)

    diffs = [abs(push200[c] - push600[c]) for c in classes] + [abs(call200[c] - call600[c]) for c in classes]
    rep["equity_table_sensitivity_10bb"] = {
        "table200": {"push_pct": wpct(push200), "call_pct": wpct(call200)},
        "table600": {"push_pct": wpct(push600), "call_pct": wpct(call600)},
        "mean_abs_prob_diff": round(sum(diffs) / len(diffs), 4),
        "max_abs_prob_diff": round(max(diffs), 4),
        "classes_with_diff_gt_0_5": sum(1 for d in diffs if d > 0.5),
        "exploitability_of_table200_policy_in_table600_game_bb": round(exploitability(g600, pol), 6),
        "exploitability_of_table600_policy_in_table600_game_bb": round(exploitability(g600, pol600), 6),
    }
    # 4. published comparison (using the 600-table solution and the 200-table solution)
    pub_push = parse_range(PUBLISHED_10BB["push_range"])
    pub_call = parse_range(PUBLISHED_10BB["call_range"])
    comp = {"published": {**PUBLISHED_10BB, "parsed_push_pct": pct(pub_push), "parsed_call_pct": pct(pub_call)}}
    for name, (pp, cc) in {"table200": (push200, call200), "table600": (push600, call600)}.items():
        ours_push = {c for c in classes if pp[c] >= 0.5}
        ours_call = {c for c in classes if cc[c] >= 0.5}

        def overlap(a: set[str], b: set[str]) -> dict[str, float]:
            inter = pct(a & b)
            union = pct(a | b)
            return {"jaccard_combos": round(inter / union, 4) if union else 1.0, "only_ours": sorted(a - b), "only_published": sorted(b - a)}

        comp[name] = {
            "push_pct_threshold_0_5": pct(ours_push),
            "call_pct_threshold_0_5": pct(ours_call),
            "push_overlap": overlap(ours_push, pub_push),
            "call_overlap": overlap(ours_call, pub_call),
        }
    rep["published_comparison_10bb"] = comp
    rep["elapsed_seconds"] = round(time.perf_counter() - t0, 1)
    (OUT / "mccfr_audit.json").write_text(json.dumps(rep, indent=1))
    json.dump({k: rep[k] for k in ("kuhn", "pushfold_10bb_convergence", "equity_table_sensitivity_10bb")}, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
