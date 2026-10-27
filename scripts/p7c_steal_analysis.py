"""When does stealing stop paying, and how does the hero respond to resistance? (P7c final DB, read-only)

Per scenario x candidate (hero only):
- late-position first-in opportunities (CO/BTN/SB, unopened & unlimped), open (steal) rate;
- steal outcome: share won immediately (everyone folded preflop) and net bb per steal hand,
  with a cluster-bootstrap CI over tournaments;
- response after a steal is re-raised: fold / call / 4-bet shares and net bb in those hands;
- open rate in the first vs second half of each tournament's hands (adaptation over time).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from poker_lab.evaluation.report import cluster_ratio_ci

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "artifacts/p7c/final.db"


def main() -> None:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    hand_info = {
        r["hand_id"]: (r["final_street"], r["hand_number"], r["tournament_id"])
        for r in c.execute("SELECT hand_id, final_street, hand_number, tournament_id FROM hands")
    }
    hero_net = {
        r["hand_id"]: r["net_chips"] / r["big_blind"]
        for r in c.execute(
            "SELECT hp.hand_id, hp.net_chips, h.big_blind FROM hand_players hp JOIN hands h ON h.hand_id=hp.hand_id"
            " JOIN tournament_entries e ON e.entry_id=hp.entry_id WHERE e.role='hero'"
        )
    }
    span = {r[0]: (r[1], r[2]) for r in c.execute("SELECT tournament_id, MIN(hand_number), MAX(hand_number) FROM hands GROUP BY tournament_id")}
    rows = c.execute(
        "SELECT t.scenario_label AS lbl, d.hand_id, d.seq_in_hand, d.position, d.action_type, d.observation_json,"
        " d.action_amount, d.big_blind, d.effective_stack, h.ante, d.agent_info_json"
        " FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
        " WHERE d.participant_label='hero' AND d.street='preflop' ORDER BY d.hand_id, d.seq_in_hand"
    )
    acc: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "opps": 0, "steals": 0, "won_pre": 0, "steal_clusters": defaultdict(lambda: [0.0, 0]),
        "resteal": defaultdict(int), "resteal_net": [], "half": {0: [0, 0], 1: [0, 0]},
        "dims": defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0]))),  # dim -> key -> tid -> [net, n]
        "fold_dims": defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0.0, 0]))),
    })
    stole: dict[str, bool] = {}
    for r in rows:
        _, scen, cand = r["lbl"].split("|")
        a = acc[(scen, cand)]
        obs = json.loads(r["observation_json"])
        pre = [x for x in obs["history"] if x["street"] == "preflop"]
        my_prev = [x for x in pre if x["seat"] == obs["seat"]]
        if not my_prev:
            unopened = not any(x["kind"] in ("raise", "call") for x in pre)
            if unopened and r["position"] in ("CO", "BTN", "SB"):
                a["opps"] += 1
                fs, hn, tid = hand_info[r["hand_id"]]
                lo, hi = span[tid]
                half = 0 if hn <= (lo + hi) / 2 else 1
                a["half"][half][0] += 1
                bb = r["big_blind"]
                eff = r["effective_stack"] / bb
                blinds = [x["player_id"] for x in obs["seats"] if x["position"] in ("SB", "BB") and x["seat"] != obs["seat"]]
                profs = {b.split("_", 1)[1] if "_" in b else b for b in blinds}
                dclass = ("adaptive" if any(q.startswith("adaptive") for q in profs)
                          else "aggressive" if profs & {"lag", "maniac", "bluffer40", "bluffer60"}
                          else "self_or_versions" if profs & {"hybrid-v1", "p7", "v2-ante", "equity"} else "static_tight")
                keys = {
                    "position": r["position"],
                    "eff_stack": "<10bb" if eff < 10 else "10-20bb" if eff < 20 else "20-40bb" if eff < 40 else "40bb+",
                    "ante": "ante" if r["ante"] else "no_ante",
                    "defender_class": dclass,
                }
                net_h = hero_net.get(r["hand_id"], 0.0)
                tgt = a["dims"] if r["action_type"] == "raise" else a["fold_dims"]
                if r["action_type"] == "raise":
                    amt = (r["action_amount"] or 0) / bb
                    keys["open_size"] = "<=2.5bb" if amt <= 2.5 else "2.5-5bb" if amt <= 5 else "shove/large"
                for dim, key in keys.items():
                    cell = tgt[dim][key][tid]
                    cell[0] += net_h
                    cell[1] += 1
                if r["action_type"] == "raise":
                    a["steals"] += 1
                    a["half"][half][1] += 1
                    stole[r["hand_id"]] = True
                    net = hero_net.get(r["hand_id"], 0.0)
                    cl = a["steal_clusters"][tid]
                    cl[0] += net
                    cl[1] += 1
                    if fs == "preflop" and net > 0:
                        a["won_pre"] += 1
        elif stole.get(r["hand_id"]) and any(x["kind"] == "raise" and x["seat"] != obs["seat"] for x in pre):
            a["resteal"][r["action_type"]] += 1
            a["resteal_net"].append(hero_net.get(r["hand_id"], 0.0))
            stole[r["hand_id"]] = False  # count only the first response
    out: dict = {}
    for (scen, cand), a in sorted(acc.items()):
        ci = cluster_ratio_ci([tuple(v) for v in a["steal_clusters"].values()], seed=1, resamples=1000)
        n_rs = sum(a["resteal"].values())
        out.setdefault(scen, {})[cand] = {
            "late_first_in_opps": a["opps"],
            "steal_rate": round(a["steals"] / max(1, a["opps"]), 3),
            "steal_won_immediately": round(a["won_pre"] / max(1, a["steals"]), 3),
            "steal_hands": a["steals"],
            "steal_net_bb_per_hand": ci.as_dict(),
            "resteal_faced": n_rs,
            "resteal_response": {k: round(v / max(1, n_rs), 3) for k, v in a["resteal"].items()},
            "resteal_hands_net_bb_mean": round(sum(a["resteal_net"]) / max(1, len(a["resteal_net"])), 3),
            "steal_rate_first_half": round(a["half"][0][1] / max(1, a["half"][0][0]), 3),
            "steal_rate_second_half": round(a["half"][1][1] / max(1, a["half"][1][0]), 3),
            "by_dimension_steal_net_bb": {
                dim: {k: {**cluster_ratio_ci([tuple(v) for v in tids.values()], seed=2, resamples=500).as_dict()}
                      for k, tids in sorted(keys.items())}
                for dim, keys in a["dims"].items()
            },
            "by_dimension_not_open_net_bb": {
                dim: {k: round(sum(v[0] for v in tids.values()) / max(1, sum(v[1] for v in tids.values())), 3)
                      for k, tids in sorted(keys.items())}
                for dim, keys in a["fold_dims"].items()
            },
            "ev_per_opportunity_open_line_bb": round(sum(v[0] for v in a["steal_clusters"].values()) / max(1, a["opps"]), 4),
        }
    (ROOT / "artifacts/p7c/steal_analysis.json").write_text(json.dumps(out, indent=1))
    for scen, d in out.items():
        for cand, v in d.items():
            s = v["steal_net_bb_per_hand"]
            print(f"{scen:16} {cand:22} steal={v['steal_rate']:.3f} won_pre={v['steal_won_immediately']:.3f} "
                  f"net/steal={s['estimate']:+.2f} [{s['ci_low']:+.2f},{s['ci_high']:+.2f}] n={v['steal_hands']} "
                  f"vs3bet={v['resteal_response']} ({v['resteal_faced']}) halves={v['steal_rate_first_half']}/{v['steal_rate_second_half']}")


if __name__ == "__main__":
    main()
