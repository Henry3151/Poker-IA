"""Self-play MCCFR training of the heads-up push/fold abstraction, one game per stack depth."""

from __future__ import annotations

import functools
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from poker_lab.domain.seeds import derive_seed, validate_seed
from poker_lab.training.checkpoints import Checkpoint, PushFoldPolicy
from poker_lab.training.games import PushFoldGame
from poker_lab.training.mccfr import ExternalSamplingMCCFR, MCCFRState, exploitability, policy_value

DEFAULT_STACKS = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0]


@dataclass
class TrainingSummary:
    checkpoint: Checkpoint
    elapsed_seconds: float
    peak_memory_mb: float
    iterations_total: int
    throughput_per_second: float
    metrics: dict[str, Any]


def train_pushfold(
    table: dict[str, Any],
    iterations: int,
    seed: int,
    stacks: list[float] | None = None,
    ante_bb: float = 0.0,
    resume: Checkpoint | None = None,
    evaluate: bool = True,
    progress: Callable[[float, int], None] | None = None,
) -> TrainingSummary:
    validate_seed(seed)
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    stacks = stacks or (resume.policy.stacks_bb if resume else list(DEFAULT_STACKS))
    if resume is not None:
        if resume.seed != seed:
            raise ValueError("resume requires the same seed for reproducibility")
        if float(resume.config.get("ante_bb", 0.0)) != ante_bb:
            raise ValueError("resume requires the same ante")
    classes = table["classes"]
    tracemalloc.start()
    t0 = time.perf_counter()
    sb_push: dict[str, dict[str, float]] = {}
    bb_call: dict[str, dict[str, float]] = {}
    solver_state: dict[str, Any] = {}
    iters: dict[str, int] = {}
    metrics: dict[str, Any] = {"per_stack": {}}
    for s in stacks:
        key = f"{s:g}"
        game = PushFoldGame(s, classes, table["equity"], table["weights"], ante_bb)
        state = MCCFRState.from_json(resume.solver_state[key]) if resume and key in resume.solver_state else None
        solver = ExternalSamplingMCCFR(game, derive_seed(seed, "stack", key), state)
        cb: Callable[[int], None] | None = functools.partial(progress, s) if progress is not None else None
        solver.run(iterations, callback=cb)
        avg = solver.average_strategy()
        sb_push[key] = {c: round(avg.get(f"SB:{c}", [1.0, 0.0])[1], 6) for c in classes}
        bb_call[key] = {c: round(avg.get(f"BB:{c}", [1.0, 0.0])[1], 6) for c in classes}
        solver_state[key] = solver.state.to_json()
        iters[key] = solver.state.iterations
        m: dict[str, Any] = {
            "push_pct_combos": _combo_pct(sb_push[key], classes),
            "call_pct_combos": _combo_pct(bb_call[key], classes),
        }
        if evaluate:
            m["exploitability_bb"] = round(exploitability(game, avg), 6)
            m["sb_value_bb"] = round(policy_value(game, avg), 6)
        metrics["per_stack"][key] = m
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_iters = sum(iters.values()) - (sum(resume.iterations.values()) if resume else 0)
    if evaluate:
        metrics["mean_exploitability_bb"] = round(
            sum(v["exploitability_bb"] for v in metrics["per_stack"].values()) / len(stacks), 6
        )
    ckpt = Checkpoint(
        algorithm="mccfr_external_sampling",
        game="hu_pushfold",
        seed=seed,
        iterations=iters,
        config={
            "ante_bb": ante_bb,
            "stacks_bb": stacks,
            "equity_table": {k: table[k] for k in ("samples_per_pair", "seed", "method")},
        },
        metrics=metrics,
        policy=PushFoldPolicy(stacks_bb=stacks, sb_push=sb_push, bb_call=bb_call),
        solver_state=solver_state,
    )
    return TrainingSummary(
        checkpoint=ckpt,
        elapsed_seconds=round(elapsed, 3),
        peak_memory_mb=round(peak / 2**20, 2),
        iterations_total=total_iters,
        throughput_per_second=round(total_iters / elapsed, 1) if elapsed > 0 else 0.0,
        metrics=metrics,
    )


def _combo_pct(probs: dict[str, float], classes: list[str]) -> float:
    from poker_lab.strategy.ranges import combos_of

    return round(sum(probs[c] * combos_of(c) for c in classes) / 1326 * 100, 2)
