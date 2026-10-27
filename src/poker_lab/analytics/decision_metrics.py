"""Offline per-decision metrics computed ONLY from the decision-time observation.

Uses ``decisions.observation_json`` (exactly what the agent saw) — never
``offline_hole_cards``, results, or later streets — so these metrics describe decision
quality inputs, not outcomes. When the agent did not record an equity estimate, equity is
re-estimated against *uniformly random* opponent hands, which is a coarse approximation
(real opponents' ranges are narrower after they bet); ``equity_basis`` says which.
"""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from poker_lab.domain.seeds import derive_seed
from poker_lab.persistence.db import now_iso, transaction
from poker_lab.strategy.equity import monte_carlo_equity
from poker_lab.strategy.math import breakeven_fold_equity, count_outs, ev_call, pot_odds, spr


def stack_bucket(eff_bb: float) -> str:
    if eff_bb < 10:
        return "<10bb"
    if eff_bb < 20:
        return "10-20bb"
    if eff_bb < 40:
        return "20-40bb"
    return "40bb+"


def pot_type(obs: dict[str, Any]) -> str:
    live = sum(1 for s in obs["seats"] if not s["folded"])
    if obs["street"] != "preflop":
        return "postflop_heads_up" if live == 2 else "postflop_multiway"
    pre = [a for a in obs["history"] if a["street"] == "preflop"]
    raises = sum(1 for a in pre if a["kind"] == "raise")
    if raises == 0:
        return "limped" if any(a["kind"] == "call" for a in pre) else "unopened"
    return "single_raised" if raises == 1 else "three_bet_plus"


def compute_metrics(obs: dict[str, Any], info: dict[str, Any], chips_added: int, seed: int, samples: int = 200) -> dict[str, Any]:
    bb = obs["big_blind"]
    me = next(s for s in obs["seats"] if s["seat"] == obs["seat"])
    my_total = me["stack"] + me["street_commitment"]
    opp = [s["stack"] + s["street_commitment"] for s in obs["seats"] if s["seat"] != obs["seat"] and not s["folded"]]
    eff = min(my_total, max(opp)) if opp else my_total
    pot = obs["pot"]
    to_call = obs["to_call"]
    n_opp = max(1, sum(1 for s in obs["seats"] if not s["folded"]) - 1)
    hole = obs["hole_cards"]
    board = obs["board"]
    if isinstance(info.get("equity"), (int, float)) and info.get("method") == "monte_carlo":
        equity, stderr = float(info["equity"]), info.get("stderr")
        basis = f"agent_estimate:{info.get('opponent_model', 'unknown')}"
    else:
        est = monte_carlo_equity(hole, board, n_opp, samples, random.Random(seed))
        equity, stderr, basis = est.equity, est.stderr, f"vs_uniform_random_hands_mc{samples}"
    outs = count_outs(hole, board) if len(board) in (3, 4) else None
    icm = info.get("icm") or {}
    return {
        "stack_bucket": stack_bucket(eff / bb),
        "effective_bb": round(eff / bb, 3),
        "spr": round(spr(eff - me["street_commitment"], pot), 4) if board else None,
        "pot_odds": round(pot_odds(to_call, pot), 5),
        "pot_type": pot_type(obs),
        "players_in_pot": n_opp + 1,
        "outs": outs["outs"] if outs else None,
        "outs_p_next": outs["p_next_card"] if outs else None,
        "equity": round(equity, 5),
        "equity_basis": basis,
        "equity_stderr": None if stderr is None else round(float(stderr), 5),
        "ev_call_chips": round(ev_call(equity, pot, to_call), 2) if to_call > 0 else None,
        "breakeven_fold_equity": round(breakeven_fold_equity(chips_added - to_call, pot + to_call), 5)
        if chips_added > to_call
        else None,
        "icm_breakeven_equity": icm.get("icm_breakeven_equity"),
        "chip_breakeven_equity": icm.get("chip_breakeven_equity"),
    }


def compute_for_tournament(conn: sqlite3.Connection, tournament_id: str, *, role: str | None = "hero", samples: int = 200) -> int:
    t = conn.execute("SELECT scenario_label, seed FROM tournaments WHERE tournament_id=?", (tournament_id,)).fetchone()
    field_profile = (t["scenario_label"] or "").split("|")[0] if t else None
    sql = (
        "SELECT d.decision_id, d.observation_json, d.agent_info_json, d.chips_added, h.phase FROM decisions d"
        " JOIN hands h ON h.hand_id = d.hand_id"
        " JOIN hand_players hp ON hp.hand_id = d.hand_id AND hp.seat = d.seat"
        " LEFT JOIN tournament_entries e ON e.entry_id = hp.entry_id"
        " WHERE h.tournament_id = ? AND NOT EXISTS (SELECT 1 FROM decision_metrics m WHERE m.decision_id = d.decision_id)"
    )
    params: list[Any] = [tournament_id]
    if role:
        sql += " AND e.role = ?"
        params.append(role)
    rows = conn.execute(sql, params).fetchall()
    ts = now_iso()
    with transaction(conn):
        for r in rows:
            obs = json.loads(r["observation_json"])
            info = json.loads(r["agent_info_json"] or "{}")
            m = compute_metrics(obs, info, r["chips_added"], derive_seed(t["seed"] if t else 0, "dm", r["decision_id"]), samples)
            conn.execute(
                "INSERT INTO decision_metrics(decision_id,phase,stack_bucket,effective_bb,spr,pot_odds,pot_type,players_in_pot,outs,"
                "outs_p_next,equity,equity_basis,equity_stderr,ev_call_chips,breakeven_fold_equity,icm_breakeven_equity,"
                "chip_breakeven_equity,field_profile,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r["decision_id"], r["phase"], m["stack_bucket"], m["effective_bb"], m["spr"], m["pot_odds"], m["pot_type"],
                    m["players_in_pot"], m["outs"], m["outs_p_next"], m["equity"], m["equity_basis"], m["equity_stderr"],
                    m["ev_call_chips"], m["breakeven_fold_equity"], m["icm_breakeven_equity"], m["chip_breakeven_equity"],
                    field_profile, ts,
                ),
            )
    return len(rows)
