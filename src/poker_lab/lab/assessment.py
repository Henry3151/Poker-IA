"""Decision assessment using ONLY decision-time information (P9-C).

A decision is graded against a reference only when a validated reference exists for that spot:

* ``pushfold_nash`` — heads-up push/fold spots (folded to the small blind; big blind facing the
  small blind's all-in), against the MCCFR push/fold equilibrium of the frozen checkpoint
  (exploitability ~0.005 bb/hand, docs/TRAINING.md) and the frozen class-vs-class equity table.
  EV of each option is computed assuming the opponent plays that equilibrium.

Everything else is ``inconclusiva`` with the reason recorded. Agreement with a model is never
called "correct" beyond what the reference supports, and the hand outcome is never an input:
the function receives the decision-time ``Observation`` and the chosen action only.

Grading (EV gap = EV(chosen) - EV(best option), in big blinds):
* ``adequada``                    gap >= -0.10 bb (table/abstraction tolerance)
* ``provavel_erro_estrategico``   gap <= -0.50 bb
* ``inconclusiva``                in between (marginal), or outside the trained contexts
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from poker_lab.domain.actions import Action, ActionKind, Street
from poker_lab.domain.cards import hand_class
from poker_lab.domain.observation import Observation
from poker_lab.lab.quality import ADEQUATE, ERROR, INCONCLUSIVE, TECHNICAL
from poker_lab.training.checkpoints import Checkpoint, load_checkpoint, load_checkpoint_meta
from poker_lab.training.pushfold_tables import load_table

ADEQUATE_TOL_BB = 0.10
ERROR_GAP_BB = 0.50
CHECKPOINT = "artifacts/checkpoints/pushfold-v2-ante.json"
TABLE = "artifacts/tables/hu_class_equity_s200_seed20261026.json"


@dataclass
class Assessment:
    label: str
    reference: str | None
    reason: str
    spot: str | None = None
    ev_chosen_bb: float | None = None
    ev_best_bb: float | None = None
    ev_gap_bb: float | None = None
    best_action: str | None = None
    confidence: str = "n/a"
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def technical(issue: str) -> Assessment:
    return Assessment(TECHNICAL, None, f"falha técnica: {issue}", confidence="alta")


def _situation(obs: Observation) -> str | None:
    if obs.street is not Street.PREFLOP:
        return None
    live = [s for s in obs.seats if not s.folded]
    if len(live) != 2:
        return None
    sb_pos = "BTN" if len(obs.seats) == 2 else "SB"
    opp = next(s for s in live if s.seat != obs.seat)
    voluntary = [a for a in obs.history if a.kind != "fold"]
    if obs.position == sb_pos and opp.position == "BB" and not voluntary and obs.current_bet <= obs.big_blind:
        return "sb_first_in"
    if (obs.position == "BB" and opp.position == sb_pos and opp.all_in and obs.to_call > 0
            and len(voluntary) == 1 and voluntary[0].seat == opp.seat):
        return "bb_vs_shove"
    return None


def _totals(obs: Observation) -> tuple[float, float, float]:
    live = [s for s in obs.seats if not s.folded]
    me = next(s for s in live if s.seat == obs.seat)
    opp = next(s for s in live if s.seat != obs.seat)
    bb = obs.big_blind
    eff = min(me.stack + me.total_commitment, opp.stack + opp.total_commitment) / bb
    dead = (obs.pot - me.total_commitment - opp.total_commitment) / bb
    return eff, obs.ante / bb, max(0.0, dead)


class PushFoldReference:
    name = "pushfold_nash"

    def __init__(self, checkpoint: Checkpoint, table: dict[str, Any], checkpoint_sha256: str = "") -> None:
        self.policy = checkpoint.policy
        self.ctx = self.policy.context_table()
        self.classes: list[str] = table["classes"]
        self.idx = {c: i for i, c in enumerate(self.classes)}
        self.eq: list[list[float]] = table["equity"]
        self.w: list[list[float]] = table["weights"]
        self.sha = checkpoint_sha256

    @classmethod
    def load(cls, root: Path) -> PushFoldReference:
        meta = load_checkpoint_meta(root / CHECKPOINT)
        return cls(load_checkpoint(root / CHECKPOINT), load_table(root / TABLE), meta["sha256"])

    def _context(self, eff: float, ante: float, dead: float) -> str | None:
        """Nearest trained context, only if close enough to be a valid reference."""
        best = min(self.ctx, key=lambda k: (abs(self.ctx[k]["ante_bb"] - ante), abs(self.ctx[k]["dead_bb"] - dead),
                                            abs(self.ctx[k]["stack_bb"] - eff)))
        c = self.ctx[best]
        if abs(c["ante_bb"] - ante) > 0.05 or abs(c["dead_bb"] - dead) > 0.30:
            return None
        if abs(c["stack_bb"] - eff) > max(1.0, 0.10 * eff):
            return None
        return best

    def evs(self, spot: str, cls: str, key: str) -> dict[str, float]:
        c = self.ctx[key]
        S, a, d = c["stack_bb"], c["ante_bb"], c["dead_bb"]
        i = self.idx[cls]
        n = len(self.classes)
        if spot == "sb_first_in":
            call = self.policy.bb_call[key]
            num = den = 0.0
            for j in range(n):
                w = self.w[i][j]
                if w <= 0:
                    continue
                pc = call[self.classes[j]]
                num += w * ((1 - pc) * (1 + a + d) + pc * (self.eq[i][j] * (2 * S + d) - S))
                den += w
            return {"push": num / den, "fold": -(0.5 + a)}
        push = self.policy.sb_push[key]
        num = den = 0.0
        for k in range(n):
            w = self.w[k][i] * push[self.classes[k]]
            if w <= 0:
                continue
            num += w * ((1 - self.eq[k][i]) * (2 * S + d) - S)
            den += w
        return {"call": num / den if den else float("-inf"), "fold": -(1 + a)}

    def assess(self, obs: Observation, chosen: Action) -> Assessment:
        spot = _situation(obs)
        if spot is None:
            return Assessment(INCONCLUSIVE, None, "sem referência validada para este tipo de decisão",
                              limitations=["só spots heads-up de push/fold têm referência validada nesta etapa"])
        eff, ante, dead = _totals(obs)
        key = self._context(eff, ante, dead)
        if key is None:
            return Assessment(INCONCLUSIVE, self.name, f"contexto fora do treinado (stack {eff:.1f} bb, ante {ante:.2f}, "
                              f"dinheiro morto {dead:.2f})", spot=spot,
                              limitations=["referência válida só perto dos contextos treinados (5–20 bb)"])
        if spot == "sb_first_in":
            if chosen.kind is ActionKind.FOLD:
                act = "fold"
            elif chosen.kind in (ActionKind.RAISE, ActionKind.BET) and chosen.amount == obs.legal.max_raise_to:
                act = "push"
            else:
                return Assessment(INCONCLUSIVE, self.name, "ação fora da abstração push/fold (limp ou raise parcial)", spot=spot,
                                  limitations=["a referência só compara all-in contra fold"])
        else:
            if chosen.kind is ActionKind.CALL:
                act = "call"
            elif chosen.kind is ActionKind.FOLD:
                act = "fold"
            else:
                return Assessment(INCONCLUSIVE, self.name, "ação fora da abstração (re-raise impossível após all-in)", spot=spot)
        cls = hand_class(obs.hole_cards)
        ev = self.evs(spot, cls, key)
        best = max(ev, key=lambda k: ev[k])
        gap = ev[act] - ev[best]
        if gap >= -ADEQUATE_TOL_BB:
            label, conf = ADEQUATE, "alta" if abs(ev["fold"] - max(v for k, v in ev.items() if k != "fold")) > 0.5 else "média"
        elif gap <= -ERROR_GAP_BB:
            label, conf = ERROR, "alta" if gap <= -1.0 else "média"
        else:
            label, conf = INCONCLUSIVE, "baixa"
        return Assessment(
            label, self.name,
            f"{spot}: {cls} · {act} vs melhor {best} · diferença {gap:+.2f} bb" + (" (margem pequena)" if label == INCONCLUSIVE else ""),
            spot=spot, ev_chosen_bb=round(ev[act], 4), ev_best_bb=round(ev[best], 4), ev_gap_bb=round(gap, 4),
            best_action=best, confidence=conf,
            assumptions=[
                f"oponente joga o equilíbrio push/fold do checkpoint (sha256 {self.sha[:12]}…)",
                f"contexto treinado {key}: stack {self.ctx[key]['stack_bb']:g} bb, ante {self.ctx[key]['ante_bb']:g}, "
                f"morto {self.ctx[key]['dead_bb']:g}",
                "equity por classe (tabela s200, seed 20261026), EV em fichas sem ICM",
            ],
            limitations=["referência de equilíbrio, não de exploração do adversário real",
                         "abstração heads-up push/fold; sem ICM; ruído Monte Carlo da tabela (~0,1 bb)"],
        )
