"""P9-C CLI: sim run / sessions list / sessions show."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from poker_lab.cli import app

runner = CliRunner()


def test_sim_run_and_history(tmp_path):
    db = str(tmp_path / "s.db")
    r = runner.invoke(app, ["sim", "run", "--hands", "15", "--seed", "4", "--yes", "--json", "--db", db])
    assert r.exit_code == 0, r.output
    st = json.loads(r.output)
    assert st["summary"]["hands_played"] == 15 and st["control"]["state"] == "encerrado"
    lst = json.loads(runner.invoke(app, ["sessions", "list", "--json", "--db", db]).output)
    assert lst[0]["session_id"] == st["session_id"]
    show = runner.invoke(app, ["sessions", "show", st["session_id"], "--db", db])
    assert show.exit_code == 0 and "eventos:" in show.output and "limite de mãos" in show.output
    assert runner.invoke(app, ["sessions", "show", "nao-existe", "--db", db]).exit_code == 2


def test_sim_run_rejects_bad_config(tmp_path):
    r = runner.invoke(app, ["sim", "run", "--opponents", "xyz", "--yes", "--db", str(tmp_path / "s.db")])
    assert r.exit_code == 2
