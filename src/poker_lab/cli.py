"""Command line entry point (``poker-lab``).

Read-only by default: every query/verification command opens databases in read-only mode and
never touches frozen reports, checkpoints or seeds. Commands that write (``export``) only write
to their own output folder and refuse frozen locations. Exit codes: 0 ok, 1 verification
failed, 2 usage error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from poker_lab.analytics.powerbi_export import RunSource, default_sources, export_powerbi
from poker_lab.lab import config as cfg
from poker_lab.lab.frozen import MANIFEST, verify_manifest
from poker_lab.lab.health import check_all, environment
from poker_lab.lab.integrity import verify_run
from poker_lab.lab.registry import KNOWN_RUNS, discover_databases, get_run, load_report, run_overview
from poker_lab.lab.summary import compare_table, run_summary, scenario_table

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="Poker AI Tournament Lab — laboratório local (unidades simuladas; sem dinheiro real).")
runs_app = typer.Typer(no_args_is_help=True, help="Consultar avaliações registradas (somente leitura).")
export_app = typer.Typer(no_args_is_help=True, help="Exportações para ferramentas de análise.")
config_app = typer.Typer(no_args_is_help=True, help="Limites e parâmetros (sem segredos).")
app.add_typer(runs_app, name="runs")
app.add_typer(export_app, name="export")
app.add_typer(config_app, name="config")
sim_app = typer.Typer(no_args_is_help=True, help="Sessões autônomas de simulação local (sem conexão online).")
sessions_app = typer.Typer(no_args_is_help=True, help="Histórico das sessões locais e mãos (somente leitura).")
app.add_typer(sim_app, name="sim")
app.add_typer(sessions_app, name="sessions")

ROOT = Path(__file__).resolve().parents[2]
FROZEN_DIRS = ("artifacts/p7", "artifacts/p7b", "artifacts/p7c", "artifacts/checkpoints", "artifacts/tables", "docs", "src")

JsonOpt = Annotated[bool, typer.Option("--json", help="Saída em JSON (para scripts).")]


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _emit(obj: Any, as_json: bool, render: Any) -> None:
    if as_json:
        typer.echo(json.dumps(obj, ensure_ascii=False, indent=1, default=str))
    else:
        render(obj)


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:+.1f}%"


def _table(rows: list[list[str]], header: list[str]) -> None:
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    typer.echo("  ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)))
    typer.echo("  ".join("-" * w for w in widths))
    for r in rows:
        typer.echo("  ".join(str(c).ljust(w) for c, w in zip(r, widths, strict=True)))


def _known(key: str) -> Any:
    try:
        return get_run(key)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


# ------------------------------------------------------------------ info / ui
@app.command()
def info(as_json: JsonOpt = False) -> None:
    """Ambiente, champion atual, execuções e estado dos artefatos congelados."""
    _utf8()
    h = check_all(ROOT)

    def render(h: dict[str, Any]) -> None:
        env = h["environment"]
        typer.echo(f"Python {env['python']} ({'ok' if env['python_ok'] else 'precisa 3.12+'}) · {env['platform']}")
        typer.echo("Dependências: " + ", ".join(f"{k} {v or 'AUSENTE'}" for k, v in env["dependencies"].items()))
        f = h["frozen"]
        typer.echo(f"Artefatos congelados: {'íntegros' if f.get('passed') else 'DIVERGÊNCIA'} ({f.get('checked', 0)} arquivos)")
        for r in h["runs"]:
            if "error" in r:
                typer.echo(f"  {r['key']}: erro {r['error']}")
                continue
            dec = ", ".join(f"{k}: {v}" for k, v in r.get("decisions", {}).items()) or "—"
            db = f"{r['tournaments']} torneios" if r["db_present"] else "banco ausente nesta máquina"
            typer.echo(f"  {r['key']:4s} seed {r['seed']} · {db} (esperado {r.get('expected_tournaments')}) · decisões: {dec}")
        typer.echo(f"Disco livre: {h['disk_free_gb']} GB · Integração online: desativada (etapa E)")

    _emit(h, as_json, render)
    raise typer.Exit(0 if h["ok"] else 1)


@app.command()
def ui(
    port: Annotated[int, typer.Option(help="Porta preferida em 127.0.0.1.")] = 8765,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Não abrir o navegador.")] = False,
) -> None:
    """Abre a interface local no navegador (servidor só em 127.0.0.1)."""
    from poker_lab.api.launch import main as launch_main

    raise typer.Exit(launch_main(["--port", str(port), *(["--no-browser"] if no_browser else [])]))


# ------------------------------------------------------------------ runs
@runs_app.command("list")
def runs_list(as_json: JsonOpt = False) -> None:
    """Avaliações registradas e bancos encontrados em artifacts/."""
    _utf8()
    data = {"known": [run_overview(r, ROOT) for r in KNOWN_RUNS], "databases": discover_databases(ROOT)}

    def render(d: dict[str, Any]) -> None:
        _table([[r["key"], str(r["seed"]), str(r["tournaments"] if r["db_present"] else "—"), str(r.get("expected_tournaments")),
                 r.get("primary_scenario", "—"), "presente" if r["db_present"] else "ausente"] for r in d["known"]],
               ["execução", "seed", "torneios", "esperado", "cenário principal", "banco"])
        typer.echo("")
        _table([[x["path"], str(x["size_mb"]), str(x.get("schema_version", "?")), "sim" if x["frozen"] else "não"] for x in d["databases"]],
               ["banco", "MB", "schema", "congelado"])

    _emit(data, as_json, render)


@runs_app.command("show")
def runs_show(run: Annotated[str, typer.Argument(help="P7, P7b ou P7c")], as_json: JsonOpt = False) -> None:
    """Resumo de uma avaliação, lido do relatório congelado."""
    _utf8()
    r = _known(run)
    s = {"key": r.key, **run_summary(load_report(r, ROOT))}

    def render(s: dict[str, Any]) -> None:
        typer.echo(f"{s['key']} · seed {s['seed']} · cenário principal: {s['primary_scenario']} · champion: {s['baseline']}")
        typer.echo(f"ROI do champion: {_pct(s['baseline_roi'])} [{_pct(s['baseline_roi_low'])}; {_pct(s['baseline_roi_high'])}]")
        for k, v in s["decisions"].items():
            typer.echo(f"  decisão {k}: {v['decision']} ({v['reason']})")
        typer.echo("")
        _table([[x["candidate"], str(x["n"]), _pct(x["roi"]), f"[{_pct(x['roi_low'])}; {_pct(x['roi_high'])}]", x["verdict"]]
                for x in s["table"]], ["agente", "n", "ROI", "IC 95%", "veredito"])

    _emit(s, as_json, render)


@runs_app.command("compare")
def runs_compare(
    run: Annotated[str, typer.Argument(help="P7, P7b ou P7c")],
    scenario: Annotated[str | None, typer.Option(help="Cenário (padrão: o principal).")] = None,
    as_json: JsonOpt = False,
) -> None:
    """Diferenças pareadas contra o champion da execução (IC 95%, p Holm, relevância δ = 0,10)."""
    _utf8()
    r = _known(run)
    rep = load_report(r, ROOT)
    scen = scenario or run_summary(rep)["primary_scenario"]
    if scen not in rep["scenarios"]:
        typer.echo(f"cenário inexistente: {scen} (disponíveis: {', '.join(rep['scenarios'])})", err=True)
        raise typer.Exit(2)
    data = {"run": r.key, "scenario": scen, "table": scenario_table(rep, scen), "compare": compare_table(rep, scen)}

    def render(d: dict[str, Any]) -> None:
        typer.echo(f"{d['run']} · {d['scenario']} · diferença pareada em buy-ins por torneio (desafiante − champion)")
        _table([[x["candidate"], f"{x['diff']:+.3f}", f"[{x['low']:+.3f}; {x['high']:+.3f}]", str(x["n"]),
                 "—" if x["p_holm"] is None else f"{x['p_holm']:.4f}", x["relevance"], x["decision"] or "—"] for x in d["compare"]],
               ["agente", "diferença", "IC 95%", "n", "p Holm", "relevância", "decisão"])

    _emit(data, as_json, render)


# ------------------------------------------------------------------ verify
@app.command()
def verify(
    run: Annotated[str | None, typer.Argument(help="P7, P7b ou P7c (integridade completa do banco)")] = None,
    all_runs: Annotated[bool, typer.Option("--all", help="Verificar todas as execuções presentes.")] = False,
    frozen: Annotated[bool, typer.Option("--frozen", help="Conferir os artefatos congelados (FROZEN.sha256).")] = False,
    quick_check: Annotated[bool, typer.Option("--quick-check", help="Inclui PRAGMA quick_check (lento em bancos grandes).")] = False,
    as_json: JsonOpt = False,
) -> None:
    """Verifica integridade (somente leitura). Sai com código 1 se algo não conferir."""
    _utf8()
    if not (run or all_runs or frozen):
        typer.echo("informe uma execução, --all ou --frozen", err=True)
        raise typer.Exit(2)
    results: dict[str, Any] = {}
    ok = True
    if frozen:
        if not (ROOT / MANIFEST).is_file():
            typer.echo(f"{MANIFEST} ausente", err=True)
            raise typer.Exit(1)
        fr = verify_manifest(ROOT).as_dict()
        results["frozen"] = fr
        ok = ok and bool(fr["passed"])
    targets = [r for r in KNOWN_RUNS if r.db_path(ROOT).is_file()] if all_runs else ([_known(run)] if run else [])
    for r in targets:
        if not r.db_path(ROOT).is_file():
            typer.echo(f"{r.key}: banco ausente ({r.db})", err=True)
            raise typer.Exit(1)
        def say(msg: str, key: str = r.key) -> None:
            typer.echo(f"  [{key}] {msg}", err=True)

        res = verify_run(r.db_path(ROOT), load_report(r, ROOT), quick_check=quick_check, progress=None if as_json else say)
        results[r.key] = res
        ok = ok and bool(res["ok"])

    def render(d: dict[str, Any]) -> None:
        for k, v in d.items():
            if k == "frozen":
                typer.echo(f"Artefatos congelados: {'íntegros' if v['passed'] else 'DIVERGÊNCIA'} ({v['checked']} arquivos)")
                for f in v["changed"] + v["missing"]:
                    typer.echo(f"  ALTERADO/AUSENTE: {f}")
            else:
                typer.echo(f"{k}: {'INTEGRIDADE CONFIRMADA' if v['ok'] else 'PROBLEMAS ENCONTRADOS'}")
                for name, c in v["checks"].items():
                    typer.echo(f"  {'OK   ' if c['ok'] else 'FALHA'} {name}")

    _emit(results, as_json, render)
    raise typer.Exit(0 if ok else 1)


# ------------------------------------------------------------------ config
@config_app.command("show")
def config_show(as_json: JsonOpt = False) -> None:
    """Mostra os limites atuais (arquivo artifacts/lab/config.json; padrão se não existir)."""
    _utf8()
    s = cfg.load_settings(ROOT).model_dump()
    _emit(s, as_json, lambda d: typer.echo(json.dumps(d, ensure_ascii=False, indent=1)))


@config_app.command("path")
def config_path() -> None:
    """Caminho do arquivo de configuração."""
    typer.echo(str(cfg.settings_path(ROOT)))


# ------------------------------------------------------------------ export
def _inside_frozen(out: Path) -> bool:
    try:
        rel = out.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return False
    return any(rel == d or rel.startswith(d + "/") for d in FROZEN_DIRS)


@export_app.command("powerbi")
def export_powerbi_cmd(
    out: Annotated[Path, typer.Option(help="Pasta de saída (substituída de forma atômica).")] = ROOT / "artifacts/powerbi/latest",
    fmt: Annotated[str, typer.Option("--format", help="parquet ou csv")] = "parquet",
    run: Annotated[list[str] | None, typer.Option(help="Restringir a execuções (P7, P7b, P7c). Padrão: todas presentes.")] = None,
) -> None:
    """Exporta o modelo estrela para o Power BI; recusa publicar se algum KPI não reconciliar."""
    if fmt not in ("parquet", "csv"):
        raise typer.BadParameter("format deve ser parquet ou csv")
    if _inside_frozen(out):
        raise typer.BadParameter(f"pasta protegida (resultados congelados): {out}")
    sources: list[RunSource] = [s for s in default_sources(ROOT) if (not run or s.label in run) and s.db_path.exists()]
    if not sources:
        raise typer.BadParameter("nenhum banco de execução encontrado em artifacts/")
    manifest = export_powerbi(sources, out, fmt)
    typer.echo(json.dumps({"out": str(out), "files": len(manifest["files"]), "reconciliation": manifest["reconciliation"]}))


# ------------------------------------------------------------------ local simulation (P9-C)
DbOpt = Annotated[Path | None, typer.Option("--db", help="Banco de sessões (padrão: artifacts/lab/sessions.db).")]


def _manager(db: Path | None) -> Any:
    from poker_lab.lab.manager import SessionManager

    return SessionManager(ROOT, db)


@sim_app.command("run")
def sim_run(
    hands: Annotated[int, typer.Option(help="Número de mãos.")] = 500,
    seed: Annotated[int, typer.Option(help="Seed (reprodutível).")] = 1,
    stack_bb: Annotated[float, typer.Option("--stack-bb", help="Stack inicial em big blinds.")] = 15.0,
    ante_bb: Annotated[float, typer.Option("--ante-bb", help="Ante em big blinds.")] = 0.0,
    opponents: Annotated[str, typer.Option(help="Perfis separados por vírgula (até 5).")] = "tag,lag,nit,station,adaptive_tag",
    max_minutes: Annotated[int, typer.Option("--max-minutes", help="Limite de duração.")] = 60,
    yes: Annotated[bool, typer.Option("--yes", help="Confirma o início da sessão autônoma.")] = False,
    db: DbOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Roda uma sessão autônoma local com o champion. Ctrl+C = parada de emergência."""
    import time

    from poker_lab.lab.session import SimConfig

    _utf8()
    try:
        conf = SimConfig(hands=hands, seed=seed, stack_bb=stack_bb, ante_bb=ante_bb, max_minutes=max_minutes,
                         opponents=[o.strip() for o in opponents.split(",") if o.strip()])
    except ValueError as exc:
        typer.echo(f"configuração inválida: {str(exc).splitlines()[0]}", err=True)
        raise typer.Exit(2) from exc
    if not yes and not typer.confirm(f"Iniciar sessão autônoma de {hands} mãos (seed {seed})?", default=True):
        raise typer.Exit(2)
    mgr = _manager(db)
    s = mgr.start(conf)
    try:
        while s.running:
            time.sleep(0.5)
            if not as_json:
                st = s.status()
                typer.echo(f"\r[{st['control']['state']}] mão {st['summary']['hands_played']}/{s.hands_target}"
                           f" · decisões {st['summary']['decisions']}", nl=False)
    except KeyboardInterrupt:
        s.emergency()
        s.join(10)
        typer.echo("\nparada de emergência confirmada", err=True)
    st = s.status()
    mgr.close()
    if as_json:
        typer.echo(json.dumps(st, ensure_ascii=False, indent=1, default=str))
        return
    sm = st["summary"]
    b = sm["bb_per_100"]
    typer.echo("")
    typer.echo(f"sessão {st['session_id']} · estado {st['control']['state']} · motivo: {st['control']['stop_reason'] or st['history'][-1]['reason']}")
    typer.echo(f"mãos {sm['hands_played']} · bb/100 {b['mean']} (IC 95% {b['low']} a {b['high']})")
    typer.echo(f"decisões {sm['decisions']}: " + ", ".join(f"{k} {v}" for k, v in sm["labels"].items()))
    q = st["quality"]
    typer.echo(f"qualidade: {q['evaluable']} avaliáveis na janela; adequação {q['adequacy']}; IC {q['adequacy_ci']}")
    typer.echo(f"detalhes: poker-lab sessions show {st['session_id']}")


@sessions_app.command("list")
def sessions_list(db: DbOpt = None, as_json: JsonOpt = False) -> None:
    """Sessões locais registradas."""
    _utf8()
    mgr = _manager(db)
    rows = mgr.list_sessions()

    def render(rows: list[dict[str, Any]]) -> None:
        _table([[r["created_at"][:19], r["session_id"], r["state"], f"{r['hands_played']}/{r['hands_target']}",
                 (r["bb_per_100"] or {}).get("mean", "—"), r["stop_reason"] or "—"] for r in rows],
               ["início", "sessão", "estado", "mãos", "bb/100", "motivo"])

    _emit(rows, as_json, render)
    mgr.close()


@sessions_app.command("show")
def sessions_show(session_id: str, db: DbOpt = None, as_json: JsonOpt = False) -> None:
    """Resumo, eventos de controle e métricas de uma sessão."""
    _utf8()
    mgr = _manager(db)
    r = mgr.get_session(session_id)
    mgr.close()
    if r is None:
        typer.echo("sessão não encontrada", err=True)
        raise typer.Exit(2)

    def render(r: dict[str, Any]) -> None:
        sm = r["summary"] or {}
        typer.echo(f"sessão {r['session_id']} · {r['state']} · política {r['policy_label']} ({r['policy_sha256'][:12]}…)")
        typer.echo(f"config: {json.dumps(r['config'], ensure_ascii=False)}")
        typer.echo(f"mãos {r['hands_played']}/{r['hands_target']} · motivo: {r['stop_reason'] or '—'}")
        if sm:
            typer.echo(f"bb/100: {sm['bb_per_100']}")
            typer.echo(f"classificações: {sm['labels']} · perda de EV estimada: {sm['ev_loss_bb']}")
            for k, v in sm["by_position"].items():
                typer.echo(f"  posição {k}: n={v['n']} média={v['mean']} IC=({v['low']}, {v['high']})")
            for k, v in sm["by_opponent"].items():
                typer.echo(f"  vs {k}: n={v['n']} média={v['mean']} IC=({v['low']}, {v['high']})")
        typer.echo("eventos:")
        for e in r["events"]:
            typer.echo(f"  {e['at']}  {e['from_state']} -> {e['to_state']}  [{e['command']}] {e['reason']} ({e['actor']})")

    _emit(r, as_json, render)


@app.command()
def doctor() -> None:
    """Checagem rápida só do ambiente (sem tocar nos bancos)."""
    _utf8()
    env = environment()
    typer.echo(json.dumps(env, ensure_ascii=False, indent=1))
    raise typer.Exit(0 if env["python_ok"] and env["dependencies_ok"] else 1)


if __name__ == "__main__":
    app()
