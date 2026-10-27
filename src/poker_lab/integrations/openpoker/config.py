"""Configuration and secret handling for the Open Poker adapter.

The integration is OFF unless OPEN_POKER_ENABLED=1 is set explicitly, and it needs
OPEN_POKER_API_KEY. The key is wrapped in :class:`ApiKey`, whose repr/str never reveal it,
and a logging filter masks it in any log record. Virtual chips only: this module never
calls wallet, deposit, credits or Pro endpoints.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

OFFICIAL_WS_URL = "wss://openpoker.ai/ws"  # docs.openpoker.ai, WebSocket Protocol
MIN_BUY_IN, MAX_BUY_IN = 1000, 5000  # documented join_lobby range
PLATFORM_ACTION_DEADLINE_S = 45.0  # documented public-play action deadline
MAX_MESSAGES_PER_SECOND = 20  # documented per-connection limit


class IntegrationDisabled(RuntimeError):
    pass


class ApiKey:
    """Opaque secret. Use :meth:`bearer_header` only when opening the socket."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("OPEN_POKER_API_KEY looks invalid (too short)")
        self._value = value

    def bearer_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._value}"}

    def matches(self, text: str) -> bool:
        return self._value in text

    def mask(self, text: str) -> str:
        return text.replace(self._value, "****")

    def __repr__(self) -> str:
        return "ApiKey(****)"

    __str__ = __repr__

    def __reduce__(self) -> tuple[object, ...]:  # never pickle the secret
        raise TypeError("ApiKey cannot be serialised")


class RedactingFilter(logging.Filter):
    def __init__(self, key: ApiKey) -> None:
        super().__init__()
        self._key = key

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if self._key.matches(msg):
            record.msg = self._key.mask(msg)
            record.args = None
        return True


@dataclass(frozen=True)
class OpenPokerConfig:
    api_key: ApiKey = field(repr=False)
    ws_url: str = OFFICIAL_WS_URL
    buy_in: int = 2000
    max_hands: int = 100
    decision_budget_s: float = 10.0  # well below the 45 s platform deadline
    auto_rebuy: bool = False
    max_invalid_actions: int = 3  # stop the session long before the platform flood limits
    max_reconnect_seconds: float = 100.0  # inside the documented 120 s seat-hold window
    kill_switch: Path = Path("artifacts/openpoker/STOP")
    db_path: Path = Path("artifacts/openpoker/online.db")
    messages_per_second: int = 8
    resync_timeout_s: float = 20.0  # paused without a consistent snapshot this long -> stop
    max_resync_attempts: int = 3

    def __post_init__(self) -> None:
        if not MIN_BUY_IN <= self.buy_in <= MAX_BUY_IN:
            raise ValueError(f"buy_in must be within [{MIN_BUY_IN}, {MAX_BUY_IN}] (documented range)")
        if not 0 < self.decision_budget_s < PLATFORM_ACTION_DEADLINE_S - 5:
            raise ValueError("decision budget must leave a safety margin before the 45 s deadline")
        if not 0 < self.messages_per_second < MAX_MESSAGES_PER_SECOND:
            raise ValueError("messages_per_second must stay below the documented 20/s limit")
        if self.ws_url != OFFICIAL_WS_URL and not self.ws_url.startswith(("ws://127.0.0.1", "ws://localhost")):
            raise ValueError("only the official endpoint (or a local test server) is allowed")
        if self.max_hands <= 0:
            raise ValueError("max_hands must be positive")


def load_config(env: Mapping[str, str] | None = None, **overrides: object) -> OpenPokerConfig:
    env = os.environ if env is None else env
    if env.get("OPEN_POKER_ENABLED") != "1":
        raise IntegrationDisabled("Open Poker integration is disabled (set OPEN_POKER_ENABLED=1 to enable)")
    raw = env.get("OPEN_POKER_API_KEY")
    if not raw:
        raise IntegrationDisabled("OPEN_POKER_API_KEY is not set")
    return OpenPokerConfig(api_key=ApiKey(raw), **overrides)  # type: ignore[arg-type]
