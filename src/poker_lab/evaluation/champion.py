"""Champion/challenger with criteria fixed BEFORE the final evaluation.

A challenger is promoted only if ALL hold (docs/P7B_REPORT.md, "Critérios"):
1. primary scenario: paired difference (challenger - champion, net per tournament in
   buy-ins) has a 95% bootstrap CI entirely above 0, with n >= min_n;
2. Holm-adjusted bootstrap p-value < alpha across every (challenger, scenario) test run;
3. no key scenario shows a paired difference whose CI is entirely below 0 (regression);
4. zero invalid actions for the challenger.
Otherwise the champion is kept ('keep_champion', 'inconclusive' or 'challenger_failed').
"""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from poker_lab.evaluation.stats import bootstrap_ci
from poker_lab.persistence import repositories as repo
from poker_lab.persistence.db import dumps, now_iso, transaction


def bootstrap_pvalue(diffs: Sequence[float], resamples: int = 4000, seed: int = 0) -> float:
    """Two-sided bootstrap p-value for mean(diffs) == 0 (shifted-null bootstrap)."""
    n = len(diffs)
    if n < 2:
        return 1.0
    m = sum(diffs) / n
    centred = [d - m for d in diffs]
    rng = random.Random(seed)
    extreme = 0
    for _ in range(resamples):
        s = sum(centred[rng.randrange(n)] for _ in range(n)) / n
        if abs(s) >= abs(m):
            extreme += 1
    return (extreme + 1) / (resamples + 1)


def holm(pvalues: Mapping[str, float]) -> dict[str, float]:
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adj: dict[str, float] = {}
    running = 0.0
    for k, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - k) * p))
        adj[name] = running
    return adj


@dataclass
class Criteria:
    primary_scenario: str
    key_scenarios: list[str]
    min_n: int = 400
    alpha: float = 0.05
    level: float = 0.95


@dataclass
class Decision:
    challenger: str
    decision: str
    reason: str
    tests: dict[str, dict[str, Any]] = field(default_factory=dict)


def decide(
    paired: Mapping[str, Mapping[str, Sequence[float]]],
    invalid_actions: Mapping[str, int],
    criteria: Criteria,
    seed: int = 0,
) -> dict[str, Decision]:
    """``paired[challenger][scenario]`` = per-tournament paired differences (buy-ins)."""
    pvals: dict[str, float] = {}
    cis: dict[str, Any] = {}
    for ch, by_s in paired.items():
        for scen, diffs in by_s.items():
            key = f"{ch}|{scen}"
            pvals[key] = bootstrap_pvalue(list(diffs), seed=seed)
            cis[key] = bootstrap_ci(list(diffs), level=criteria.level, seed=seed + 1)
    adj = holm(pvals)
    out: dict[str, Decision] = {}
    for ch, by_s in paired.items():
        tests = {
            scen: {**cis[f"{ch}|{scen}"].as_dict(), "p_value": round(pvals[f"{ch}|{scen}"], 5), "p_holm": round(adj[f"{ch}|{scen}"], 5)}
            for scen in by_s
        }
        prim = tests.get(criteria.primary_scenario)
        regress = [s for s in criteria.key_scenarios if s in tests and tests[s]["ci_high"] < 0]
        if invalid_actions.get(ch, 0) > 0:
            d = Decision(ch, "challenger_failed", f"{invalid_actions[ch]} invalid actions", tests)
        elif prim is None or prim["n"] < criteria.min_n:
            d = Decision(ch, "inconclusive", "primary scenario missing or n < min_n", tests)
        elif regress:
            d = Decision(ch, "keep_champion", f"regression (CI < 0) in {regress}", tests)
        elif prim["ci_low"] > 0 and prim["p_holm"] < criteria.alpha:
            d = Decision(ch, "promote", "primary CI > 0, Holm p < alpha, no regression, no invalid actions", tests)
        elif prim["ci_high"] < 0:
            d = Decision(ch, "keep_champion", "challenger worse than champion in the primary scenario", tests)
        else:
            d = Decision(ch, "inconclusive", "primary CI contains 0 or Holm-adjusted p >= alpha", tests)
        out[ch] = d
    return out


def record_and_apply(
    conn: sqlite3.Connection,
    *,
    experiment_id: str | None,
    champion_version_id: str,
    challenger_ids: Mapping[str, str],
    decisions: Mapping[str, Decision],
    criteria: Criteria,
    suite: dict[str, Any],
) -> str | None:
    """Store every decision in ``evaluations``; promote at most one challenger (largest primary
    effect among those meeting all criteria). Returns the promoted version id or None."""
    promoted: str | None = None
    winners = [d for d in decisions.values() if d.decision == "promote"]
    best = max(winners, key=lambda d: d.tests[criteria.primary_scenario]["estimate"]) if winners else None
    with transaction(conn):
        for ch, d in decisions.items():
            prim = d.tests.get(criteria.primary_scenario, {})
            decision = d.decision
            reason = d.reason
            if decision == "promote" and best is not None and d is not best:
                decision, reason = "keep_champion", "another challenger met the criteria with a larger effect"
            conn.execute(
                "INSERT INTO evaluations(evaluation_id,experiment_id,champion_version_id,challenger_version_id,suite_json,metric,"
                "n_samples,champion_mean,challenger_mean,diff_mean,ci_low,ci_high,confidence_level,invalid_actions,decision,reason,"
                "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    repo.new_id(), experiment_id, champion_version_id, challenger_ids[ch],
                    dumps({**suite, "tests": d.tests, "criteria": criteria.__dict__}),
                    "paired_net_per_tournament_buyins", int(prim.get("n", 0)), None, None, prim.get("estimate"),
                    prim.get("ci_low"), prim.get("ci_high"), criteria.level, 0, decision, reason, now_iso(),
                ),
            )
            if decision == "promote":
                conn.execute("UPDATE agent_versions SET status='retired' WHERE agent_version_id=?", (champion_version_id,))
                conn.execute("UPDATE agent_versions SET status='champion' WHERE agent_version_id=?", (challenger_ids[ch],))
                promoted = challenger_ids[ch]
    return promoted
