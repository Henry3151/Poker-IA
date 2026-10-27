"""Open Poker adapter tests — simulated messages and a local fake server only (no network)."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path

import pytest

from poker_lab.agents.base import Agent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.domain.actions import Action, ActionKind
from poker_lab.domain.cards import parse_card
from poker_lab.engine.hand import HandEngine
from poker_lab.integrations.openpoker import protocol as P
from poker_lab.integrations.openpoker.client import OpenPokerSession, RateLimiter, TransportClosed
from poker_lab.integrations.openpoker.config import ApiKey, IntegrationDisabled, OpenPokerConfig, load_config
from poker_lab.integrations.openpoker.recorder import OnlineRecorder, export_jsonl
from poker_lab.integrations.openpoker.state import (
    TableTracker,
    UnsupportedState,
    legal_from_valid,
    to_platform,
)

SECRET = "opk_live_TESTSECRET_1234567890"


def cfg(tmp_path: Path, **kw) -> OpenPokerConfig:
    base = dict(api_key=ApiKey(SECRET), max_hands=2, kill_switch=tmp_path / "STOP", db_path=tmp_path / "online.db",
                decision_budget_s=2.0, messages_per_second=19)
    base.update(kw)
    return OpenPokerConfig(**base)


def m(**kw) -> str:
    return json.dumps(kw)


# ---------------------------------------------------------------- config & secrets
def test_disabled_by_default_and_requires_key():
    with pytest.raises(IntegrationDisabled):
        load_config({})
    with pytest.raises(IntegrationDisabled):
        load_config({"OPEN_POKER_ENABLED": "1"})
    c = load_config({"OPEN_POKER_ENABLED": "1", "OPEN_POKER_API_KEY": SECRET})
    assert SECRET not in repr(c) and SECRET not in str(c.api_key)
    assert c.api_key.bearer_header() == {"Authorization": f"Bearer {SECRET}"}


def test_config_guards(tmp_path):
    with pytest.raises(ValueError):
        cfg(tmp_path, buy_in=10_000)  # outside the documented 1000..5000
    with pytest.raises(ValueError):
        cfg(tmp_path, decision_budget_s=44)  # no margin before the 45 s deadline
    with pytest.raises(ValueError):
        cfg(tmp_path, ws_url="wss://evil.example/ws")
    with pytest.raises(ValueError):
        cfg(tmp_path, messages_per_second=25)
    with pytest.raises(TypeError):
        import pickle

        pickle.dumps(ApiKey(SECRET))


# ---------------------------------------------------------------- parsing & state
def test_card_parsing():
    assert P.card("Ah") == parse_card("Ah") and P.card("Ts") == parse_card("Ts") and P.card("10d") == parse_card("Td")


def build_hand(tr: TableTracker, my_seat=3, dealer=1, seats=(1, 3, 5)):
    tr.apply(P.parse(m(type="table_joined", table_id="t1", seat=my_seat, players=[{"seat": s, "name": f"bot{s}", "stack": 2000} for s in seats])))
    tr.apply(P.parse(m(type="hand_start", hand_id="h1", seat=my_seat, dealer_seat=dealer, blinds={"small_blind": 10, "big_blind": 20})))
    tr.apply(P.parse(m(type="hole_cards", cards=["Ah", "Kd"])))


def test_tracker_builds_compact_observation_with_only_own_cards():
    tr = TableTracker()
    build_hand(tr)  # seats 1 (BTN), 3 (SB), 5 (BB) -> compact 0,1,2
    tr.apply(P.parse(m(type="player_action", seat=1, name="bot1", action="raise", amount=60, street="preflop", stack=1940, pot=90)))
    turn = P.parse(m(type="your_turn", hand_id="h1", turn_token="tok1", pot=90, community_cards=[],
                     players=[{"seat": 1, "stack": 1940}, {"seat": 3, "stack": 1990}, {"seat": 5, "stack": 1980}],
                     valid_actions=[{"action": "fold"}, {"action": "call", "amount": 50}, {"action": "raise", "min": 100, "max": 2000}]))
    obs, ctx = tr.observation(turn)
    assert obs.seat == 1 and obs.position == "SB" and obs.button_seat == 0
    assert [s.position for s in obs.seats] == ["BTN", "SB", "BB"]
    assert obs.hole_cards == (parse_card("Ah"), parse_card("Kd"))
    assert obs.to_call == 50 and obs.current_bet == 60 and obs.pot == 90
    assert obs.legal.raise_kind is ActionKind.RAISE and (obs.legal.min_raise_to, obs.legal.max_raise_to) == (100, 2000)
    assert obs.history[0].kind == "raise" and obs.history[0].seat == 0 and obs.history[0].to_total == 60
    assert obs.seats[0].street_commitment == 60 and obs.seats[1].street_commitment == 10 and obs.seats[2].street_commitment == 20


def test_shown_cards_never_reach_next_observation():
    tr = TableTracker()
    build_hand(tr)
    tr.apply(P.parse(m(type="hand_result", hand_id="h1", pot=40, winners=[{"seat": 5}], final_stacks={"1": 2000, "3": 1990, "5": 2010},
                       shown_cards={"1": ["Qs", "Qh"], "5": ["2c", "2d"]})))
    assert tr.hole is None and tr.hand_id is None
    with pytest.raises(UnsupportedState):
        tr.observation(P.parse(m(type="your_turn", hand_id="h1", turn_token="x", pot=0, valid_actions=[{"action": "check"}])))
    tr.apply(P.parse(m(type="hand_start", hand_id="h2", seat=3, dealer_seat=3, blinds={"small_blind": 10, "big_blind": 20})))
    tr.apply(P.parse(m(type="hole_cards", cards=["7c", "2s"])))
    obs, _ = tr.observation(P.parse(m(type="your_turn", hand_id="h2", turn_token="y", pot=30,
                                      valid_actions=[{"action": "fold"}, {"action": "call", "amount": 20}])))
    dumped = json.dumps(obs.to_dict())
    for c in ("Qs", "Qh", "2c", "2d"):
        assert parse_card(c) not in obs.hole_cards and parse_card(c) not in obs.board
    assert "shown" not in dumped


def test_duplicate_and_regressed_messages_ignored():
    tr = TableTracker()
    assert tr.accept(P.parse(m(type="player_action", table_seq=5, seat=1, action="call", street="preflop")))
    assert not tr.accept(P.parse(m(type="player_action", table_seq=5, seat=1, action="call", street="preflop")))
    assert not tr.accept(P.parse(m(type="player_action", table_seq=3, seat=1, action="call", street="preflop")))
    assert tr.accept(P.parse(m(type="player_action", table_seq=9, seat=1, action="call", street="preflop")))  # gaps are normal
    assert tr.duplicates_ignored == 2 and tr.gaps_detected == 1  # counted for diagnostics only


def test_unsupported_states_detected():
    tr = TableTracker()
    build_hand(tr)
    with pytest.raises(UnsupportedState):
        tr.observation(P.parse(m(type="your_turn", hand_id="other", turn_token="x", pot=0, valid_actions=[{"action": "check"}])))
    with pytest.raises(UnsupportedState):
        tr.observation(P.parse(m(type="your_turn", hand_id="h1", turn_token="x", pot=0, community_cards=["Ah", "2c"],
                                 valid_actions=[{"action": "check"}])))
    with pytest.raises(UnsupportedState):
        tr.apply(P.parse(m(type="hole_cards", cards=["Ah"])))


# ---------------------------------------------------------------- legality & action mapping
def _valid(*items):
    return {v["action"]: P.ValidAction.model_validate(v) for v in items}


def test_action_mapping_raise_allin_and_short_allin_call():
    turn = P.YourTurn.model_validate({"type": "your_turn", "turn_token": "t", "pot": 30, "valid_actions": []})
    valid = _valid({"action": "fold"}, {"action": "call", "amount": 20}, {"action": "raise", "min": 40, "max": 1500}, {"action": "all_in"})
    legal, ctx = legal_from_valid(valid, my_street=0, my_stack=1980, current_bet=20, turn=turn)
    # conservative: never widen the platform range; a raise is never silently turned into an all-in
    assert legal.max_raise_to == 1500 and ctx["allin_unreachable"] is True
    assert to_platform(Action.raise_to(60), legal, ctx) == ("raise", 60)
    assert to_platform(Action.raise_to(1500), legal, ctx) == ("raise", 1500)
    with pytest.raises(ValueError):
        to_platform(Action.raise_to(1700), legal, ctx)  # above platform raise max
    assert to_platform(Action.call(), legal, ctx) == ("call", None)
    with pytest.raises(ValueError):
        to_platform(Action.raise_to(30), legal, ctx)  # below min
    with pytest.raises(ValueError):
        to_platform(Action.check(), legal, ctx)  # check not legal facing a bet
    # short all-in is offered as a call (documented)
    short = _valid({"action": "fold"}, {"action": "call", "amount": 150})
    legal2, ctx2 = legal_from_valid(short, my_street=0, my_stack=150, current_bet=400, turn=turn)
    assert legal2.raise_kind is None and legal2.call_amount == 150
    assert to_platform(Action.call(), legal2, ctx2) == ("call", None)
    with pytest.raises(ValueError):
        P.action("h", "bet", 10, "c", "t")  # 'bet' is not a platform action
    with pytest.raises(ValueError):
        P.action("h", "raise", None, "c", "t")


def test_rules_compatibility_with_internal_engine():
    """Platform model (blinds 10/20, no ante, raise-to semantics) vs. our engine on the same spot."""
    e = HandEngine([("a", 2000), ("b", 2000), ("c", 2000)], 0, 10, 20, ante=0, seed=3)
    lg = e.legal_actions(e.to_act)  # UTG/BTN first to act 3-handed
    turn = P.YourTurn.model_validate({"type": "your_turn", "turn_token": "t", "pot": 30, "valid_actions": []})
    valid = _valid({"action": "fold"}, {"action": "call", "amount": 20}, {"action": "raise", "min": lg.min_raise_to, "max": lg.max_raise_to})
    mapped, _ = legal_from_valid(valid, my_street=0, my_stack=2000, current_bet=20, turn=turn)
    assert (mapped.can_fold, mapped.can_check, mapped.call_amount, mapped.raise_kind, mapped.min_raise_to, mapped.max_raise_to) == (
        lg.can_fold, lg.can_check, lg.call_amount, lg.raise_kind, lg.min_raise_to, lg.max_raise_to)


# ---------------------------------------------------------------- fake server sessions
class FakeServer:
    """In-process scripted server implementing the documented happy path + injected faults."""

    def __init__(self, hands: int = 2, faults: set[str] | None = None) -> None:
        self.inbox: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[dict] = []
        self.hands = hands
        self.hand_no = 0
        self.seq = 0
        self.faults = faults or set()
        self.connections = 0
        self.closed_once = False

    async def connect(self):
        self.connections += 1
        srv = self
        await self.push(type="connected", agent_id="a1", name="MyBot")

        class _T:
            async def send(self, text: str) -> None:
                await srv.on_client(json.loads(text))

            async def recv(self) -> str:
                item = await srv.inbox.get()
                if item == "__CLOSE__":
                    raise TransportClosed("1006")
                return item

            async def close(self) -> None:
                pass

        return _T()

    async def push(self, seq: bool = False, **kw):
        if seq:
            self.seq += 1
            kw["table_seq"] = self.seq
        await self.inbox.put(json.dumps(kw))

    async def deal(self):
        self.hand_no += 1
        hid = f"h{self.hand_no}"
        await self.push(seq=True, type="hand_start", table_id="T", hand_id=hid, seat=2, dealer_seat=2, blinds={"small_blind": 10, "big_blind": 20})
        await self.push(seq=True, type="hole_cards", table_id="T", hand_id=hid, cards=["As", "Ad"])
        turn = dict(type="your_turn", table_id="T", hand_id=hid, turn_token=f"tok{self.hand_no}", pot=30, community_cards=[],
                    players=[{"seat": 2, "name": "MyBot", "stack": 1990}, {"seat": 4, "name": "opp", "stack": 1980}],
                    valid_actions=[{"action": "fold"}, {"action": "call", "amount": 10}, {"action": "raise", "min": 40, "max": 2000}])
        await self.push(seq=True, **turn)
        if "dup_turn" in self.faults:
            await self.push(**turn)  # repeated your_turn without seq: must not create a second decision

    async def on_client(self, msg: dict):
        self.sent.append(msg)
        t = msg["type"]
        if t == "join_lobby":
            await self.push(type="lobby_joined", position=1, estimated_wait=0)
            await self.push(seq=True, type="table_joined", table_id="T", seat=2,
                            players=[{"seat": 2, "name": "MyBot", "stack": 2000}, {"seat": 4, "name": "opp", "stack": 2000}])
            await self.deal()
        elif t == "action":
            if "reject_first" in self.faults and self.hand_no == 1 and not any(x.get("_rej") for x in self.sent):
                msg["_rej"] = True
                await self.push(type="action_rejected", code="invalid_action", reason="test")
                return
            await self.push(type="action_ack", client_action_id=msg["client_action_id"], status="accepted")
            if "disconnect" in self.faults and not self.closed_once:
                self.closed_once = True
                await self.inbox.put("__CLOSE__")
                return
            await self.finish()
        elif t == "resync_request":
            await self.push(type="resync_response", to_table_seq=self.seq, replayed_events=[], snapshot={})
            await self.finish()
        elif t == "leave_table":
            await self.push(type="table_closed", reason="left")

    async def finish(self):
        hid = f"h{self.hand_no}"
        await self.push(seq=True, type="player_action", table_id="T", hand_id=hid, seat=4, name="opp", action="fold", street="preflop", stack=1980)
        await self.push(seq=True, type="hand_result", table_id="T", hand_id=hid, pot=30, winners=[{"seat": 2}],
                        final_stacks={"2": 2000 + 20 * self.hand_no, "4": 2000 - 20 * self.hand_no})
        if self.hand_no < self.hands + 5:
            await self.deal()


def run_session(tmp_path, agent=None, faults=None, **kw):
    srv = FakeServer(faults=faults)
    c = cfg(tmp_path, **kw)
    rec = OnlineRecorder(c.db_path, "test-agent", {"k": "v"})
    sess = OpenPokerSession(c, agent or RandomAgent("r", seed=1), srv.connect, rec)
    stats = asyncio.run(asyncio.wait_for(sess.run(), timeout=20))
    return srv, stats, rec


def test_happy_path_session_legal_idempotent_and_recorded(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    srv, stats, rec = run_session(tmp_path)
    types = [x["type"] for x in srv.sent]
    assert types[:2] == ["join_lobby", "set_auto_rebuy"] and srv.sent[0]["buy_in"] == 2000 and srv.sent[1]["enabled"] is False
    actions = [x for x in srv.sent if x["type"] == "action"]
    assert len(actions) == 2 and all(a["turn_token"].startswith("tok") and a["client_action_id"] for a in actions)
    assert all(a["action"] in ("fold", "check", "call", "raise", "all_in") for a in actions)
    assert stats.hands_completed == 2 and stats.stop_reason == "max_hands" and types[-1] == "leave_table"
    db = sqlite3.connect(tmp_path / "online.db")
    assert db.execute("SELECT COUNT(*) FROM online_decisions").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM online_hands WHERE end_stack IS NOT NULL").fetchone()[0] == 2
    assert db.execute("SELECT money FROM online_sessions").fetchone()[0] == "virtual_chips"
    # the secret appears nowhere: messages, logs, database file
    assert all(SECRET not in json.dumps(x) for x in srv.sent)
    assert SECRET not in caplog.text
    assert SECRET.encode() not in (tmp_path / "online.db").read_bytes()
    out = export_jsonl(tmp_path / "online.db", tmp_path / "export")
    assert out["online_decisions"] == 2


def test_duplicate_turn_resends_same_payload(tmp_path):
    srv, stats, _ = run_session(tmp_path, faults={"dup_turn"})
    actions = [x for x in srv.sent if x["type"] == "action"]
    by_token: dict[str, list[dict]] = {}
    for a in actions:
        by_token.setdefault(a["turn_token"], []).append(a)
    assert stats.decisions == 2  # one decision per turn token
    for lst in by_token.values():
        assert all(x == lst[0] for x in lst)  # identical payload incl. client_action_id (safe retry)


def test_rejection_counts_and_stops_before_flood(tmp_path):
    srv, stats, _ = run_session(tmp_path, faults={"reject_first"}, max_invalid_actions=1)
    assert stats.rejected.get("invalid_action") == 1
    assert stats.stop_reason == "too_many_invalid_actions"
    assert srv.sent[-1]["type"] == "leave_table"


def test_disconnect_reconnects_and_resyncs(tmp_path):
    srv, stats, _ = run_session(tmp_path, faults={"disconnect"})
    assert srv.connections == 2 and stats.reconnects == 1
    resync = [x for x in srv.sent if x["type"] == "resync_request"]
    assert resync and resync[0]["table_id"] == "T" and resync[0]["last_table_seq"] > 0
    assert stats.hands_completed == 2


class SlowAgent(Agent):
    algorithm = "slow"

    def act(self, obs):
        import time

        time.sleep(1.5)
        return Action.raise_to(obs.legal.min_raise_to)


def test_decision_timeout_uses_safe_fallback(tmp_path):
    srv, stats, _ = run_session(tmp_path, agent=SlowAgent("s"), decision_budget_s=0.2)
    actions = [x for x in srv.sent if x["type"] == "action"]
    assert stats.timeouts == 2 and stats.fallbacks == 2
    assert all(a["action"] == "fold" for a in actions)  # facing the BB: fold (check not legal)


class IllegalAgent(Agent):
    algorithm = "illegal"

    def act(self, obs):
        return Action.raise_to(10**9)


def test_illegal_internal_action_never_sent(tmp_path):
    srv, stats, _ = run_session(tmp_path, agent=IllegalAgent("x"))
    assert all(a["action"] in ("fold", "check") for a in srv.sent if a["type"] == "action")
    assert stats.fallbacks == 2


def test_kill_switch_stops_immediately(tmp_path):
    (tmp_path / "STOP").write_text("stop")
    srv, stats, _ = run_session(tmp_path)
    assert stats.stop_reason == "kill_switch" and not [x for x in srv.sent if x["type"] == "action"]


def test_rate_limiter_spacing():
    t = [0.0]
    rl = RateLimiter(10, clock=lambda: t[0])

    async def go():
        slept = []
        orig = asyncio.sleep

        async def fake_sleep(d):
            slept.append(d)
            t[0] += d
            await orig(0)

        asyncio.sleep = fake_sleep  # type: ignore[assignment]
        try:
            for _ in range(5):
                await rl.wait()
        finally:
            asyncio.sleep = orig  # type: ignore[assignment]
        return slept

    slept = asyncio.run(go())
    assert len(slept) == 4 and all(abs(s - 0.1) < 1e-9 for s in slept)


def test_adapter_does_not_reference_money_endpoints_or_gui_automation():
    import ast

    literals: list[str] = []
    imports: list[str] = []
    for f in Path("src/poker_lab/integrations/openpoker").glob("*.py"):
        tree = ast.parse(f.read_text())
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                literals.append(node.value.lower())
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports += [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
    for forbidden in ("wallet", "deposit", "withdraw", "/api/", "credits", "regenerate-key", "premium"):
        assert not any(forbidden in lit for lit in literals), forbidden
    for mod in ("selenium", "pyautogui", "playwright", "pynput"):
        assert not any(i and i.startswith(mod) for i in imports)
