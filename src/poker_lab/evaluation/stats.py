"""Statistics for evaluation: bootstrap confidence intervals, drawdown, sample-size flags.

Bootstrap: percentile method, resampling *independent units* (whole tournaments, or
seed-paired tournament pairs), with a fixed seed so results are reproducible. Percentile
bootstrap CIs are approximate and can under-cover for heavy-tailed data with small n
(MTT results are heavy-tailed: most entries lose the buy-in, few win large prizes).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

MIN_N_FOR_CLAIM = 200  # below this many independent tournaments, never claim an edge
MIN_N_FOR_BUCKET = 100  # below this many hands/decisions a breakdown bucket is flagged


@dataclass(frozen=True, slots=True)
class CI:
    estimate: float
    low: float
    high: float
    n: int
    level: float
    method: str = "percentile_bootstrap"

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimate": round(self.estimate, 6),
            "ci_low": round(self.low, 6),
            "ci_high": round(self.high, 6),
            "n": self.n,
            "level": self.level,
            "method": self.method,
        }


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(
    data: Sequence[float],
    stat: Callable[[Sequence[float]], float] = mean,
    *,
    level: float = 0.95,
    resamples: int = 2000,
    seed: int = 0,
) -> CI:
    n = len(data)
    if n == 0:
        return CI(float("nan"), float("nan"), float("nan"), 0, level)
    est = stat(data)
    if n == 1:
        return CI(est, float("nan"), float("nan"), 1, level)
    rng = random.Random(seed)
    vals = sorted(stat([data[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples))
    a = (1 - level) / 2
    lo = vals[max(0, int(math.floor(a * resamples)))]
    hi = vals[min(resamples - 1, int(math.ceil((1 - a) * resamples)) - 1)]
    return CI(est, lo, hi, n, level)


def ratio_bootstrap_ci(
    num: Sequence[float], den: Sequence[float], *, level: float = 0.95, resamples: int = 2000, seed: int = 0
) -> CI:
    """CI for sum(num)/sum(den) resampling paired units (e.g. aggregate ROI = net/cost)."""
    n = len(num)
    if n == 0 or n != len(den):
        return CI(float("nan"), float("nan"), float("nan"), n, level)
    est = sum(num) / sum(den) if sum(den) else float("nan")
    rng = random.Random(seed)
    vals = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        d = sum(den[i] for i in idx)
        vals.append(sum(num[i] for i in idx) / d if d else 0.0)
    vals.sort()
    a = (1 - level) / 2
    return CI(est, vals[int(math.floor(a * resamples))], vals[int(math.ceil((1 - a) * resamples)) - 1], n, level)


def max_drawdown(series: Sequence[float]) -> dict[str, float]:
    """Max peak-to-trough decline of the cumulative sum of ``series`` (in the same units)."""
    peak = 0.0
    cum = 0.0
    mdd = 0.0
    trough_at = -1
    for i, x in enumerate(series):
        cum += x
        peak = max(peak, cum)
        if peak - cum > mdd:
            mdd = peak - cum
            trough_at = i
    return {"max_drawdown": mdd, "final_cumulative": cum, "trough_index": trough_at}


def quantiles(xs: Sequence[float], qs: Sequence[float] = (0.05, 0.25, 0.5, 0.75, 0.95)) -> dict[str, float]:
    if not xs:
        return {}
    s = sorted(xs)
    out = {}
    for q in qs:
        pos = q * (len(s) - 1)
        lo, hi = int(math.floor(pos)), int(math.ceil(pos))
        out[f"p{int(q * 100)}"] = s[lo] + (s[hi] - s[lo]) * (pos - lo)
    return out


def verdict(ci: CI, *, min_n: int = MIN_N_FOR_CLAIM, null: float = 0.0) -> str:
    """Conservative reading of an effect estimate.

    - ``insufficient_sample``: n < min_n, no claim either way.
    - ``evidence_positive`` / ``evidence_negative``: the whole CI is above / below ``null``.
    - ``inconclusive``: the CI contains ``null``.
    Even ``evidence_positive`` is evidence *in this simulated setting only*, never proof of
    real-money profitability.
    """
    if ci.n < min_n or math.isnan(ci.low):
        return "insufficient_sample"
    if ci.low > null:
        return "evidence_positive"
    if ci.high < null:
        return "evidence_negative"
    return "inconclusive"
