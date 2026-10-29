"""P9-B CLI: read-only commands, JSON output, exit codes, protected output folders."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import poker_lab.cli as cli

runner = CliRunner()


@pytest.fixture()
def root(lab_root, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", lab_root)
    return lab_root


def test_runs_list_show_compare(root):
    before = (root / "artifacts/p7c/final.db").read_bytes()
    r = runner.invoke(cli.app, ["runs", "list", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert {k["key"] for k in data["known"]} == {"P7", "P7b", "P7c"}
    r = runner.invoke(cli.app, ["runs", "show", "P7c"])
    assert r.exit_code == 0 and "heuristic" in r.stdout and "ROI do champion" in r.stdout
    r = runner.invoke(cli.app, ["runs", "compare", "P7c", "--json"])
    assert r.exit_code == 0 and json.loads(r.stdout)["compare"][0]["candidate"] == "equity"
    assert runner.invoke(cli.app, ["runs", "compare", "P7c", "--scenario", "nope"]).exit_code == 2
    assert runner.invoke(cli.app, ["runs", "show", "P99"]).exit_code == 2
    assert (root / "artifacts/p7c/final.db").read_bytes() == before


def test_verify_exit_codes(root):
    assert runner.invoke(cli.app, ["verify"]).exit_code == 2
    r = runner.invoke(cli.app, ["verify", "P7c", "--frozen", "--json"])
    assert r.exit_code == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["frozen"]["passed"] and out["P7c"]["ok"]
    (root / "artifacts/checkpoints/model.json").write_text("tampered")
    assert runner.invoke(cli.app, ["verify", "--frozen"]).exit_code == 1
    assert runner.invoke(cli.app, ["verify", "P7"]).exit_code == 1  # database absent


def test_info_and_config(root):
    r = runner.invoke(cli.app, ["info", "--json"])
    assert r.exit_code == 0 and json.loads(r.stdout)["online"]["enabled"] is False
    r = runner.invoke(cli.app, ["config", "show", "--json"])
    assert r.exit_code == 0 and json.loads(r.stdout)["simulation"]["concurrent_jobs"] == 1


@pytest.mark.parametrize("target", ["artifacts/p7c/out", "docs/x", "artifacts/checkpoints"])
def test_export_refuses_protected_folders(root, target):
    r = runner.invoke(cli.app, ["export", "powerbi", "--out", str(root / target)])
    assert r.exit_code == 2 and not (root / target / "manifest.json").exists()


def test_help_lists_commands():
    r = runner.invoke(cli.app, ["--help"])
    for cmd in ("info", "ui", "runs", "verify", "config", "export", "doctor"):
        assert cmd in r.stdout
