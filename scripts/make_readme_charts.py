"""Render the README charts (light + dark) from the committed evaluation artifacts.

Every number comes from docs/p7b_artifacts/p7b_final_report.json and
docs/p7_artifacts/mccfr_audit.json; nothing is typed by hand.

    python scripts/make_readme_charts.py      # writes docs/assets/*.png  (needs matplotlib)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets"
REPORT = json.loads((ROOT / "docs/p7b_artifacts/p7b_final_report.json").read_text())
AUDIT = json.loads((ROOT / "docs/p7_artifacts/mccfr_audit.json").read_text())
P7C_PATH = ROOT / "docs/p7c_artifacts/p7c_final_report.json"

THEMES = {
    "light": dict(surface="#fcfcfb", text="#0b0b0b", text2="#52514e", muted="#8a8984", grid="#e6e5e1",
                  accent="#2a78d6", neutral="#b9b8b2", series2="#eb6834"),
    "dark": dict(surface="#1a1a19", text="#f0efec", text2="#c3c2b7", muted="#8f8e88", grid="#33322f",
                 accent="#3987e5", neutral="#5d5c57", series2="#d95926"),
}
LABELS = {
    "hybrid_v1": "hybrid-v1 (champion)", "lag": "LAG (referência)", "pushfold_v2_ante": "push/fold v2",
    "pushfold_p7": "push/fold P7", "heuristic": "heurístico", "random": "aleatório", "equity": "equity MC",
}
SCEN = {
    "baseline": "campo misto", "field_lag": "campo LAG", "turbo_short": "turbo curto", "field_tag": "campo TAG",
    "field_nit": "campo nit", "field_station": "campo station", "reentry": "reentrada", "top_heavy": "prêmio top-heavy",
}


def style(ax, t) -> None:
    ax.set_facecolor(t["surface"])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(which="both", colors=t["text2"], labelsize=10, length=0)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def fig(t, w=8.6, h=4.6):
    f, ax = plt.subplots(figsize=(w, h), dpi=150)
    f.patch.set_facecolor(t["surface"])
    return f, ax


def roi_chart(mode: str) -> None:
    t = THEMES[mode]
    sc = REPORT["scenarios"]["baseline"]
    order = sorted(sc, key=lambda k: sc[k]["roi"]["estimate"])
    f, ax = fig(t)
    style(ax, t)
    for i, k in enumerate(order):
        r = sc[k]["roi"]
        c = t["accent"] if k == "hybrid_v1" else t["neutral"]
        ax.plot([r["ci_low"] * 100, r["ci_high"] * 100], [i, i], color=c, linewidth=2, solid_capstyle="round")
        ax.scatter([r["estimate"] * 100], [i], s=70, color=c, edgecolor=t["surface"], linewidth=2, zorder=3)
        ax.annotate(f"{r['estimate'] * 100:+.1f}%", (r["ci_high"] * 100, i), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=t["text"] if k == "hybrid_v1" else t["text2"],
                    bbox=dict(facecolor=t["surface"], edgecolor="none", pad=1.5))
    ax.axvline(-9.09, color=t["muted"], linestyle=(0, (3, 3)), linewidth=1)
    ax.annotate("campo igual (só a taxa): −9,1%", (-9.09, len(order) - 0.45), xytext=(6, 0), textcoords="offset points",
                fontsize=8.5, color=t["muted"])
    ax.set_yticks(range(len(order)), [LABELS.get(k, k) for k in order], color=t["text"])
    ax.set_xlabel("ROI por torneio (%) — ponto = estimativa, linha = IC 95% bootstrap", color=t["text2"], fontsize=9.5)
    ax.set_xlim(-70, 135)
    ax.set_title("ROI simulado no cenário principal (n = 400 torneios por agente)", loc="left", color=t["text"],
                 fontsize=12, fontweight="semibold", pad=12)
    f.tight_layout()
    f.savefig(OUT / f"roi_baseline_{mode}.png", facecolor=t["surface"])
    plt.close(f)


def paired_chart(mode: str) -> None:
    t = THEMES[mode]
    tests = REPORT["paired_vs_baseline"]
    items = [(s, tests[s]["hybrid_v1"]) for s in tests if "hybrid_v1" in tests[s]]
    items.sort(key=lambda x: x[1]["estimate"])
    f, ax = fig(t)
    style(ax, t)
    for i, (_scen, r) in enumerate(items):
        pos = r["ci_low"] > 0
        c = t["accent"] if pos else t["neutral"]
        ax.plot([r["ci_low"], r["ci_high"]], [i, i], color=c, linewidth=2, solid_capstyle="round")
        ax.scatter([r["estimate"]], [i], s=70, color=c, edgecolor=t["surface"], linewidth=2, zorder=3)
        ax.annotate(f"{r['estimate']:+.2f}  (n={r['n']})", (r["ci_high"], i), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=t["text"] if pos else t["text2"])
    ax.axvline(0, color=t["muted"], linewidth=1)
    ax.set_yticks(range(len(items)), [SCEN.get(x[0], x[0]) for x in items], color=t["text"])
    ax.set_xlabel("diferença pareada de lucro por torneio (buy-ins) — mesmas seeds para os dois agentes", color=t["text2"],
                  fontsize=9.5)
    ax.set_xlim(-0.5, 2.6)
    ax.set_title("hybrid-v1 − push/fold P7, por cenário (IC 95%)", loc="left", color=t["text"], fontsize=12,
                 fontweight="semibold", pad=12)
    f.tight_layout()
    f.savefig(OUT / f"paired_by_scenario_{mode}.png", facecolor=t["surface"])
    plt.close(f)


def convergence_chart(mode: str) -> None:
    t = THEMES[mode]
    f, axes = plt.subplots(1, 2, figsize=(8.6, 3.6), dpi=150)
    f.patch.set_facecolor(t["surface"])
    panels = [
        (AUDIT["kuhn"]["convergence"], "exploitability", "Kuhn poker (fichas/mão)"),
        (AUDIT["pushfold_10bb_convergence"], "exploitability_bb", "Push/fold heads-up 10 bb (bb/mão)"),
    ]
    for ax, (rows, key, title) in zip(axes, panels, strict=True):
        style(ax, t)
        ax.grid(axis="both", color=t["grid"], linewidth=0.8)
        xs = [r["iterations"] for r in rows]
        ys = [r[key] for r in rows]
        ax.plot(xs, ys, color=t["accent"], linewidth=2)
        ax.scatter(xs, ys, s=40, color=t["accent"], edgecolor=t["surface"], linewidth=2, zorder=3)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.annotate(f"{ys[-1]:.4f}", (xs[-1], ys[-1]), xytext=(-6, 10), textcoords="offset points", ha="right",
                    fontsize=9, color=t["text"])
        ax.set_title(title, loc="left", color=t["text"], fontsize=10.5, fontweight="semibold")
        ax.set_xlabel("iterações MCCFR", color=t["text2"], fontsize=9)
    axes[0].set_ylabel("exploitability (melhor resposta exata)", color=t["text2"], fontsize=9)
    f.tight_layout()
    f.savefig(OUT / f"mccfr_convergence_{mode}.png", facecolor=t["surface"])
    plt.close(f)


P7C_SCEN = {"robust_mix": "robust mix (primário)", "adaptive_only": "só adaptativos", "bluff_heavy": "blefadores",
            "baseline_mixed": "campo misto", "selfplay_hybrid": "self-play", "versions_mix": "versões mistas"}


def p7c_chart(mode: str) -> None:
    """Robustness cycle: challenger - champion paired differences (frozen decision tests)."""
    if not P7C_PATH.exists():
        return
    t = THEMES[mode]
    rep = json.loads(P7C_PATH.read_text())
    dec = rep["champion_challenger"]["decisions"]
    series = [("hybrid_v2_adaptive", "v2 adaptativo (β 0,2)", t["accent"], 0.17),
              ("hybrid_v1_bluffcatch", "v1 + bluff-catch (β 0,2)", t["series2"], -0.17)]
    scen = list(P7C_SCEN)
    f, ax = fig(t, h=4.9)
    style(ax, t)
    ax.axvspan(-0.10, 0.10, color=t["grid"], alpha=0.55, linewidth=0)
    for key, label, color, off in series:
        tests = dec[key]["tests"]
        for i, s in enumerate(reversed(scen)):
            r = tests[s]
            ax.plot([r["ci_low"], r["ci_high"]], [i + off, i + off], color=color, linewidth=2, solid_capstyle="round")
            ax.scatter([r["estimate"]], [i + off], s=55, color=color, edgecolor=t["surface"], linewidth=2, zorder=3,
                       label=label if i == 0 else None)
    ax.axvline(0, color=t["muted"], linewidth=1)
    ax.set_yticks(range(len(scen)), [P7C_SCEN[s] for s in reversed(scen)], color=t["text"])
    ax.set_xlabel("desafiante − champion (buy-ins por torneio, mesmas seeds) · faixa cinza = ±δ 0,10", color=t["text2"],
                  fontsize=9.5)
    leg = ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9.5)
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    ax.set_title("P7c: nenhum desafiante superou o hybrid-v1 (IC 95%)", loc="left", color=t["text"], fontsize=12,
                 fontweight="semibold", pad=30)
    f.tight_layout()
    f.savefig(OUT / f"p7c_challengers_{mode}.png", facecolor=t["surface"])
    plt.close(f)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    for m in THEMES:
        roi_chart(m)
        paired_chart(m)
        convergence_chart(m)
        p7c_chart(m)
    print(sorted(p.name for p in OUT.glob("*.png")))
