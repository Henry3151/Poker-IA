"""Quality-control statistics and stop rules (P9-C). Every threshold is computed and checked here."""

from __future__ import annotations

import random

import pytest

from poker_lab.lab.quality import (
    ADEQUATE,
    ERROR,
    INCONCLUSIVE,
    TECHNICAL,
    QualityMonitor,
    binom_tail,
    clopper_pearson_lower,
    min_errors_to_stop,
    wilson_interval,
)


def test_exact_threshold_for_100_decisions_is_36_not_37():
    """The plan's example said ~37; exact math gives 36 (correction documented)."""
    assert min_errors_to_stop(100) == 36
    assert binom_tail(100, 36, 0.25) < 0.01 <= binom_tail(100, 35, 0.25)
    assert clopper_pearson_lower(36, 100, 0.01) > 0.25 > clopper_pearson_lower(35, 100, 0.01)
    assert clopper_pearson_lower(37, 100, 0.01) > 0.25  # 37 errors also stops (a fortiori)


@pytest.mark.parametrize("n,k", [(50, 21), (75, 29), (100, 36)])
def test_threshold_table(n, k):
    assert min_errors_to_stop(n) == k
    assert binom_tail(n, k, 0.25) < 0.01 <= binom_tail(n, k - 1, 0.25)


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(80, 100)
    assert round(lo, 4) == 0.7112 and round(hi, 4) == 0.8666  # standard Wilson 95% for 80/100
    assert wilson_interval(0, 0) == (0.0, 1.0)


def _feed(m: QualityMonitor, labels):
    st = None
    for lab in labels:
        st = m.record(lab)
    return st


def test_small_sample_never_decides():
    m = QualityMonitor()
    st = _feed(m, [ERROR] * 49)
    assert not st.stop and not st.sample_ok and not st.target_reached


def test_agent_with_80_percent_adequate_is_not_stopped_and_target_reported_only_with_confidence():
    rng = random.Random(7)
    m = QualityMonitor()
    for _ in range(1000):
        st = m.record(ADEQUATE if rng.random() < 0.80 else ERROR)
        assert not st.stop
    assert st.sample_ok and st.adequacy_ci is not None
    assert st.target_reached == (st.adequacy_ci[0] >= 0.75)


def test_persistently_bad_agent_is_stopped():
    rng = random.Random(11)
    m = QualityMonitor()
    stopped_at = None
    for i in range(1000):
        st = m.record(ERROR if rng.random() < 0.40 else ADEQUATE)
        if st.stop:
            stopped_at = i + 1
            break
    assert stopped_at is not None and stopped_at >= 50 and "qualidade" in st.stop_reason


def test_stop_rule_when_window_has_36_errors_out_of_100():
    m = QualityMonitor()
    st = _feed(m, [ADEQUATE] * 64 + [ERROR] * 36)  # 100 evaluable; checks at 25/50/75/100
    assert st.stop and "36/100" in st.stop_reason


def test_35_errors_out_of_100_does_not_trigger_the_main_rule():
    m = QualityMonitor()
    st = _feed(m, [ADEQUATE] * 65 + [ERROR] * 35)
    assert not st.stop or "persistente" in (st.stop_reason or "")


def test_inconclusive_and_technical_are_excluded_from_denominator():
    m = QualityMonitor()
    st = _feed(m, [INCONCLUSIVE] * 500 + [ADEQUATE] * 10)
    assert st.evaluable == 10 and st.inconclusive_total == 500 and not st.sample_ok
    st = m.record(TECHNICAL, issue="timeout")
    assert st.evaluable == 10 and st.technical_total == 1


def test_persistent_deterioration_rule():
    """Lower bound above 20 % (but not above 25 %) at 3 consecutive checks suspends autonomy."""
    m = QualityMonitor()
    block = [ERROR] * 8 + [ADEQUATE] * 17  # 32 % errors per 25-decision block
    for _ in range(2):
        st = _feed(m, block)
    states = []
    for _ in range(6):
        st = _feed(m, block)
        states.append(st)
        if st.stop:
            break
    assert st.stop and ("persistente" in st.stop_reason or "qualidade" in st.stop_reason)
    assert any(s.persistent_count >= 1 for s in states)


@pytest.mark.parametrize("issue,count", [("invalid_action", 2), ("agent_exception", 2)])
def test_technical_limits_stop_immediately_without_minimum_sample(issue, count):
    m = QualityMonitor()
    st = None
    for _ in range(count):
        st = m.record(TECHNICAL, issue=issue)
    assert st.stop and st.stop_reason.startswith("tecnico") and st.evaluable == 0


def test_consecutive_timeouts_stop():
    m = QualityMonitor()
    m.record(TECHNICAL, issue="timeout")
    m.record(ADEQUATE)
    m.record(TECHNICAL, issue="timeout")
    assert not m.state().stop
    m.record(TECHNICAL, issue="timeout")
    st = m.record(TECHNICAL, issue="timeout")
    assert st.stop and "timeouts" in st.stop_reason


def test_critical_failure_and_human_acknowledgement():
    m = QualityMonitor()
    m.critical("estado inconsistente")
    assert m.state().stop and m.state().stop_reason.startswith("critico")
    m.acknowledge_and_reset_stop()
    assert not m.state().stop


@pytest.mark.parametrize("p,max_rate", [(0.10, 0.0), (0.20, 0.05)])
def test_operating_characteristics_false_stops(p, max_rate):
    """Seeded simulation of 400 evaluable decisions x 400 sessions (documented in docs/P9_PLANO.md)."""
    assert _stop_rate(p) <= max_rate


def test_operating_characteristics_power():
    assert _stop_rate(0.35) >= 0.95


def _stop_rate(p: float, n: int = 400, reps: int = 400) -> float:
    rng = random.Random(1)
    stops = 0
    for _ in range(reps):
        m = QualityMonitor()
        for _ in range(n):
            if m.record(ERROR if rng.random() < p else ADEQUATE).stop:
                stops += 1
                break
    return stops / reps
