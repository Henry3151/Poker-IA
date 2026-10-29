"""Known evaluation runs (frozen) and discovery of other local databases. Read-only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poker_lab.lab.readonly import connect_ro, schema_version


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class KnownRun:
    key: str
    title: str
    question: str
    db: str  # relative to project root
    report: str  # versioned frozen report, relative to project root
    seed: int

    def db_path(self, root: Path) -> Path:
        return root / self.db

    def report_path(self, root: Path) -> Path:
        return root / self.report


KNOWN_RUNS: tuple[KnownRun, ...] = (
    KnownRun("P7", "P7 · avaliação quantitativa", "Como cada agente se sai em campos simulados variados?",
             "artifacts/p7/p7_lab.db", "docs/p7_artifacts/p7_report.json", 20261027),
    KnownRun("P7b", "P7b · promoção do hybrid-v1", "O hybrid-v1 supera a política push/fold anterior?",
             "artifacts/p7b/final.db", "docs/p7b_artifacts/p7b_final_report.json", 20261028),
    KnownRun("P7c", "P7c · robustez", "O champion resiste a adaptativos, blefadores e self-play?",
             "artifacts/p7c/final.db", "docs/p7c_artifacts/p7c_final_report.json", 20261029),
)


def get_run(key: str) -> KnownRun:
    for r in KNOWN_RUNS:
        if r.key.lower() == key.lower():
            return r
    raise KeyError(f"execução desconhecida: {key} (conhecidas: {', '.join(r.key for r in KNOWN_RUNS)})")


def load_report(run: KnownRun, root: Path) -> dict[str, Any]:
    return dict(json.loads(run.report_path(root).read_text(encoding="utf-8")))


def run_overview(run: KnownRun, root: Path) -> dict[str, Any]:
    """Light, read-only overview (no full scans): report facts + database presence/schema/size."""
    rep = load_report(run, root) if run.report_path(root).is_file() else None
    db = run.db_path(root)
    info: dict[str, Any] = {
        "key": run.key, "title": run.title, "question": run.question, "seed": run.seed,
        "report": run.report, "report_present": rep is not None, "db": run.db, "db_present": db.is_file(),
        "db_size_mb": round(db.stat().st_size / 1e6, 1) if db.is_file() else None,
        "schema_version": None, "tournaments": None,
    }
    if rep:
        info["evaluation_run_id"] = rep["evaluation_run_id"]
        info["scenarios"] = [s["label"] for s in rep["protocol"]["scenarios"]]
        info["candidates"] = [c["label"] for c in rep["protocol"]["candidates"]]
        info["expected_tournaments"] = sum(int(s["n_tournaments"]) for s in rep["protocol"]["scenarios"]) * len(info["candidates"])
        cc = rep.get("champion_challenger")
        info["primary_scenario"] = cc["criteria"]["primary_scenario"] if cc else rep["protocol"]["scenarios"][0]["label"]
        info["decisions"] = {k: v["decision"] for k, v in (cc or {}).get("decisions", {}).items()}
    if db.is_file():
        conn = connect_ro(db)
        try:
            info["schema_version"] = schema_version(conn)
            info["tournaments"] = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
        finally:
            conn.close()
    return info


def discover_databases(root: Path) -> list[dict[str, Any]]:
    """Every *.db under artifacts/ (excluding staging/backups), with schema version; read-only."""
    out = []
    known = {r.db for r in KNOWN_RUNS}
    for p in sorted((root / "artifacts").rglob("*.db")):
        rel = p.relative_to(root).as_posix()
        if any(part.startswith(".") or part in ("baseline", "backups") or part.startswith("incident") for part in p.parts):
            continue
        item: dict[str, Any] = {"path": rel, "size_mb": round(p.stat().st_size / 1e6, 1), "frozen": rel in known}
        try:
            conn = connect_ro(p)
            item["schema_version"] = schema_version(conn)
            conn.close()
        except Exception as exc:  # noqa: BLE001 - report, never crash a listing
            item["error"] = type(exc).__name__
        out.append(item)
    return out
