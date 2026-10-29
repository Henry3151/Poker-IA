"""Decision-quality monitoring with conservative, pre-defined statistical stop rules (P9-C).

Operational, experimental targets (NOT a guarantee of profitability):
- >= 75 % of *evaluable* decisions adequate; <= 25 % probable strategic errors.

Rules (validated in ``tests/lab/test_quality.py``; thresholds are computed, never hard-coded):
- window: the last <= 100 evaluable decisions (adequate or probable error). Inconclusive and
  technical-error decisions are excluded from the denominator and counted separately;
- no statistical decision before 50 evaluable decisions in the window;
- adequacy: Wilson score interval (two-sided 95 %). The target is "reached" only if n >= 50 and
  the Wilson LOWER bound >= 0.75;
- strategic stop: exact one-sided 99 % Clopper-Pearson lower bound of the error rate > 0.25,
  i.e. P(X >= k | p = 0.25) < 0.01 for k errors in the window (n = 100 -> k >= 36);
- evaluated every ``check_every`` (25) new evaluable decisions, limiting repeated looks;
- persistent deterioration: the 99 % lower bound > 0.20 at 3 consecutive evaluations;
- technical limits stop immediately, without a minimum sample (see ``TechnicalLimits``).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from math import comb, sqrt
from typing import Any

ADEQUATE = "adequada"
ERROR = "provavel_erro_estrategico"
TECHNICAL = "erro_tecnico"
INCONCLUSIVE = "inconclusiva"
LABELS = (ADEQUATE, ERROR, TECHNICAL, INCONCLUSIVE)

Z95 = 1.959963984540054


@lru_cache(maxsize=65536)
def binom_tail(n: int, k: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), exact."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return float(sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1)))


@lru_cache(maxsize=16384)
def clopper_pearson_lower(k: int, n: int, alpha: float) -> float:
    """Exact one-sided (1-alpha) lower confidence bound for a binomial proportion."""
    if n <= 0 or k <= 0:
        return 0.0
    lo, hi = 0.0, k / n
    for _ in range(100):
        mid = (lo + hi) / 2
        if binom_tail(n, k, mid) >= alpha:
            hi = mid
        else:
            lo = mid
    return hi


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


@lru_cache(maxsize=1024)
def min_errors_to_stop(n: int, limit: float = 0.25, alpha: float = 0.01) -> int:
    """Smallest k with P(X >= k | p = limit) < alpha (equivalently CP lower bound > limit)."""
    for k in range(n + 1):
        if binom_tail(n, k, limit) < alpha:
            return k
    return n + 1


@dataclass(frozen=True)
class QualityPolicy:
    window: int = 100
    min_sample: int = 50
    check_every: int = 25
    target_adequate: float = 0.75
    error_limit: float = 0.25
    stop_alpha: float = 0.01  # one-sided 99 %
    persistent_limit: float = 0.20
    persistent_checks: int = 3


@dataclass(frozen=True)
class TechnicalLimits:
    window: int = 100
    max_invalid_actions: int = 2  # requested illegal actions within the last `window` decisions
    max_agent_exceptions: int = 2
    max_consecutive_timeouts: int = 3


@dataclass
class QualityState:
    evaluable: int
    errors: int
    adequate: int
    inconclusive_total: int
    technical_total: int
    adequacy: float | None
    adequacy_ci: tuple[float, float] | None
    error_rate: float | None
    error_lower_99: float | None
    sample_ok: bool
    target_reached: bool
    stop: bool
    stop_reason: str | None
    persistent_count: int
    last_check_at: int

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class QualityMonitor:
    policy: QualityPolicy = field(default_factory=QualityPolicy)
    tech: TechnicalLimits = field(default_factory=TechnicalLimits)
    _window: deque[str] = field(default_factory=deque)
    _recent: deque[str] = field(default_factory=deque)  # all decisions' technical issues (for technical limits)
    inconclusive_total: int = 0
    technical_total: int = 0
    evaluable_total: int = 0
    _since_check: int = 0
    _persistent: int = 0
    _consecutive_timeouts: int = 0
    stopped: str | None = None
    last_state: QualityState | None = None
    _last_check_at: int = 0

    # -------------------------------------------------------------- recording
    def record(self, label: str, issue: str | None = None) -> QualityState:
        """Record one decision's assessment (and technical issue, if any). Returns the current state."""
        if label not in LABELS:
            raise ValueError(label)
        self._recent.append(issue or "")
        while len(self._recent) > self.tech.window:
            self._recent.popleft()
        self._consecutive_timeouts = self._consecutive_timeouts + 1 if issue == "timeout" else 0
        if label == INCONCLUSIVE:
            self.inconclusive_total += 1
        elif label == TECHNICAL:
            self.technical_total += 1
        else:
            self.evaluable_total += 1
            self._window.append(label)
            while len(self._window) > self.policy.window:
                self._window.popleft()
            self._since_check += 1
        if self.stopped is None:
            reason = self._technical_reason()
            if reason:
                self.stopped = reason
        state = self.state(evaluate=self._since_check >= self.policy.check_every)
        return state

    def _technical_reason(self) -> str | None:
        if sum(1 for i in self._recent if i == "invalid_action") >= self.tech.max_invalid_actions:
            return f"tecnico: {self.tech.max_invalid_actions}+ ações inválidas nas últimas {self.tech.window} decisões"
        if sum(1 for i in self._recent if i == "agent_exception") >= self.tech.max_agent_exceptions:
            return f"tecnico: {self.tech.max_agent_exceptions}+ falhas do agente nas últimas {self.tech.window} decisões"
        if self._consecutive_timeouts >= self.tech.max_consecutive_timeouts:
            return f"tecnico: {self.tech.max_consecutive_timeouts} timeouts de decisão consecutivos"
        return None

    def critical(self, reason: str) -> None:
        """Immediate stop for critical technical failures (inconsistent state, control failure)."""
        if self.stopped is None:
            self.stopped = f"critico: {reason}"

    # -------------------------------------------------------------- statistics
    def state(self, evaluate: bool = False) -> QualityState:
        p = self.policy
        n = len(self._window)
        errors = sum(1 for x in self._window if x == ERROR)
        adequate = n - errors
        sample_ok = n >= p.min_sample
        ci = wilson_interval(adequate, n) if n else None
        lower = clopper_pearson_lower(errors, n, p.stop_alpha) if n else None
        if evaluate and sample_ok and self.stopped is None:
            self._since_check = 0
            self._last_check_at = self.evaluable_total
            if lower is not None and lower > p.error_limit:
                self.stopped = (f"qualidade: taxa de erro estimada {errors}/{n} = {errors / n:.1%}; limite inferior "
                                f"99% {lower:.1%} > {p.error_limit:.0%}")
            elif lower is not None and lower > p.persistent_limit:
                self._persistent += 1
                if self._persistent >= p.persistent_checks:
                    self.stopped = (f"qualidade: piora persistente (limite inferior 99% > {p.persistent_limit:.0%} em "
                                    f"{p.persistent_checks} avaliações seguidas)")
            else:
                self._persistent = 0
        elif evaluate and not sample_ok:
            self._since_check = 0
        st = QualityState(
            evaluable=n, errors=errors, adequate=adequate,
            inconclusive_total=self.inconclusive_total, technical_total=self.technical_total,
            adequacy=adequate / n if n else None, adequacy_ci=ci,
            error_rate=errors / n if n else None, error_lower_99=lower,
            sample_ok=sample_ok, target_reached=bool(sample_ok and ci and ci[0] >= p.target_adequate),
            stop=self.stopped is not None, stop_reason=self.stopped,
            persistent_count=self._persistent, last_check_at=self._last_check_at,
        )
        self.last_state = st
        return st

    def acknowledge_and_reset_stop(self) -> None:
        """Human review done: allow resuming. The window is kept (history is not erased)."""
        self.stopped = None
        self._persistent = 0
        self._since_check = 0
