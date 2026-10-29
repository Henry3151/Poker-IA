"""Command line entry point (``poker-lab``)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from poker_lab.analytics.powerbi_export import RunSource, default_sources, export_powerbi

app = typer.Typer(no_args_is_help=True, help="Poker AI Tournament Lab (simulated units only; no real money).")
export_app = typer.Typer(no_args_is_help=True, help="Exports for analytics tools.")
app.add_typer(export_app, name="export")

ROOT = Path(__file__).resolve().parents[2]


@export_app.command("powerbi")
def export_powerbi_cmd(
    out: Annotated[Path, typer.Option(help="Output folder (replaced atomically).")] = ROOT / "artifacts/powerbi/latest",
    fmt: Annotated[str, typer.Option("--format", help="parquet or csv")] = "parquet",
    run: Annotated[list[str] | None, typer.Option(help="Restrict to runs (P7, P7b, P7c). Default: all available.")] = None,
) -> None:
    """Export the star schema for Power BI; fails if any KPI does not reconcile."""
    if fmt not in ("parquet", "csv"):
        raise typer.BadParameter("format must be parquet or csv")
    sources: list[RunSource] = [s for s in default_sources(ROOT) if (not run or s.label in run) and s.db_path.exists()]
    if not sources:
        raise typer.BadParameter("no run databases found under artifacts/")
    manifest = export_powerbi(sources, out, fmt)
    typer.echo(json.dumps({"out": str(out), "files": len(manifest["files"]), "reconciliation": manifest["reconciliation"]}))


if __name__ == "__main__":
    app()
