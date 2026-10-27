"""Use case: train the push/fold policy with MCCFR, save a checkpoint and record it."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from poker_lab.persistence import repositories as repo
from poker_lab.persistence.db import file_sha256, transaction
from poker_lab.training.checkpoints import load_checkpoint, load_checkpoint_meta, save_checkpoint
from poker_lab.training.pushfold_tables import get_or_build
from poker_lab.training.pushfold_trainer import train_pushfold

log = logging.getLogger("poker_lab.training")

LINEAGE = "pushfold"


def run_pushfold_training(
    conn: sqlite3.Connection,
    *,
    iterations: int,
    seed: int,
    version_label: str,
    artifacts_dir: str | Path = "artifacts",
    table_samples: int = 200,
    table_seed: int = 20261026,
    stacks: list[float] | None = None,
    ante_bb: float = 0.0,
    resume_path: str | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    art = Path(artifacts_dir)
    table_path = art / "tables" / f"hu_class_equity_s{table_samples}_seed{table_seed}.json"
    table = get_or_build(table_path, table_samples, table_seed)
    resume = load_checkpoint(resume_path) if resume_path else None
    parent_sha = load_checkpoint_meta(resume_path)["sha256"] if resume_path else None
    config = {
        "iterations": iterations,
        "stacks": stacks,
        "ante_bb": ante_bb,
        "table_samples": table_samples,
        "table_seed": table_seed,
        "resume_from_sha256": parent_sha,
    }
    exp = experiment_id or repo.create_experiment(
        conn, f"pushfold-{version_label}", "mccfr_external_sampling", config, seed, hypothesis="MCCFR push/fold policy"
    )
    repo.set_experiment_status(conn, exp, "running")
    run_id = repo.start_training_run(conn, exp, "mccfr_external_sampling", "hu_pushfold", seed, config)
    try:
        summary = train_pushfold(table, iterations, seed, stacks=stacks, ante_bb=ante_bb, resume=resume)
    except Exception as exc:
        repo.finish_training_run(
            conn, run_id, status="failed", iteration_end=None, elapsed_seconds=0.0, peak_memory_mb=None, throughput=None,
            metrics={}, error=f"{type(exc).__name__}: {exc}",
        )
        repo.set_experiment_status(conn, exp, "failed")
        raise
    ckpt = summary.checkpoint
    ckpt.parent_sha256 = parent_sha
    ckpt_path = art / "checkpoints" / f"{LINEAGE}-{version_label}.json"
    if ckpt_path.exists():
        raise FileExistsError(f"checkpoint {ckpt_path} already exists; choose a new version label")
    meta = save_checkpoint(ckpt, ckpt_path)
    parent_vid = None
    if parent_sha:
        row = conn.execute("SELECT agent_version_id FROM agent_versions WHERE checkpoint_sha256=?", (parent_sha,)).fetchone()
        parent_vid = row["agent_version_id"] if row else None
    with transaction(conn):
        table_art = conn.execute("SELECT artifact_id FROM artifacts WHERE path=?", (str(table_path),)).fetchone()
        if table_art is None:
            repo.register_artifact(
                conn, "equity_table", str(table_path), file_sha256(table_path), table_path.stat().st_size,
                {"samples_per_pair": table["samples_per_pair"], "seed": table["seed"]},
            )
        aid = repo.register_artifact(
            conn, "checkpoint", str(ckpt_path), meta["sha256"], meta["size_bytes"],
            {"game": ckpt.game, "algorithm": ckpt.algorithm, "iterations": ckpt.iterations, "seed": seed},
        )
        vid = repo.get_or_create_agent_version(
            conn, LINEAGE, "policy", version_label,
            config={"checkpoint_path": str(ckpt_path), "iterations": ckpt.iterations},
            checkpoint_artifact_id=aid, checkpoint_sha256=meta["sha256"], status="candidate", parent_version_id=parent_vid,
        )
        repo.finish_training_run(
            conn, run_id, status="completed", iteration_end=sum(ckpt.iterations.values()),
            elapsed_seconds=summary.elapsed_seconds, peak_memory_mb=summary.peak_memory_mb,
            throughput=summary.throughput_per_second, metrics=summary.metrics, checkpoint_artifact_id=aid, agent_version_id=vid,
        )
        repo.set_experiment_status(conn, exp, "completed")
    log.info("training_completed", extra={"version": version_label, "sha256": meta["sha256"], "elapsed": summary.elapsed_seconds})
    return {
        "experiment_id": exp,
        "training_run_id": run_id,
        "agent_version_id": vid,
        "checkpoint_path": str(ckpt_path),
        "sha256": meta["sha256"],
        "metrics": summary.metrics,
        "elapsed_seconds": summary.elapsed_seconds,
        "peak_memory_mb": summary.peak_memory_mb,
        "throughput_per_second": summary.throughput_per_second,
    }
