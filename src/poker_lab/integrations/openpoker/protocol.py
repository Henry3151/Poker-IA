"""Open Poker message contract (docs.openpoker.ai: Message Types / WebSocket Protocol).

Incoming messages are validated with tolerant pydantic models (unknown extra fields are
kept but ignored). Outgoing messages are built only through the helpers below.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from poker_lab.domain.cards import parse_card


class _Msg(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    table_id: str | None = None
    hand_id: str | None = None
    table_seq: int | None = None


class ValidAction(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str
    amount: int | None = None
    min: int | None = None
    max: int | None = None


class PlayerInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    seat: int
    name: str | None = None
    stack: int = 0


class Connected(_Msg):
    agent_id: str
    name: str


class TableJoined(_Msg):
    seat: int
    players: list[PlayerInfo] = Field(default_factory=list)


class Blinds(BaseModel):
    small_blind: int
    big_blind: int


class HandStart(_Msg):
    seat: int
    dealer_seat: int
    blinds: Blinds


class HoleCards(_Msg):
    cards: list[str]


class YourTurn(_Msg):
    valid_actions: list[ValidAction]
    pot: int
    community_cards: list[str] = Field(default_factory=list)
    players: list[PlayerInfo] = Field(default_factory=list)
    min_raise: int | None = None
    max_raise: int | None = None
    turn_token: str


class PlayerAction(_Msg):
    seat: int
    name: str | None = None
    action: str
    amount: int | None = None
    street: str
    stack: int | None = None
    pot: int | None = None
    stack_after: int | None = None
    contribution_delta: int | None = None


class CommunityCards(_Msg):
    cards: list[str]
    street: str


class HandResult(_Msg):
    winners: list[dict[str, Any]] = Field(default_factory=list)
    pot: int = 0
    final_stacks: dict[str, int] = Field(default_factory=dict)
    shown_cards: dict[str, list[str]] | None = None


class ActionAck(_Msg):
    client_action_id: str
    status: str


class ActionRejected(_Msg):
    code: str
    reason: str = ""


class ErrorMsg(_Msg):
    code: str
    message: str = ""


MODELS: dict[str, type[_Msg]] = {
    "connected": Connected,
    "table_joined": TableJoined,
    "hand_start": HandStart,
    "hole_cards": HoleCards,
    "your_turn": YourTurn,
    "player_action": PlayerAction,
    "community_cards": CommunityCards,
    "hand_result": HandResult,
    "action_ack": ActionAck,
    "action_rejected": ActionRejected,
    "error": ErrorMsg,
}


def parse(raw: str | bytes) -> _Msg:
    data = json.loads(raw)
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("message without type")
    model = MODELS.get(str(data["type"]), _Msg)
    return model.model_validate(data)


def card(text: str) -> int:
    """Platform card text ('Ah', 'Ts'; defensively also '10h') -> internal int."""
    t = text.strip()
    if t.startswith("10"):
        t = "T" + t[2:]
    return parse_card(t[0].upper() + t[1].lower())


# ---------------------------------------------------------------- outgoing
def join_lobby(buy_in: int) -> dict[str, Any]:
    return {"type": "join_lobby", "buy_in": int(buy_in)}


def set_auto_rebuy(enabled: bool) -> dict[str, Any]:
    return {"type": "set_auto_rebuy", "enabled": bool(enabled)}


def action(hand_id: str, kind: str, amount: int | None, client_action_id: str, turn_token: str) -> dict[str, Any]:
    if kind not in ("fold", "check", "call", "raise", "all_in"):
        raise ValueError(f"unsupported platform action {kind!r}")
    msg: dict[str, Any] = {
        "type": "action",
        "hand_id": hand_id,
        "action": kind,
        "client_action_id": client_action_id,
        "turn_token": turn_token,
    }
    if kind == "raise":
        if amount is None:
            raise ValueError("raise requires amount (raise-to total)")
        msg["amount"] = int(amount)
    return msg


def resync_request(table_id: str, last_table_seq: int) -> dict[str, Any]:
    return {"type": "resync_request", "table_id": table_id, "last_table_seq": int(last_table_seq)}


def leave_table() -> dict[str, Any]:
    return {"type": "leave_table"}
