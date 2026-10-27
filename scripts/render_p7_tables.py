"""Render artifacts/p7/p7_report.json into docs/P7_RESULTS_TABLES.md (auto-generated, no hand edits)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
rep = json.loads((ROOT / "artifacts/p7/p7_report.json").read_text())


def pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


lines = [
    "# P7 — tabelas de resultados (gerado automaticamente por scripts/render_p7_tables.py)",
    "",
    f"Evaluation run: `{rep['evaluation_run_id']}` · unidades: {rep['units']}",
    "",
    "ROI = lucro líquido / custo (buy-in 100 + taxa 10). IC 95% bootstrap sobre torneios. "
    "Referência de campo igual: ROI esperado = −9,1% (só a taxa).",
    "",
]
for scen, cands in rep["scenarios"].items():
    lines += [f"## Cenário `{scen}`", "", "| candidato | n | ROI | IC 95% | veredito | ITM | vitórias | drawdown máx (SIM) | reentradas |", "|---|---|---|---|---|---|---|---|---|"]
    for c, s in cands.items():
        if not s.get("n_tournaments"):
            continue
        r = s["roi"]
        lines.append(
            f"| {c} | {s['n_tournaments']} | {pct(r['estimate'])} | [{pct(r['ci_low'])}, {pct(r['ci_high'])}] | {s['roi_verdict']} | "
            f"{s['itm_rate']['estimate']:.1%} | {s['wins']} | {s['drawdown']['max_drawdown']:.0f} | {s['reentries_total']} |"
        )
    pv = rep["paired_vs_baseline"].get(scen, {})
    if pv:
        lines += ["", "Diferença pareada vs `heuristic` (lucro por torneio, em buy-ins de 110):", "", "| candidato | média | IC 95% | n | veredito |", "|---|---|---|---|---|"]
        for c, d in pv.items():
            lines.append(f"| {c} | {d['estimate']:+.3f} | [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] | {d['n']} | {d['verdict']} |")
    lines.append("")

lines += ["## Amostras progressivas (cenário baseline)", "", "| candidato | n | ROI | IC 95% | veredito |", "|---|---|---|---|---|"]
for c, prog in rep["progressive"].items():
    for p in prog:
        r = p["roi"]
        lines.append(f"| {c} | {p['n']} | {pct(r['estimate'])} | [{pct(r['ci_low'])}, {pct(r['ci_high'])}] | {p['roi_verdict']} |")
lines.append("")

lines += ["## Recortes por mão (baseline): bb/mão com IC por cluster (torneios)", ""]
for c, dims in rep["breakdowns"].items():
    lines += [f"### {c}", "", "| dimensão | faixa | mãos | bb/mão | IC 95% | flag |", "|---|---|---|---|---|---|"]
    for dim, buckets in dims.items():
        for key, b in buckets.items():
            lines.append(f"| {dim} | {key} | {b['hands']} | {b['estimate']:+.3f} | [{b['ci_low']:+.3f}, {b['ci_high']:+.3f}] | {b['flag']} |")
    lines.append("")

lines += ["## Qualidade de decisão (baseline, só informação disponível na decisão)", "", "| candidato | decisões | calls | margem média equity−pot odds (IC) | calls abaixo das pot odds | mix de ações | base da equity |", "|---|---|---|---|---|---|---|"]
for c, d in rep["decision_quality"].items():
    m = d["call_margin_mean"]
    mtxt = f"{m['estimate']:+.3f} [{m['ci_low']:+.3f}, {m['ci_high']:+.3f}]" if m else "—"
    lines.append(
        f"| {c} | {d['decisions']} | {d['calls']} | {mtxt} | {d['calls_below_pot_odds_rate']} | "
        f"{', '.join(f'{k} {v:.0%}' for k, v in d['action_mix'].items())} | {d['equity_basis_counts']} |"
    )
lines += ["", "## Sorte de all-in (baseline): resultado − EV de all-in, calculado offline após a mão", "", "| candidato | mãos all-in | sorte total (bb) | sorte média/mão (IC) | EV all-in total (bb) |", "|---|---|---|---|---|"]
for c, d in rep["allin_luck"].items():
    m = d["luck_bb_mean"]
    lines.append(f"| {c} | {d['allin_hands']} | {d['luck_bb_total']:+.1f} | {m['estimate']:+.2f} [{m['ci_low']:+.2f}, {m['ci_high']:+.2f}] | {d['allin_ev_bb_total']:+.1f} |")

(ROOT / "docs/P7_RESULTS_TABLES.md").write_text("\n".join(lines) + "\n")
print("written docs/P7_RESULTS_TABLES.md")
