"""P7b Phase A: quantitative audit of the P7 evaluation database (read-only).

Writes artifacts/p7b/diagnosis.json. Every query is read-only on artifacts/p7/p7_lab.db.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "artifacts/p7/p7_lab.db"
OUT = ROOT / "artifacts/p7b"


def q(c: sqlite3.Connection, sql: str, *args: object) -> list[sqlite3.Row]:
    return c.execute(sql, args).fetchall()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rep: dict = {}

    # A1 accounting -----------------------------------------------------------------
    per_t = q(
        c,
        "SELECT t.tournament_id, t.fee_per_entry, t.total_entries, t.prize_pool, t.buy_in, SUM(f.net_profit) AS net,"
        " SUM(f.payout) AS paid, SUM(f.entries_count) AS ents FROM tournaments t JOIN v_entry_financials f"
        " ON f.tournament_id=t.tournament_id WHERE t.evaluation_run_id IS NOT NULL GROUP BY t.tournament_id",
    )
    rep["A1_accounting"] = {
        "tournaments": len(per_t),
        "net_sum_equals_minus_fees": sum(1 for r in per_t if r["net"] == -r["fee_per_entry"] * r["total_entries"]),
        "payouts_equal_prize_pool": sum(1 for r in per_t if r["paid"] == r["prize_pool"]),
        "prize_pool_equals_buyin_x_entries": sum(1 for r in per_t if r["prize_pool"] == r["buy_in"] * r["total_entries"]),
        "entries_match": sum(1 for r in per_t if r["ents"] == r["total_entries"]),
        "chips_not_conserved_hands": q(c, "SELECT COUNT(*) FROM hands WHERE chips_conserved=0")[0][0],
        "invalid_decisions": q(c, "SELECT COUNT(*) FROM decisions WHERE action_valid=0")[0][0],
        "audit_issues": q(c, "SELECT COUNT(*) FROM audit_issues")[0][0],
    }

    # A2 fairness ---------------------------------------------------------------------
    seeds: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for r in q(c, "SELECT scenario_label, seed FROM tournaments WHERE evaluation_run_id IS NOT NULL"):
        _, scen, cand = r["scenario_label"].split("|")
        seeds[scen][cand].add(r["seed"])
    fair = {}
    for scen, by in seeds.items():
        sets = list(by.values())
        fair[scen] = {"candidates": len(by), "identical_seed_sets": all(s == sets[0] for s in sets), "n": len(sets[0])}
    seat = Counter(
        (r["starting_table"], r["starting_seat"])
        for r in q(c, "SELECT starting_table, starting_seat FROM tournament_entries WHERE role='hero'")
    )
    tables = Counter(k[0] for k in seat.elements())
    seats_only = Counter(k[1] for k in seat.elements())
    n_hero = sum(seat.values())
    exp = n_hero / 6
    chi2 = sum((v - exp) ** 2 / exp for v in seats_only.values())
    # same hero seat across candidates for the same seed (CRN seating)
    same_seat = q(
        c,
        "SELECT t.seed, COUNT(DISTINCT e.starting_table || ':' || e.starting_seat) AS k FROM tournament_entries e"
        " JOIN tournaments t ON t.tournament_id=e.tournament_id WHERE e.role='hero' GROUP BY t.seed",
    )
    rep["A2_fairness"] = {
        "seed_sets_by_scenario": fair,
        "hero_table_counts": dict(tables),
        "hero_seat_counts": {str(k): v for k, v in sorted(seats_only.items())},
        "seat_chi2_df5": round(chi2, 2),
        "seeds_with_identical_hero_seat_across_candidates": sum(1 for r in same_seat if r["k"] == 1),
        "seeds_total": len(same_seat),
    }

    # A3 variance & power --------------------------------------------------------------
    var = {}
    for r in q(
        c,
        "SELECT t.scenario_label AS lbl, f.net_profit AS net FROM v_entry_financials f JOIN tournaments t"
        " ON t.tournament_id=f.tournament_id WHERE f.role='hero' AND t.scenario_label LIKE '%|baseline|%'",
    ):
        var.setdefault(r["lbl"].split("|")[2], []).append(r["net"] / 110)
    power = {}
    for cand, xs in var.items():
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
        power[cand] = {
            "n": len(xs),
            "mean_buyins": round(m, 4),
            "sd_buyins": round(sd, 3),
            "n_needed_detect_0_1_buyin_80pct": math.ceil((2.8 * sd / 0.1) ** 2),
            "n_needed_detect_0_2_buyin_80pct": math.ceil((2.8 * sd / 0.2) ** 2),
        }
    rep["A3_variance_power_unpaired"] = power

    # A4 hero preflop tendencies (baseline) --------------------------------------------
    rows = q(
        c,
        "SELECT t.scenario_label AS lbl, d.hand_id, d.position, d.street, d.action_type, d.to_call, d.big_blind,"
        " d.pot_before, d.effective_stack, m.pot_type FROM decisions d JOIN hands h ON h.hand_id=d.hand_id"
        " JOIN tournaments t ON t.tournament_id=h.tournament_id LEFT JOIN decision_metrics m ON m.decision_id=d.decision_id"
        " WHERE t.scenario_label LIKE '%|baseline|%' ORDER BY d.hand_id, d.seq_in_hand",
    )
    stats: dict[str, Counter] = defaultdict(Counter)
    first_pre: dict[tuple[str, str], tuple[str, str, str]] = {}
    for r in rows:
        cand = r["lbl"].split("|")[2]
        st = stats[cand]
        if r["street"] == "preflop":
            key = (cand, r["hand_id"])
            if key not in first_pre:
                first_pre[key] = (r["position"], r["action_type"], r["pot_type"] or "")
                st["pf_hands"] += 1
                if r["action_type"] in ("call", "raise", "bet"):
                    st["vpip"] += 1
                if r["action_type"] == "raise":
                    st["pfr"] += 1
                if r["pot_type"] == "unopened":
                    st[f"unopened_{r['position']}"] += 1
                    if r["action_type"] == "raise":
                        st[f"open_{r['position']}"] += 1
                if r["pot_type"] == "single_raised":
                    st["facing_open"] += 1
                    st[f"facing_open_{r['action_type']}"] += 1
                    if r["position"] == "BB":
                        st["bb_vs_open"] += 1
                        st[f"bb_vs_open_{r['action_type']}"] += 1
        else:
            st["post_" + r["action_type"]] += 1
    tend = {}
    for cand, st in stats.items():
        n = st["pf_hands"] or 1
        opens = {p: round(st[f"open_{p}"] / st[f"unopened_{p}"], 3) for p in ("UTG", "HJ", "CO", "BTN", "SB") if st[f"unopened_{p}"]}
        agg = st["post_bet"] + st["post_raise"]
        tend[cand] = {
            "hands_with_preflop_decision": st["pf_hands"],
            "vpip": round(st["vpip"] / n, 3),
            "pfr": round(st["pfr"] / n, 3),
            "open_rate_when_unopened_by_position": opens,
            "vs_single_open": {k.replace("facing_open_", ""): round(v / max(1, st["facing_open"]), 3) for k, v in st.items() if k.startswith("facing_open_")},
            "bb_vs_open": {k.replace("bb_vs_open_", ""): round(v / max(1, st["bb_vs_open"]), 3) for k, v in st.items() if k.startswith("bb_vs_open_")},
            "postflop_aggression_factor": round(agg / max(1, st["post_call"]), 2),
            "postflop_fold_share": round(st["post_fold"] / max(1, sum(v for k, v in st.items() if k.startswith("post_"))), 3),
        }
    rep["A4_hero_tendencies_baseline"] = tend

    # A5 loss decomposition: bb/hand by position x first preflop action -----------------
    hp = {
        (r["lbl"].split("|")[2], r["hand_id"]): (r["net_chips"] / r["big_blind"], r["showdown"])
        for r in q(
            c,
            "SELECT t.scenario_label AS lbl, hp.hand_id, hp.net_chips, h.big_blind, hp.went_to_showdown AS showdown"
            " FROM hand_players hp JOIN hands h ON h.hand_id=hp.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
            " JOIN tournament_entries e ON e.entry_id=hp.entry_id WHERE e.role='hero' AND t.scenario_label LIKE '%|baseline|%'",
        )
    }
    dec: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for (cand, hid), (pos, act, ptype) in first_pre.items():
        if (cand, hid) not in hp:
            continue
        net, _ = hp[(cand, hid)]
        cell = dec[cand][f"{pos}|{ptype}|{act}"]
        cell[0] += net
        cell[1] += 1
    decomp = {}
    for cand, cells in dec.items():
        items = sorted(cells.items(), key=lambda kv: kv[1][0])
        decomp[cand] = {
            "worst_lines_total_bb": [{"line": k, "hands": int(v[1]), "total_bb": round(v[0], 1), "bb_per_hand": round(v[0] / v[1], 3)} for k, v in items[:8]],
            "best_lines_total_bb": [{"line": k, "hands": int(v[1]), "total_bb": round(v[0], 1), "bb_per_hand": round(v[0] / v[1], 3)} for k, v in items[-5:]],
        }
    rep["A5_loss_decomposition_baseline"] = decomp

    # A6 antes present in levels where the policy is used -------------------------------
    rep["A6_antes"] = {
        "hands_with_ante_share": round(q(c, "SELECT AVG(ante > 0) FROM hands WHERE tournament_id IS NOT NULL")[0][0], 4),
        "trained_policy_decisions_with_ante": q(
            c,
            "SELECT COUNT(*) FROM decisions d JOIN hands h ON h.hand_id=d.hand_id WHERE h.ante > 0"
            " AND d.agent_info_json LIKE '%trained_policy%'",
        )[0][0],
        "trained_policy_decisions_total": q(c, "SELECT COUNT(*) FROM decisions WHERE agent_info_json LIKE '%trained_policy%'")[0][0],
    }
    (OUT / "diagnosis.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
