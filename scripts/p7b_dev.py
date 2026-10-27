"""P7b development-set experiments (seed root 777001; never used for final evaluation).

  python scripts/p7b_dev.py run      # full-record tournaments (field decisions included)
  python scripts/p7b_dev.py analyze  # profile stats, LAG mechanisms, equity calibration

Outputs: artifacts/p7b/dev.db, artifacts/p7b/dev_analysis.json
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from poker_lab.agents.registry import AgentSpec
from poker_lab.domain.cards import parse_card
from poker_lab.engine.evaluator import evaluate
from poker_lab.evaluation.protocol import Candidate, Protocol, Scenario, run_shard
from poker_lab.evaluation.stats import bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/p7b"
DEV_DB = OUT / "dev.db"
DEV_SEED = 777001
CKPT_P7 = ROOT / "artifacts/checkpoints/pushfold-p7.json"


def dev_protocol(n: int = 60, candidates: list[Candidate] | None = None, name: str = "p7b-dev") -> Protocol:
    return Protocol(
        name=name,
        seed=DEV_SEED,
        candidates=candidates
        or [
            Candidate(label="heuristic", spec=AgentSpec(algorithm="heuristic")),
            Candidate(label="equity", spec=AgentSpec(algorithm="equity", params={"samples": 120})),
            Candidate(
                label="pushfold_p7",
                spec=AgentSpec(algorithm="policy", version_label="p7", checkpoint_path=str(CKPT_P7), params={"fallback_samples": 120}),
                lineage="pushfold",
            ),
        ],
        scenarios=[Scenario(label="dev_mixed", field_profile="mixed", n_tournaments=n)],
        progressive_n=[n],
        min_n_claim=200,
    )


def profile_of(label: str) -> str:
    return "hero" if label == "hero" else label.split("_", 1)[1]


def analyze(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    out: dict = {}
    rows = conn.execute(
        "SELECT t.scenario_label AS lbl, d.hand_id, d.seq_in_hand, d.participant_label AS who, d.position, d.street,"
        " d.action_type, d.to_call, d.pot_before, d.big_blind, d.chips_added, d.agent_info_json, d.observation_json, d.seat"
        " FROM decisions d JOIN hands h ON h.hand_id=d.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
        " ORDER BY d.hand_id, d.seq_in_hand"
    ).fetchall()
    # ---------------------------------------------------------------- B1 profile stats
    st: dict[str, Counter] = defaultdict(Counter)
    hands_seen: dict[str, set] = defaultdict(set)
    pre_raiser: dict[str, str] = {}
    first_action: dict[tuple[str, str], bool] = {}
    by_hand: dict[str, list] = defaultdict(list)
    for r in rows:
        by_hand[r["hand_id"]].append(r)
    for hid, decs in by_hand.items():
        raises_pre = 0
        limpers = 0
        opener = None
        for r in decs:
            prof = profile_of(r["who"]) if r["who"] != "hero" else "hero:" + r["lbl"].split("|")[2]
            k = (hid, r["who"])
            s = st[prof]
            if r["street"] == "preflop":
                if k not in first_action:
                    first_action[k] = True
                    hands_seen[prof].add(hid)
                    if raises_pre == 0 and limpers == 0 and r["position"] != "BB":
                        s["unopened"] += 1
                        s[f"unopened_{r['position']}"] += 1
                        if r["action_type"] == "raise":
                            s["open"] += 1
                            s[f"open_{r['position']}"] += 1
                    if raises_pre == 1 and r["position"] in ("SB", "BB") and opener and opener[1] in ("CO", "BTN", "SB"):
                        s["blind_vs_steal"] += 1
                        s[f"blind_vs_steal_{r['action_type']}"] += 1
                if r["action_type"] in ("call", "raise", "bet") and f"vpip:{hid}" not in s:
                    s["vpip"] += 1
                    s[f"vpip:{hid}"] = 1
                if r["action_type"] == "raise":
                    if raises_pre == 0:
                        opener = (r["who"], r["position"])
                        pre_raiser[hid] = r["who"]
                    raises_pre += 1
                    if f"pfr:{hid}" not in s:
                        s["pfr"] += 1
                        s[f"pfr:{hid}"] = 1
                if r["action_type"] == "call" and raises_pre == 0:
                    limpers += 1
            else:
                s[f"post_{r['action_type']}"] += 1
                if r["street"] == "flop" and pre_raiser.get(hid) == r["who"] and r["to_call"] == 0 and f"cb:{hid}" not in s:
                    s[f"cb:{hid}"] = 1
                    s["cbet_opp"] += 1
                    if r["action_type"] == "bet":
                        s["cbet"] += 1
                if r["street"] == "flop" and r["to_call"] > 0 and f"fcb:{hid}" not in s and pre_raiser.get(hid) not in (None, r["who"]):
                    s[f"fcb:{hid}"] = 1
                    s["vs_cbet"] += 1
                    if r["action_type"] == "fold":
                        s["fold_vs_cbet"] += 1
    prof_stats = {}
    for prof, s in st.items():
        n = len(hands_seen[prof]) or 1
        post = sum(v for k, v in s.items() if k.startswith("post_"))
        prof_stats[prof] = {
            "hands": len(hands_seen[prof]),
            "vpip": round(s["vpip"] / n, 3),
            "pfr": round(s["pfr"] / n, 3),
            "open_when_unopened": round(s["open"] / max(1, s["unopened"]), 3),
            "open_by_pos": {p: round(s[f"open_{p}"] / s[f"unopened_{p}"], 3) for p in ("UTG", "HJ", "CO", "BTN", "SB") if s[f"unopened_{p}"]},
            "blind_vs_steal_fold": round(s["blind_vs_steal_fold"] / max(1, s["blind_vs_steal"]), 3),
            "blind_vs_steal_n": s["blind_vs_steal"],
            "cbet": round(s["cbet"] / max(1, s["cbet_opp"]), 3),
            "fold_vs_cbet": round(s["fold_vs_cbet"] / max(1, s["vs_cbet"]), 3),
            "postflop_af": round((s["post_bet"] + s["post_raise"]) / max(1, s["post_call"]), 2),
            "postflop_fold_share": round(s["post_fold"] / max(1, post), 3),
        }
    out["B1_profile_stats"] = prof_stats

    # ---------------------------------------------------------------- B2 results by profile & position
    res: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute(
        "SELECT t.scenario_label AS lbl, hp.participant_label AS who, hp.position, hp.net_chips, h.big_blind FROM hand_players hp"
        " JOIN hands h ON h.hand_id=hp.hand_id JOIN tournaments t ON t.tournament_id=h.tournament_id"
    ):
        prof = profile_of(r["who"]) if r["who"] != "hero" else "hero:" + r["lbl"].split("|")[2]
        res[prof][r["position"]].append(r["net_chips"] / r["big_blind"])
    out["B2_bb_per_hand_by_profile_position"] = {
        p: {pos: {"hands": len(v), "bb_per_hand": round(sum(v) / len(v), 3)} for pos, v in sorted(d.items())} for p, d in res.items()
    }

    # ---------------------------------------------------------------- B3 equity calibration (offline truth)
    holes = {
        (r["hand_id"], r["seat"]): [parse_card(x) for x in json.loads(r["hole_cards_json"])]
        for r in conn.execute("SELECT hand_id, seat, hole_cards_json FROM offline_hole_cards")
    }
    calib: dict[str, list[tuple[float, float]]] = defaultdict(list)
    rng = random.Random(1)
    for r in rows:
        if r["who"] != "hero" or r["to_call"] <= 0:
            continue
        info = json.loads(r["agent_info_json"] or "{}")
        if not isinstance(info.get("equity"), (int, float)):
            continue
        obs = json.loads(r["observation_json"])
        opp = [s["seat"] for s in obs["seats"] if not s["folded"] and s["seat"] != obs["seat"]]
        mine = list(obs["hole_cards"])
        board = list(obs["board"])
        opp_cards = [holes[(r["hand_id"], s)] for s in opp]
        dead = set(mine) | set(board) | {c for oc in opp_cards for c in oc}
        deck = [c for c in range(52) if c not in dead]
        need = 5 - len(board)
        runouts = list(combinations(deck, need)) if need <= 2 else [tuple(rng.sample(deck, need)) for _ in range(300)]
        tot = 0.0
        for ro in runouts:
            b = board + list(ro)
            me = evaluate(mine + b)
            best = max(evaluate(oc + b) for oc in opp_cards)
            tot += 1.0 if me > best else (1 / (1 + sum(1 for oc in opp_cards if evaluate(oc + b) == me)) if me == best else 0.0)
        true_eq = tot / len(runouts)
        key = f"{r['lbl'].split('|')[2]}|{r['street']}|{r['action_type']}"
        calib[key].append((float(info["equity"]), true_eq))
    cal = {}
    for k, v in sorted(calib.items()):
        if len(v) < 30:
            continue
        diffs = [a - b for a, b in v]
        ci = bootstrap_ci(diffs, seed=3, resamples=1000)
        cal[k] = {"n": len(v), "mean_estimated": round(sum(a for a, _ in v) / len(v), 3), "mean_true": round(sum(b for _, b in v) / len(v), 3), "bias": ci.as_dict()}
    out["B3_equity_calibration_when_facing_bet"] = cal
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "run":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        print(run_shard(DEV_DB, dev_protocol(n), 0, 1, log_every=30, record_level="full"))
    elif cmd == "analyze":
        conn = sqlite3.connect(f"file:{DEV_DB}?mode=ro", uri=True)
        rep = analyze(conn)
        (OUT / "dev_analysis.json").write_text(json.dumps(rep, indent=1))
        print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
