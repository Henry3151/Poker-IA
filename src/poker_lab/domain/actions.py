"""Actions, legal-action sets and streets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any


class ActionKind(StrEnum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"


class Street(IntEnum):
    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Action:
    """An action requested by an agent.

    ``amount`` is only meaningful for BET/RAISE and is the *total* street commitment
    after the action ("raise to"), not the increment.
    """

    kind: ActionKind
    amount: int | None = None

    @staticmethod
    def fold() -> Action:
        return Action(ActionKind.FOLD)

    @staticmethod
    def check() -> Action:
        return Action(ActionKind.CHECK)

    @staticmethod
    def call() -> Action:
        return Action(ActionKind.CALL)

    @staticmethod
    def bet(to: int) -> Action:
        return Action(ActionKind.BET, to)

    @staticmethod
    def raise_to(to: int) -> Action:
        return Action(ActionKind.RAISE, to)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "amount": self.amount}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Action:
        return Action(ActionKind(d["kind"]), d.get("amount"))


@dataclass(frozen=True, slots=True)
class LegalActions:
    """Legal action set for the player to act, computed by the engine.

    - ``can_fold``: only when there is something to call.
    - ``can_check``: when nothing to call.
    - ``call_amount``: chips that a CALL adds (capped by stack; 0 when not callable).
    - ``raise_kind``: BET (no bet yet on street) or RAISE, or None when not allowed.
    - ``min_raise_to``/``max_raise_to``: inclusive bounds of total street commitment.
      ``max_raise_to`` is always the all-in amount; when the stack cannot reach a full
      raise, ``min_raise_to == max_raise_to`` (all-in only).
    """

    can_fold: bool
    can_check: bool
    call_amount: int
    raise_kind: ActionKind | None
    min_raise_to: int
    max_raise_to: int

    @property
    def can_call(self) -> bool:
        return self.call_amount > 0

    @property
    def can_raise(self) -> bool:
        return self.raise_kind is not None

    def is_legal(self, action: Action) -> bool:
        return self.why_illegal(action) is None

    def why_illegal(self, action: Action) -> str | None:
        k = action.kind
        if k is ActionKind.FOLD:
            return None if self.can_fold else "fold not allowed when check is available"
        if k is ActionKind.CHECK:
            return None if self.can_check else "cannot check facing a bet"
        if k is ActionKind.CALL:
            return None if self.can_call else "nothing to call"
        if k in (ActionKind.BET, ActionKind.RAISE):
            if self.raise_kind is None:
                return "betting/raising not allowed"
            if k is not self.raise_kind:
                return f"use {self.raise_kind.value} instead of {k.value}"
            if action.amount is None or not isinstance(action.amount, int) or isinstance(action.amount, bool):
                return "bet/raise requires an integer amount"
            if not self.min_raise_to <= action.amount <= self.max_raise_to:
                return f"amount {action.amount} outside [{self.min_raise_to}, {self.max_raise_to}]"
            return None
        return f"unknown action kind {k!r}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_fold": self.can_fold,
            "can_check": self.can_check,
            "call_amount": self.call_amount,
            "raise_kind": self.raise_kind.value if self.raise_kind else None,
            "min_raise_to": self.min_raise_to,
            "max_raise_to": self.max_raise_to,
        }

    def safe_default(self) -> Action:
        """Fallback used by the runner when an agent fails: check, else fold."""
        return Action.check() if self.can_check else Action.fold()
