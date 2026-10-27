"""Print the P7c frozen-rule decision tables (markdown) from docs/p7c_artifacts/p7c_final_report.json.

Practical relevance (pre-registered delta = 0.10 buy-in per tournament):
- "melhora relevante":   CI entirely above +delta
- "piora relevante":     CI entirely below -delta
- "equivalência prática": CI entirely inside (-delta, +delta)
- "piora (relevância incerta)" / "melhora (relevância incerta)": CI excludes 0 but crosses +-delta
- "inconclusivo":        CI contains 0 (inconclusive is NOT equivalence)
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REP = json.loads((ROOT / "docs/p7c_artifacts/p7c_final_report.json").read_text())
DELTA = 0.10
SCEN = ["robust_mix", "adaptive_only", "bluff_heavy", "baseline_mixed", "selfplay_hybrid", "versions_mix"]


def relevance(lo: float, hi: float) -> str:
    if lo > DELTA:
        return "melhora relevante"
    if hi < -DELTA:
        return "piora relevante"
    if lo > -DELTA and hi < DELTA:
        return "equivalência prática"
    if lo > 0:
        return "melhora (relevância incerta)"
    if hi < 0:
        return "piora (relevância incerta)"
    return "inconclusivo"


def decision_tables() -> str:
    cc = REP["champion_challenger"]
    out = []
    for ch, d in cc["decisions"].items():
        out += [f"**{ch}** − hybrid_v1 · decisão: `{d['decision']}` ({d['reason']}) · estimativas ≥ 0: {d['nonnegative_scenarios']}/6 · "
                f"ações inválidas: {cc['invalid_actions'][ch]}", "",
                "| cenário | n | diferença (buy-ins/torneio) | IC 95% | p | p Holm | relevância (δ = 0,10) |",
                "|---|---|---|---|---|---|---|"]
        for s in SCEN:
            t = d["tests"][s]
            out.append(f"| {s} | {t['n']} | {t['estimate']:+.3f} | [{t['ci_low']:+.3f}; {t['ci_high']:+.3f}] | {t['p_value']:.4f} | "
                       f"{t['p_holm']:.4f} | {relevance(t['ci_low'], t['ci_high'])} |")
        out.append("")
    return "\n".join(out)


def roi_table() -> str:
    cands = ["hybrid_v1", "hybrid_v2_adaptive", "hybrid_v1_bluffcatch", "lag", "pushfold_p7"]
    out = ["| cenário | " + " | ".join(cands) + " |", "|---|" + "---|" * len(cands)]
    for s in SCEN:
        row = []
        for c in cands:
            r = REP["scenarios"][s][c]["roi"]
            row.append(f"{r['estimate'] * 100:+.1f}% [{r['ci_low'] * 100:+.1f}; {r['ci_high'] * 100:+.1f}]")
        out.append(f"| {s} (n={REP['scenarios'][s]['hybrid_v1']['n_tournaments']}) | " + " | ".join(row) + " |")
    return "\n".join(out)


def lag_table() -> str:
    out = ["| cenário | LAG − hybrid_v1 | IC 95% | n | relevância |", "|---|---|---|---|---|"]
    for s in SCEN:
        v = REP["paired_vs_baseline"][s]["lag"]
        out.append(f"| {s} | {v['estimate']:+.3f} | [{v['ci_low']:+.3f}; {v['ci_high']:+.3f}] | {v['n']} | {relevance(v['ci_low'], v['ci_high'])} |")
    return "\n".join(out)


def breakdown_table() -> str:
    b = REP["breakdowns"]["hybrid_v1"]
    out = ["| dimensão | grupo | mãos | bb/mão | IC 95% (cluster) |", "|---|---|---|---|---|"]
    for dim in ("position", "stack_bucket", "phase"):
        for g, v in sorted(b[dim].items()):
            out.append(f"| {dim} | {g} | {v['hands']} | {v['estimate']:+.3f} | [{v['ci_low']:+.3f}; {v['ci_high']:+.3f}] |")
    return "\n".join(out)


def luck_table() -> str:
    out = ["| candidato | mãos all-in | sorte média (bb/all-in) | IC 95% |", "|---|---|---|---|"]
    for c, v in REP["allin_luck"].items():
        m = v["luck_bb_mean"]
        out.append(f"| {c} | {v['allin_hands']} | {m['estimate']:+.3f} | [{m['ci_low']:+.3f}; {m['ci_high']:+.3f}] |")
    return "\n".join(out)


if __name__ == "__main__":
    for name, fn in (("DECISION", decision_tables), ("ROI", roi_table), ("LAG", lag_table), ("BREAKDOWN", breakdown_table),
                     ("LUCK", luck_table)):
        print(f"<!--{name}-->\n{fn()}\n")
