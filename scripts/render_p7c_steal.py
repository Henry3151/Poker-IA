"""Render docs/P7C_STEAL_TABLES.md from artifacts/p7c/steal_analysis.json (no hand-typed numbers)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "artifacts/p7c/steal_analysis.json"
OUT = ROOT / "docs/P7C_STEAL_TABLES.md"
CANDS = ["hybrid_v1", "hybrid_v2_adaptive", "hybrid_v1_bluffcatch", "lag", "pushfold_p7"]


def ci(v: dict | None) -> str:
    if not v:
        return "—"
    return f"{v['estimate']:+.2f} [{v['ci_low']:+.2f}; {v['ci_high']:+.2f}] (n={v['n']})"


def resp(r: dict) -> str:
    return ", ".join(f"{k} {v * 100:.0f}%" for k, v in sorted(r.items()))


def main() -> None:
    d = json.loads(SRC.read_text())
    lines = [
        "# P7c: steal e re-steal (tabelas geradas por `scripts/render_p7c_steal.py`)",
        "",
        "Fonte: `artifacts/p7c/steal_analysis.json`, calculado sobre `final.db` (somente leitura).",
        "Steal = primeiro a entrar com raise em CO, BTN ou SB. Unidade: bb por mão do herói.",
        "IC 95% por bootstrap de cluster (torneio). Só informação pública foi usada para classificar o defensor.",
        "",
    ]
    for scen, cands in d.items():
        lines += [f"## Cenário `{scen}`", "",
                  "| candidato | oportunidades | taxa de steal | ganha sem showdown | lucro por steal (bb) | EV por oportunidade (bb) | resposta ao re-steal | taxa 1ª/2ª metade |",
                  "|---|---|---|---|---|---|---|---|"]
        for c in CANDS:
            x = cands.get(c)
            if not x:
                continue
            rr = x.get("resteal_response") or {}
            lines.append(
                f"| {c} | {x['late_first_in_opps']} | {x['steal_rate'] * 100:.1f}% | {x['steal_won_immediately'] * 100:.1f}% | "
                f"{ci(x.get('steal_net_bb_per_hand'))} | {x.get('ev_per_opportunity_open_line_bb', 0):+.2f} | "
                f"{resp(rr)} ({x.get('resteal_faced', 0)}) | {x['steal_rate_first_half'] * 100:.0f}% / {x['steal_rate_second_half'] * 100:.0f}% |"
            )
        lines.append("")
        for c in ("hybrid_v1", "hybrid_v2_adaptive"):
            x = cands.get(c)
            if not x:
                continue
            lines += [f"**{c}: lucro por steal por dimensão (bb)**", "", "| dimensão | grupo | estimativa [IC 95%] |", "|---|---|---|"]
            for dim, groups in x["by_dimension_steal_net_bb"].items():
                for g, v in sorted(groups.items()):
                    lines.append(f"| {dim} | {g} | {ci(v)} |")
            lines.append("")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
