"""P11 reinforced criteria: turn-token binding, pause-until-snapshot, state_hash, pot
reconciliation, exhaustive valid_actions <-> internal conversion, invariance to hidden info,
and separation of the cash policy from the MTT champion. Local fake server only, no network."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poker_lab.agents.heuristic import HeuristicAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.domain.actions import Action, ActionKind
from poker_lab.domain.observation import Observation
from poker_lab.integrations.openpoker import protocol as P
from poker_lab.integrations.openpoker.client import OpenPokerSession
from poker_lab.integrations.openpoker.policy import CASH_POLICY_LABEL, CashGamePolicy, cash_policy_spec
from poker_lab.integrations.openpoker.state import (
    StateDivergence,
    TableTracker,
    UnsupportedState,
    compute_state_hash,
    legal_from_valid,
    reconcile_pot,
    state_hash_ok,
    to_platform,
)

from .test_openpoker import FakeServer, _valid, cfg, m

HID = "h1"


def snapshot(token: str | None, hand_no: int = 1) -> dict:
    hero = {"seat": 2, "hole_cards": ["As", "Ad"]}
    if token:
        hero |= {"turn_token": token,
                 "valid_actions": [{"action": "fold"}, {"action": "call", "amount": 10}, {"action": "raise", "min": 40, "max": 2000}]}
    return {"hand_id": f"h{hand_no}", "dealer_seat": 2, "small_blind": 10, "big_blind": 20, "street": "preflop", "board": [],
            "pot": 30, "seats": [{"seat": 2, "name": "MyBot", "stack": 1990, "bet": 10, "in_hand": True, "folded": False},
                                 {"seat": 4, "name": "opp", "stack": 1980, "bet": 20, "in_hand": True, "folded": False}],
            "hero": hero}


class SafetyServer(FakeServer):
    """Adds the documented failure modes to the scripted server."""

    def __init__(self, faults: set[str]) -> None:
        super().__init__(hands=2, faults=faults)
        self.resyncs = 0

    async def deal(self):
        if self.hand_no == 0 and self.faults & {"bad_hash", "good_hash", "pot_mismatch", "wrong_hand"}:
            self.hand_no = 1
            await self.push(seq=True, type="hand_start", table_id="T", hand_id=HID, seat=2, dealer_seat=2,
                            blinds={"small_blind": 10, "big_blind": 20})
            await self.push(seq=True, type="hole_cards", table_id="T", hand_id=HID, cards=["As", "Ad"])
            turn = dict(type="your_turn", table_id="T", hand_id=HID, turn_token="tok1", pot=30, community_cards=[],
                        players=[{"seat": 2, "name": "MyBot", "stack": 1990}, {"seat": 4, "name": "opp", "stack": 1980}],
                        valid_actions=[{"action": "fold"}, {"action": "call", "amount": 10}, {"action": "raise", "min": 40, "max": 2000}])
            if "pot_mismatch" in self.faults:
                turn["pot"] = 999
            if "wrong_hand" in self.faults:
                turn["hand_id"] = "h-other"
            if "bad_hash" in self.faults:
                turn["state_hash"] = "sha256:" + "0" * 64
            if "good_hash" in self.faults:
                turn["state_hash"] = compute_state_hash(turn)
            await self.push(seq=True, **turn)
            return
        await super().deal()

    async def on_client(self, msg: dict):
        t = msg["type"]
        if t == "action" and self.faults & {"drop_same_token", "drop_new_token"} and not self.closed_once:
            self.sent.append(msg)
            self.closed_once = True  # connection dies before any ack: outcome unknown to the client
            await self.inbox.put("__CLOSE__")
            return
        if t == "action" and "stale_then_repeat" in self.faults and self.hand_no == 1 and not any(x.get("_st") for x in self.sent):
            msg["_st"] = True
            self.sent.append(msg)
            await self.push(type="action_rejected", code="stale_turn_token", reason="test")
            await self.push(type="your_turn", table_id="T", hand_id=HID, turn_token="tok1", pot=30,  # same dead token again
                            players=[], valid_actions=[{"action": "fold"}, {"action": "call", "amount": 10}])
            await self.finish()
            return
        if t == "action" and "event_then_repeat" in self.faults and self.hand_no == 1 and not any(x.get("_ev") for x in self.sent):
            msg["_ev"] = True
            self.sent.append(msg)
            await self.push(seq=True, type="player_joined", table_id="T", seat=5, name="late", stack=2000)  # newer table event
            await self.push(type="your_turn", table_id="T", hand_id=HID, turn_token="tok1", pot=30,
                            players=[], valid_actions=[{"action": "fold"}, {"action": "call", "amount": 10}])
            return
        if t == "action" and "protocol_bug" in self.faults:
            self.sent.append(msg)
            await self.push(type="action_rejected", code="action_id_conflict", reason="test")
            return
        if t == "resync_request":
            self.sent.append(msg)
            self.resyncs += 1
            if "resync_never" in self.faults:
                return
            if self.faults & {"drop_same_token", "drop_new_token"}:
                token = "tok1" if "drop_same_token" in self.faults else "tok1-new"
                await self.push(type="resync_response", table_id="T", to_table_seq=self.seq, replayed_events=[], snapshot=snapshot(token))
                return
            if self.faults & {"bad_hash", "pot_mismatch", "wrong_hand", "event_then_repeat"}:
                # authoritative snapshot: the hand is still h1 and hero still holds the (unanswered) token
                await self.push(type="resync_response", table_id="T", to_table_seq=self.seq, replayed_events=[],
                                snapshot=snapshot(None))
                await self.finish()
                return
        await super().on_client(msg)


def run(tmp_path: Path, faults: set[str], agent=None, **kw):
    srv = SafetyServer(faults)
    c = cfg(tmp_path, **kw)
    sess = OpenPokerSession(c, agent or RandomAgent("r", seed=3), srv.connect, None)
    stats = asyncio.run(asyncio.wait_for(sess.run(), timeout=20))
    return srv, stats, sess


def actions(srv) -> list[dict]:
    return [x for x in srv.sent if x["type"] == "action"]


# ---------------------------------------------------------------- turn-token binding & idempotency
def test_each_action_bound_to_its_token_and_stable_id(tmp_path):
    srv, stats, _ = run(tmp_path, set())
    acts = actions(srv)
    assert [a["turn_token"] for a in acts] == ["tok1", "tok2"]
    assert len({a["client_action_id"] for a in acts}) == 2 and all(a["hand_id"] == f"h{i + 1}" for i, a in enumerate(acts))


def test_reconnect_resends_identical_payload_only_for_same_token(tmp_path):
    srv, stats, _ = run(tmp_path, {"drop_same_token"})
    tok1 = [a for a in actions(srv) if a["turn_token"] == "tok1"]
    assert len(tok1) == 2 and tok1[0] == tok1[1]  # same client_action_id + same payload: dedupe-safe
    assert stats.resends == 1 and stats.decisions == 2 and stats.reconnects == 1 and stats.hands_completed == 2


def test_reconnect_with_new_token_drops_old_action(tmp_path):
    srv, stats, _ = run(tmp_path, {"drop_new_token"})
    acts = actions(srv)
    assert sum(a["turn_token"] == "tok1" for a in acts) == 1  # never resent
    new = [a for a in acts if a["turn_token"] == "tok1-new"]
    assert len(new) == 1 and new[0]["client_action_id"] != acts[0]["client_action_id"]
    assert stats.pending_dropped == 1 and stats.resends == 0


def test_rejected_token_is_never_reused(tmp_path):
    srv, stats, _ = run(tmp_path, {"stale_then_repeat"})
    assert sum(a["turn_token"] == "tok1" for a in actions(srv)) == 1
    assert stats.rejected == {"stale_turn_token": 1} and stats.resends == 0


def test_repeat_after_newer_table_event_is_not_resent(tmp_path):
    srv, stats, _ = run(tmp_path, {"event_then_repeat"})
    assert sum(a["turn_token"] == "tok1" for a in actions(srv)) == 1
    assert stats.pending_dropped == 1 and stats.resyncs_requested >= 1 and stats.resends == 0


def test_protocol_bug_rejection_stops_session(tmp_path):
    srv, stats, _ = run(tmp_path, {"protocol_bug"})
    assert stats.stop_reason == "protocol_error:action_id_conflict" and srv.sent[-1]["type"] == "leave_table"
    assert len(actions(srv)) == 1


# ---------------------------------------------------------------- pause until a consistent snapshot
@pytest.mark.parametrize("fault,counter", [("bad_hash", "hash_mismatches"), ("pot_mismatch", "divergences"),
                                           ("wrong_hand", "divergences")])
def test_divergence_pauses_and_sends_nothing_for_that_turn(tmp_path, fault, counter):
    srv, stats, _ = run(tmp_path, {fault})
    assert not [a for a in actions(srv) if a["turn_token"] == "tok1"]  # server's own deadline action applies
    assert getattr(stats, counter) == 1 and stats.pauses >= 1 and srv.resyncs >= 1
    assert [a["turn_token"] for a in actions(srv)] == ["tok2"]  # resumes only after the snapshot
    assert stats.hands_completed == 2


def test_valid_state_hash_is_accepted(tmp_path):
    srv, stats, _ = run(tmp_path, {"good_hash"})
    assert stats.hash_mismatches == 0 and stats.pauses == 0
    assert [a["turn_token"] for a in actions(srv)] == ["tok1", "tok2"]


def test_unrecovered_divergence_stops_the_session(tmp_path):
    srv, stats, _ = run(tmp_path, {"pot_mismatch", "resync_never"}, resync_timeout_s=0.1, max_resync_attempts=2)
    assert stats.stop_reason == "reconciliation_failed" and not actions(srv) and srv.sent[-1]["type"] == "leave_table"
    assert srv.resyncs == 2


def test_state_hash_algorithm_matches_documentation():
    msg = {"type": "table_state", "table_seq": 7, "hand_seq": 2, "ts": "x", "b": 1, "a": {"z": "é", "y": [1, 2]}}
    expected = "sha256:" + __import__("hashlib").sha256(
        json.dumps({"a": {"y": [1, 2], "z": "é"}, "b": 1, "type": "table_state"}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    assert compute_state_hash(msg) == expected
    assert state_hash_ok(msg | {"state_hash": expected}) and not state_hash_ok(msg | {"state_hash": "sha256:00"})
    assert state_hash_ok(msg)  # no hash -> nothing to verify


def test_pot_reconciliation_conventions():
    assert reconcile_pot(30, 30, 30) == "incl_street"
    assert reconcile_pot(0, 30, 30) == "excl_street"
    assert reconcile_pot(31, 30, 30) is None


# ---------------------------------------------------------------- exhaustive valid_actions <-> internal
TURN = P.YourTurn.model_validate({"type": "your_turn", "turn_token": "t", "pot": 30, "valid_actions": []})


@pytest.mark.parametrize(
    "items,street,stack,bet,expect",
    [
        # check-only (BB option without raise rights is impossible, but a check-only set must work)
        ([{"action": "check"}], 20, 500, 20, dict(can_check=True, can_fold=False, call=0, kind=None)),
        # check or bet: opening is 'raise' on the platform, BET internally
        ([{"action": "check"}, {"action": "raise", "min": 20, "max": 500}, {"action": "all_in"}], 0, 500, 0,
         dict(can_check=True, can_fold=False, call=0, kind=ActionKind.BET, rng=(20, 500))),
        # fold/call only (no raise rights: short all-in does not reopen)
        ([{"action": "fold"}, {"action": "call", "amount": 80}], 0, 900, 400,
         dict(can_check=False, can_fold=True, call=80, kind=None)),
        # short all-in reported as call: capped by stack
        ([{"action": "fold"}, {"action": "call", "amount": 150}], 0, 150, 400,
         dict(can_check=False, can_fold=True, call=150, kind=None)),
        # call larger than stack (platform reports full amount): capped
        ([{"action": "fold"}, {"action": "call", "amount": 400}], 0, 150, 400,
         dict(can_check=False, can_fold=True, call=150, kind=None)),
        # min == max raise
        ([{"action": "fold"}, {"action": "call", "amount": 20}, {"action": "raise", "min": 300, "max": 300}], 0, 300, 20,
         dict(can_fold=True, call=20, kind=ActionKind.RAISE, rng=(300, 300))),
        # all_in only (stack cannot make a full raise)
        ([{"action": "fold"}, {"action": "call", "amount": 20}, {"action": "all_in"}], 0, 35, 20,
         dict(can_fold=True, call=20, kind=ActionKind.RAISE, rng=(35, 35))),
        # capped max (e.g. covered opponents / limited): range not widened to all-in
        ([{"action": "fold"}, {"action": "call", "amount": 20}, {"action": "raise", "min": 40, "max": 120}], 0, 1980, 20,
         dict(can_fold=True, call=20, kind=ActionKind.RAISE, rng=(40, 120))),
        # fold only
        ([{"action": "fold"}], 0, 100, 400, dict(can_check=False, can_fold=True, call=0, kind=None)),
    ],
)
def test_valid_actions_table(items, street, stack, bet, expect):
    legal, ctx = legal_from_valid(_valid(*items), street, stack, bet, TURN)
    assert legal.can_check == expect.get("can_check", False)
    assert legal.can_fold == expect.get("can_fold", False)
    assert legal.call_amount == expect["call"]
    assert legal.raise_kind is expect["kind"]
    if "rng" in expect:
        assert (legal.min_raise_to, legal.max_raise_to) == expect["rng"]


@pytest.mark.parametrize(
    "items,street,stack,bet",
    [
        ([], 0, 100, 0),  # no actions at all
        ([{"action": "bet", "min": 20, "max": 100}], 0, 100, 0),  # 'bet' does not exist on the platform
        ([{"action": "fold"}, {"action": "call", "amount": 0}], 0, 100, 20),  # zero call
        ([{"action": "raise", "min": 500, "max": 100}], 0, 1000, 20),  # inverted bounds
        ([{"action": "raise", "min": 20, "max": 5000}], 0, 1000, 0),  # max above our all-in total
        ([{"action": "fold"}, {"action": "raise", "min": 10, "max": 20}], 0, 1000, 20),  # raise-to not above bet
    ],
)
def test_inconsistent_valid_actions_are_unsupported(items, street, stack, bet):
    with pytest.raises((UnsupportedState, ValueError)):
        legal_from_valid({v["action"]: P.ValidAction.model_validate(v) for v in items}, street, stack, bet, TURN)


def test_raise_above_platform_max_without_all_in_is_error():
    legal, ctx = legal_from_valid(_valid({"action": "fold"}, {"action": "call", "amount": 20},
                                         {"action": "raise", "min": 40, "max": 120}), 0, 1980, 20, TURN)
    with pytest.raises(ValueError):
        to_platform(Action.raise_to(121), legal, ctx)
    with pytest.raises(ValueError):
        to_platform(Action.raise_to(1980), legal, ctx)  # no all_in offered: never invented
    assert to_platform(Action.raise_to(120), legal, ctx) == ("raise", 120)


def test_all_in_mapping_requires_exact_total():
    legal, ctx = legal_from_valid(_valid({"action": "fold"}, {"action": "call", "amount": 20},
                                         {"action": "raise", "min": 40, "max": 1980}, {"action": "all_in"}), 0, 1980, 20, TURN)
    assert to_platform(Action.raise_to(1980), legal, ctx) == ("all_in", None)
    assert to_platform(Action.raise_to(1979), legal, ctx) == ("raise", 1979)


@st.composite
def platform_spots(draw):
    stack = draw(st.integers(1, 5000))
    street = draw(st.integers(0, 400))
    facing = draw(st.booleans())
    items: list[dict] = []
    current_bet = 0
    if facing:
        call = draw(st.integers(1, 2000))
        current_bet = street + call
        items += [{"action": "fold"}, {"action": "call", "amount": call}]
    else:
        current_bet = street
        items.append({"action": "check"})
    allin_total = street + stack
    if allin_total > current_bet and draw(st.booleans()):
        lo = draw(st.integers(current_bet + 1, allin_total))
        hi = draw(st.integers(lo, allin_total))
        items.append({"action": "raise", "min": lo, "max": hi})
    if allin_total > current_bet and draw(st.booleans()):
        items.append({"action": "all_in"})
    return items, street, stack, current_bet


@settings(max_examples=400, deadline=None)
@given(platform_spots(), st.integers(0, 6000), st.sampled_from(list(ActionKind)))
def test_property_conversion_never_leaves_platform_set(spot, amount, kind):
    items, street, stack, bet = spot
    valid = _valid(*items)
    try:
        legal, ctx = legal_from_valid(valid, street, stack, bet, TURN)
    except UnsupportedState:
        return
    action = Action(kind, amount if kind in (ActionKind.BET, ActionKind.RAISE) else None)
    try:
        out, amt = to_platform(action, legal, ctx)
    except ValueError:
        assert not legal.is_legal(action) or kind in (ActionKind.BET, ActionKind.RAISE)
        return
    assert legal.is_legal(action)
    assert out in valid  # never an action the platform did not offer
    if out == "raise":
        assert valid["raise"].min <= amt <= valid["raise"].max and amt == amount  # exact, never clamped
    else:
        assert amt is None
    if out == "all_in":
        assert amount == street + stack
    # the safe default is always convertible
    assert to_platform(legal.safe_default(), legal, ctx)[0] in valid


# ---------------------------------------------------------------- invariance to hidden / future info
def _stream(shown: dict, opp_extra: dict) -> list[str]:
    msgs = [
        m(type="table_joined", table_id="t1", seat=3, players=[{"seat": s, "name": f"bot{s}", "stack": 2000} for s in (1, 3, 5)]),
        m(type="hand_start", hand_id="h1", seat=3, dealer_seat=1, blinds={"small_blind": 10, "big_blind": 20}),
        m(type="hole_cards", cards=["9h", "9d"]),
        m(type="player_action", seat=1, name="bot1", action="fold", street="preflop", stack=2000, **opp_extra),
        m(type="hand_result", hand_id="h1", pot=40, winners=[{"seat": 5}], final_stacks={"1": 2000, "3": 1990, "5": 2010},
          shown_cards=shown, **opp_extra),
        m(type="hand_start", hand_id="h2", seat=3, dealer_seat=3, blinds={"small_blind": 10, "big_blind": 20}),
        m(type="hole_cards", cards=["Ah", "Qc"]),
        m(type="player_action", seat=1, name="bot1", action="raise", amount=60, street="preflop", stack=1940, **opp_extra),
    ]
    return msgs


TURN2 = m(type="your_turn", hand_id="h2", turn_token="tk", pot=70, community_cards=[],
          players=[{"seat": 1, "stack": 1940}, {"seat": 3, "stack": 1990}, {"seat": 5, "stack": 1990}],
          valid_actions=[{"action": "fold"}, {"action": "call", "amount": 50}, {"action": "raise", "min": 100, "max": 1990}, {"action": "all_in"}])


def _obs_for(stream: list[str]) -> Observation:
    tr = TableTracker()
    for raw in stream:
        tr.apply(P.parse(raw))
    obs, _ = tr.observation(P.parse(TURN2))
    return obs


@pytest.mark.parametrize("variant", [
    ({"1": ["Ks", "Kh"]}, {}),
    ({"5": ["2c", "7d"], "1": ["As", "Ad"]}, {}),
    ({}, {"hole_cards": ["Kc", "Kd"], "cards": ["Qs", "Qd"], "equity": 0.99, "next_card": "Jh"}),
])
def test_observation_and_action_invariant_to_hidden_and_future_info(variant):
    base = _obs_for(_stream({}, {}))
    other = _obs_for(_stream(*variant))
    assert base.to_dict() == other.to_dict()
    for seed in range(5):
        a = HeuristicAgent("h", seed=seed).act(base)
        b = HeuristicAgent("h", seed=seed).act(other)
        assert a == b


def test_snapshot_cards_of_others_never_enter_observation():
    tr = TableTracker()
    snap = snapshot("tk")
    snap["seats"][1]["hole_cards"] = ["Kc", "Kd"]  # a malformed/leaky snapshot
    snap["deck"] = ["2c", "3c"]
    tr.table_id = "T"
    tr.install_snapshot(copy.deepcopy(snap), "h1")
    obs, _ = tr.observation(P.parse(m(type="your_turn", hand_id="h1", turn_token="tk", pot=30,
                                      valid_actions=snap["hero"]["valid_actions"])))
    dumped = json.dumps(obs.to_dict())
    assert "Kc" not in dumped and "Kd" not in dumped
    from poker_lab.domain.cards import parse_card
    assert set(obs.hole_cards) == {parse_card("As"), parse_card("Ad")} and obs.board == ()


def test_divergent_turn_raises_divergence_not_fallback():
    tr = TableTracker()
    with pytest.raises(StateDivergence):
        tr.observation(P.parse(m(type="your_turn", hand_id="h1", turn_token="x", pot=0, valid_actions=[{"action": "check"}])))


# ---------------------------------------------------------------- cash policy separated from the MTT champion
class _Echo(RandomAgent):
    pass


def test_cash_policy_is_separate_from_mtt_champion():
    spec = cash_policy_spec()
    assert spec.version_label == CASH_POLICY_LABEL != "hybrid-v1"
    assert spec.params["icm"] is False
    wrapped = CashGamePolicy(_Echo("e", seed=1))
    obs = _obs_for(_stream({}, {}))
    assert wrapped.act(obs).kind in set(ActionKind)
    with pytest.raises(ValueError):
        wrapped.act(__import__("dataclasses").replace(obs, ante=5))


def test_run_module_does_not_use_mtt_champion():
    src = (Path(__file__).resolve().parents[2] / "src/poker_lab/integrations/openpoker/run.py").read_text()
    assert "hybrid-v1\"" not in src and "create_cash_policy" in src
