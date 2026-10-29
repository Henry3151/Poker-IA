"""P9-D: session decision analysis (read-only, decision-time only, recommendations never change the policy)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from poker_lab.cli import app
from poker_lab.lab.analysis import MIN_EXPERIMENT_N, analyze_session, render_markdown
from poker_lab.lab.assessment import Assessment
from poker_lab.lab.quality import ERROR, QualityMonitor, QualityPolicy
from poker_lab.lab.session import SimConfig, SimulationSession
from poker_lab.lab.store import SessionStore

ROOT = Path(__file__).resolve().parents[2]


class FixedError:
    """Every decision is a probable error in the same spot with the same chosen/best actions."""

    name = "stub"

    def assess(self, obs, chosen):  # noqa: ANN001
        return Assessment(ERROR, "stub", "sb_first_in: XX · push vs melhor fold · diferença -1.00 bb", spot="sb_first_in",
                          ev_chosen_bb=-2.0, ev_best_bb=-1.0, ev_gap_bb=-1.0, best_action="fold", confidence="média")


@pytest.fixture(scope="module")
def session_db(tmp_path_factory):
    db = tmp_path_factory.mktemp("an") / "s.db"
    st = SessionStore(db)
    s = SimulationSession(ROOT, st, SimConfig(hands=120, seed=17))
    s.start()
    s.join(120)
    yield st, s.session_id
    st.close()


def test_analysis_counts_are_consistent(session_db):
    st, sid = session_db
    a = analyze_session(st, sid)
    assert a is not None and sum(a["labels"].values()) == a["decisions"]
    assert a["coverage"]["n"] == a["decisions"]
    ev = a["adequacy"]["n"]
    assert ev == a["labels"].get("adequada", 0) + a["labels"].get("provavel_erro_estrategico", 0)
    gaps = [w["ev_gap_bb"] for w in a["worst_decisions"]]
    assert gaps == sorted(gaps)
    md = render_markdown(a)
    assert "Análise da sessão" in md and "nunca entra" in md
    assert analyze_session(st, "nao-existe") is None


def test_analysis_never_uses_hand_outcomes(session_db):
    st, sid = session_db
    before = analyze_session(st, sid)
    st.write("UPDATE hands SET net_bb = -net_bb, showdown = 1 - COALESCE(showdown, 0) WHERE session_id=?", (sid,))
    st.write("DELETE FROM revealed WHERE hand_id IN (SELECT hand_id FROM hands WHERE session_id=?)", (sid,))
    after = analyze_session(st, sid)
    for k in ("labels", "adequacy", "error_rate", "coverage", "worst_decisions", "patterns", "recommendations", "by_position"):
        assert before[k] == after[k], k


def test_recommendations_need_sample_and_are_only_hypotheses(tmp_path):
    st = SessionStore(tmp_path / "s.db")
    s = SimulationSession(ROOT, st, SimConfig(hands=400, seed=2))
    s.reference = FixedError()  # type: ignore[assignment]
    s.quality = QualityMonitor(policy=QualityPolicy(min_sample=10_000))  # keep the stub from stopping the session
    s.start()
    s.join(120)
    a = analyze_session(st, s.session_id)
    assert a is not None and a["recommendations"]
    for r in a["recommendations"]:
        assert r["status"] in ("propor experimento", "observar (amostra pequena)")
        assert (r["status"] == "propor experimento") == (r["evidence"]["n"] >= MIN_EXPERIMENT_N)
        assert "champion/challenger" in r["next_step"] or "acumular" in r["next_step"]
    st.close()


def test_cli_analyze_writes_report_and_refuses_frozen(session_db, tmp_path):
    st, sid = session_db
    runner = CliRunner()
    out = tmp_path / "rel"
    r = runner.invoke(app, ["sessions", "analyze", sid, "--db", str(st.path), "--out", str(out), "--json"])
    assert r.exit_code == 0, r.output
    assert (out / f"sessao_{sid}.md").exists() and json.loads((out / f"sessao_{sid}.json").read_text("utf-8"))["session_id"] == sid
    bad = runner.invoke(app, ["sessions", "analyze", sid, "--db", str(st.path), "--out", str(ROOT / "artifacts/p7c/x")])
    assert bad.exit_code != 0
