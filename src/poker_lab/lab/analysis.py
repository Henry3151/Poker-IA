"""Decision analysis of a finished (or running) local session (P9-D, lean scope).

Everything here is read from the session store and works only with decision-time information:
the classification of a decision never looks at how the hand ended. Recommendations are
*hypotheses for a future champion/challenger experiment*; nothing here changes the policy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from poker_lab.domain.cards import hand_class
from poker_lab.lab.quality import ADEQUATE, ERROR, INCONCLUSIVE, TECHNICAL, wilson_interval
from poker_lab.lab.store import SessionStore

MIN_PATTERN_N = 5  # a pattern needs at least this many evaluable decisions to be reported
MIN_EXPERIMENT_N = 30  # ...and this many to justify proposing an experiment

FORMAT_NOTE = ("Sessão em formato cash (stacks reiniciados a cada mão). As métricas de torneio (ROI, ITM) "
               "ficam nas avaliações MTT (P7–P7c) e não são misturadas com estas.")


def _rate(k: int, n: int) -> dict[str, Any]:
    if n == 0:
        return {"k": k, "n": n, "rate": None, "ci95": None}
    lo, hi = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 4), "ci95": [round(lo, 4), round(hi, 4)]}


def analyze_session(store: SessionStore, session_id: str) -> dict[str, Any] | None:
    srows = store.query("SELECT * FROM sessions WHERE session_id=?", (session_id,))
    if not srows:
        return None
    s = srows[0]
    decs = store.query(
        "SELECT d.hand_id, d.seq, d.street, d.position, d.label, d.issue, d.observation_json, d.applied_json, d.assessment_json,"
        " h.hand_no FROM decisions d JOIN hands h ON h.hand_id = d.hand_id WHERE d.session_id=? ORDER BY h.hand_no, d.seq",
        (session_id,))
    labels: dict[str, int] = defaultdict(int)
    by_pos: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_street: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    patterns: dict[tuple[str, str, str], dict[str, Any]] = {}
    evaluated: list[dict[str, Any]] = []
    technical: list[dict[str, Any]] = []
    inconclusive_reasons: dict[str, int] = defaultdict(int)
    for d in decs:
        lab = d["label"]
        labels[lab] += 1
        by_pos[d["position"] or "?"][lab] += 1
        by_street[d["street"] or "?"][lab] += 1
        a = json.loads(d["assessment_json"])
        if lab == TECHNICAL:
            technical.append({"hand_no": d["hand_no"], "issue": d["issue"], "reason": a.get("reason")})
            continue
        if lab == INCONCLUSIVE:
            reason = (a.get("reason") or "").split(":")[0].split("(")[0].strip()
            inconclusive_reasons[reason or "sem motivo"] += 1
            if a.get("ev_gap_bb") is None:
                continue
        obs = json.loads(d["observation_json"])
        cls = hand_class(tuple(obs["hole_cards"]))
        chosen = a.get("reason", "").split("·")[1].strip().split(" ")[0] if "·" in a.get("reason", "") else "?"
        item = {"hand_no": d["hand_no"], "hand_id": d["hand_id"], "spot": a.get("spot"), "class": cls, "label": lab,
                "chosen": chosen, "best": a.get("best_action"), "ev_gap_bb": a.get("ev_gap_bb"),
                "stack_bb": round(obs["stack"] / obs["big_blind"] + 0.0, 1), "confidence": a.get("confidence")}
        evaluated.append(item)
        key = (a.get("spot") or "?", cls, chosen)
        p = patterns.setdefault(key, {"spot": key[0], "class": cls, "chosen": chosen, "best": a.get("best_action"),
                                      "n": 0, "errors": 0, "adequate": 0, "marginal": 0, "ev_gap_total": 0.0})
        p["n"] += 1
        p["errors"] += lab == ERROR
        p["adequate"] += lab == ADEQUATE
        p["marginal"] += lab == INCONCLUSIVE
        p["ev_gap_total"] += a.get("ev_gap_bb") or 0.0
    evaluable = labels[ADEQUATE] + labels[ERROR]
    worst = sorted((e for e in evaluated if (e["ev_gap_bb"] or 0) < 0), key=lambda e: e["ev_gap_bb"])[:20]
    pat_list = sorted((p for p in patterns.values() if p["errors"] > 0 or p["marginal"] > 0),
                      key=lambda p: p["ev_gap_total"])
    recommendations = []
    for p in pat_list:
        if p["n"] < MIN_PATTERN_N:
            continue
        p["ev_gap_total"] = round(p["ev_gap_total"], 3)
        enough = p["n"] >= MIN_EXPERIMENT_N
        recommendations.append({
            "pattern": f"{p['spot']} · {p['class']} · {p['chosen']} (referência prefere {p['best']})",
            "evidence": _rate(p["errors"], p["n"]),
            "ev_gap_total_bb": p["ev_gap_total"],
            "status": "propor experimento" if enough else "observar (amostra pequena)",
            "next_step": ("criar um challenger que ajuste só este spot e avaliá-lo pela regra champion/challenger "
                          "com seeds novas" if enough else
                          f"acumular pelo menos {MIN_EXPERIMENT_N} ocorrências antes de qualquer mudança"),
        })
    for p in pat_list:
        p["ev_gap_total"] = round(p["ev_gap_total"], 3)
    summary = json.loads(s["summary_json"]) if s["summary_json"] else None
    return {
        "session_id": session_id, "state": s["state"], "policy_label": s["policy_label"], "policy_sha256": s["policy_sha256"],
        "hands_played": s["hands_played"], "decisions": len(decs), "labels": dict(labels),
        "adequacy": _rate(labels[ADEQUATE], evaluable), "error_rate": _rate(labels[ERROR], evaluable),
        "coverage": _rate(evaluable, len(decs)),
        "by_position": {k: dict(v) for k, v in sorted(by_pos.items())},
        "by_street": {k: dict(v) for k, v in sorted(by_street.items())},
        "inconclusive_reasons": dict(sorted(inconclusive_reasons.items(), key=lambda kv: -kv[1])),
        "worst_decisions": worst, "patterns": pat_list[:30], "recommendations": recommendations,
        "technical": technical[:50], "results": summary,
        "notes": [
            FORMAT_NOTE,
            "A classificação usa só o que o agente sabia no momento da decisão; o resultado da mão nunca entra.",
            "Recomendações são hipóteses para um experimento futuro; a política da sessão não é alterada.",
            "Cobertura baixa é esperada: só há referência validada para spots heads-up de push/fold.",
        ],
    }


def render_markdown(a: dict[str, Any]) -> str:
    def pct(r: dict[str, Any]) -> str:
        if r["rate"] is None:
            return "—"
        return f"{r['rate'] * 100:.1f}% (IC 95% {r['ci95'][0] * 100:.1f}–{r['ci95'][1] * 100:.1f}%, n={r['n']})"

    lines = [f"# Análise da sessão {a['session_id']}", "",
             f"- Política: `{a['policy_label']}` (sha256 `{a['policy_sha256'][:16]}…`) · estado `{a['state']}`",
             f"- Mãos: {a['hands_played']} · decisões: {a['decisions']} · classificações: {a['labels']}",
             f"- Cobertura (decisões com referência validada): {pct(a['coverage'])}",
             f"- Adequadas entre as avaliáveis: {pct(a['adequacy'])}",
             f"- Prováveis erros entre as avaliáveis: {pct(a['error_rate'])}", ""]
    r = (a.get("results") or {}).get("bb_per_100")
    if r:
        lines += [f"- Resultado: {r['mean']} bb/100 (IC 95% {r['low']} a {r['high']}, n={r['n']})", ""]
    lines += ["## Piores decisões (perda de EV estimada)", "", "| Mão | Spot | Classe | Escolha | Melhor | Perda (bb) | Confiança |",
              "|---:|---|---|---|---|---:|---|"]
    lines += [f"| {w['hand_no']} | {w['spot']} | {w['class']} | {w['chosen']} | {w['best']} | {w['ev_gap_bb']} | {w['confidence']} |"
              for w in a["worst_decisions"]] or ["| — | | | | | | |"]
    lines += ["", "## Recomendações (hipóteses para experimento)", ""]
    lines += [f"- **{x['pattern']}** — erros {pct(x['evidence'])}; perda total {x['ev_gap_total_bb']} bb → "
              f"{x['status']}: {x['next_step']}" for x in a["recommendations"]] or ["- Nenhum padrão com amostra suficiente."]
    lines += ["", "## Motivos das decisões inconclusivas", ""]
    lines += [f"- {k}: {v}" for k, v in a["inconclusive_reasons"].items()] or ["- —"]
    lines += ["", "## Observações", ""] + [f"- {n}" for n in a["notes"]]
    return "\n".join(lines) + "\n"


def write_report(a: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j = out_dir / f"sessao_{a['session_id']}.json"
    m = out_dir / f"sessao_{a['session_id']}.md"
    j.write_text(json.dumps(a, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    m.write_text(render_markdown(a), encoding="utf-8")
    return {"json": str(j), "markdown": str(m)}
