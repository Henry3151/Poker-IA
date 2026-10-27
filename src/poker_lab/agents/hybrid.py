"""HybridAgent (P7b challenger).

Each component addresses a diagnosed cause (docs/P7B_REPORT.md):
- H1 (antes): SB-vs-BB push/fold from a policy trained WITH antes and dead money.
- H2 (too few opens / no steals): first-in raise-or-fold with position-based open ranges;
  first-in shove when short, chosen by chip EV against the trained calling ranges.
- H4 (SB limps): the SB never limps first-in (raise or fold).
- Preflop defence: decisions use equity against the *raiser's* estimated range (by the
  raiser's position, or by observed profile when enough hands were seen) with a
  realisation discount for out-of-position calls; ICM threshold when an all-in matters.
- H3 (postflop over-calling): equity against a betting-range filter calibrated on the
  development set; continuation bet as preflop aggressor heads-up.
Everything here is heuristic except the push/fold sub-policy (epsilon-equilibrium of an
abstract heads-up game). Only decision-time information is used.
"""

from __future__ import annotations

from typing import Any

from poker_lab.agents.base import Agent, clamp_raise, give_up
from poker_lab.agents.policy_agent import PolicyAgent
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.cards import hand_class
from poker_lab.domain.observation import Observation
from poker_lab.strategy.equity import monte_carlo_equity, pot_odds
from poker_lab.strategy.icm import icm_call_decision
from poker_lab.strategy.opponents import OpponentModel
from poker_lab.strategy.postflop_ranges import betting_filter
from poker_lab.strategy.preflop_model import ClassEquity, open_fraction, top_range
from poker_lab.strategy.ranges import class_rank_fraction
from poker_lab.training.checkpoints import Checkpoint, load_checkpoint, load_checkpoint_meta
from poker_lab.training.pushfold_tables import load_table

PROFILE_OPEN = {"loose_aggressive": 0.45, "loose_passive": 0.40, "tight_aggressive": 0.12, "tight_passive": 0.06}


class HybridAgent(Agent):
    algorithm = "policy"

    def __init__(
        self,
        checkpoint: Checkpoint,
        table: dict[str, Any],
        name: str | None = None,
        version_label: str = "hybrid",
        seed: int = 0,
        samples: int = 150,
        bluff_rate: float = 0.0,
        icm: bool = True,
        shove_max_bb: float = 12.0,
        cbet_freq: float = 0.7,
        checkpoint_sha256: str | None = None,
    ) -> None:
        super().__init__(name, version_label, seed)
        self.pf = PolicyAgent(checkpoint, f"{self.name}-pf", version_label, seed + 7, fallback_samples=samples)
        self.ce = ClassEquity.from_table(table)
        self.samples = samples
        self.bluff_rate = bluff_rate
        self.icm = icm
        self.shove_max_bb = shove_max_bb
        self.cbet_freq = cbet_freq
        self.checkpoint_sha256 = checkpoint_sha256
        self.model = OpponentModel()

    @classmethod
    def from_checkpoint(
        cls, path: str, name: str, version_label: str, seed: int, table_path: str, **params: Any
    ) -> HybridAgent:
        meta = load_checkpoint_meta(path)
        return cls(load_checkpoint(path), load_table(table_path), name, version_label, seed, checkpoint_sha256=meta["sha256"], **params)

    def reseed(self, seed: int) -> None:
        super().reseed(seed)
        self.pf.reseed(seed + 7)

    def config(self) -> dict[str, Any]:
        return {
            **super().config(),
            "samples": self.samples,
            "bluff_rate": self.bluff_rate,
            "icm": self.icm,
            "shove_max_bb": self.shove_max_bb,
            "cbet_freq": self.cbet_freq,
            "checkpoint_sha256": self.checkpoint_sha256,
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _players_behind(obs: Observation) -> list[int]:
        """Seats still to act after us this street, in order (not folded, not all-in)."""
        n = len(obs.seats)
        acted = {a.seat for a in obs.history if a.street == obs.street.label}
        out = []
        k = (obs.seat + 1) % n
        while k != obs.seat:
            s = obs.seats[k]
            if not s.folded and not s.all_in and (k not in acted or s.street_commitment < obs.current_bet):
                out.append(k)
            k = (k + 1) % n
        return out

    def _raiser_range(self, obs: Observation, raiser_seat: int) -> tuple[dict[str, float], str]:
        rs = obs.seats[raiser_seat]
        prof = self.model.profile(rs.player_id)
        if prof in PROFILE_OPEN:
            return top_range(PROFILE_OPEN[prof]), prof
        return top_range(open_fraction(self._behind_when_opening(obs, raiser_seat))), "position_default"

    @staticmethod
    def _behind_when_opening(obs: Observation, seat: int) -> int:
        """Players behind a first-in raiser by position (BTN 2, SB 1, BB 1, others n-offset+2)."""
        n = len(obs.seats)
        if n == 2:
            return 1
        off = (seat - obs.button_seat) % n
        return {0: 2, 1: 1, 2: 1}.get(off, n - off + 2)

    def _open_fraction(self, obs: Observation, behind: list[int]) -> tuple[float, dict[str, Any]]:
        """First-in open fraction (v1: fixed by players behind)."""
        return open_fraction(len(behind)), {}

    def _reraise_range(self, obs: Observation, raiser_seat: int) -> tuple[dict[str, float], str]:
        """Range assumed for a player who re-raised us (v1: fixed top 6%)."""
        return top_range(min(0.06, open_fraction(1) * 0.1)), "+3bet"

    def _icm_ok(self, obs: Observation) -> bool:
        t = obs.tournament
        return self.icm and t is not None and t.phase in ("bubble", "itm", "final_table")

    # ------------------------------------------------------------------ act
    def act(self, obs: Observation) -> Action:
        self.model.observe(obs)
        if obs.street is Street.PREFLOP:
            return self._preflop(obs)
        return self._postflop(obs)

    def _preflop(self, obs: Observation) -> Action:
        lg = obs.legal
        cls = hand_class(obs.hole_cards)
        frac = class_rank_fraction(cls)
        bb = obs.big_blind
        me = obs.seats[obs.seat]
        # 1) trained push/fold sub-policy in its own abstraction
        if self.pf._situation(obs) is not None:
            eff, ante, dead = self.pf._hand_totals(obs)
            if self.pf._bucket(eff, ante, dead) is not None:
                a = self.pf.act(obs)
                self.last_info = {**self.pf.last_info, "component": "pushfold_v2"}
                return a
        raises = [a for a in obs.history if a.street == "preflop" and a.kind == "raise"]
        info: dict[str, Any] = {"hand_class": cls, "class_rank": round(frac, 4)}
        behind = self._players_behind(obs)
        my_total = (me.stack + me.total_commitment) / bb
        eff_bb = obs.effective_stack / bb
        if not raises:
            # 2) first-in (limpers treated as dead money): shove when short, else raise-or-fold
            if eff_bb <= self.shove_max_bb and lg.can_raise:
                table = self.pf.contexts
                callers = []
                for k in behind:
                    s = obs.seats[k]
                    tot = (s.stack + s.total_commitment) / bb
                    key = self.pf._bucket(min(tot, my_total), obs.ante / bb, 0.0)
                    if key is None:
                        key = max(table, key=lambda x: table[x]["stack_bb"])
                    callers.append((tot, s.total_commitment / bb, self.pf.ckpt.policy.bb_call[key]))
                ev = self.ce.shove_ev(
                    cls, pot_bb=obs.pot / bb, my_posted_bb=me.total_commitment / bb, my_total_bb=my_total, callers=callers
                )
                self.last_info = {**info, "component": "first_in_shove_ev", "shove_ev_bb": round(ev, 4), "callers": len(callers)}
                return clamp_raise(lg, lg.max_raise_to) if ev > 0 else give_up(lg)
            open_frac, adj = self._open_fraction(obs, behind)
            self.last_info = {
                **info, "component": "first_in_open", "open_fraction": open_frac, "players_behind": len(behind), **adj
            }
            if frac <= open_frac and lg.can_raise:
                limpers = sum(1 for a in obs.history if a.street == "preflop" and a.kind == "call")
                return clamp_raise(lg, int((2.2 + limpers) * bb))
            return give_up(lg)
        # 3) facing a raise
        raiser = raises[-1].seat
        rng_r, prof = self._raiser_range(obs, raiser)
        if len(raises) >= 2:
            rng_r, tag = self._reraise_range(obs, raiser)
            prof += tag
        eq, _ = self.ce.eq_vs_range(cls, rng_r)
        po = pot_odds(obs.to_call, obs.pot)
        info.update({"component": "vs_raise", "raiser_profile": prof, "eq_vs_range": round(eq, 4), "pot_odds": round(po, 4)})
        vil = obs.seats[raiser]
        facing_allin = vil.all_in or obs.to_call >= obs.stack
        live = [s for s in obs.seats if not s.folded]
        if facing_allin and len(live) == 2 and self._icm_ok(obs):
            t = obs.tournament
            assert t is not None
            others = [s.stack for s in obs.seats if s.folded and s.stack > 0] + list(t.other_table_stacks)
            try:
                d = icm_call_decision(
                    me.stack + me.total_commitment, me.total_commitment, vil.stack + vil.total_commitment,
                    obs.pot - me.total_commitment - vil.total_commitment, others, list(t.payouts), eq,
                )
                self.last_info = {**info, "icm": {k: round(v, 5) for k, v in d.items()}}
                return Action.call() if eq >= d["icm_breakeven_equity"] + 0.02 else give_up(lg)
            except ValueError:
                pass
        in_position = obs.position == "BTN" or (len(behind) == 0 and obs.position not in ("SB", "BB"))
        realisation = 1.0 if facing_allin else (0.9 if in_position else 0.75)
        self.last_info = {**info, "realisation": realisation}
        if len(raises) == 1 and lg.can_raise and (frac <= 0.035 or (eff_bb <= 25 and eq >= 0.56)):
            target = lg.max_raise_to if eff_bb <= 25 else 3 * obs.current_bet + (obs.pot - obs.current_bet) // 2
            self.last_info["decision"] = "3bet"
            return clamp_raise(lg, target)
        if len(raises) >= 2 and lg.can_raise and frac <= 0.02:
            self.last_info["decision"] = "4bet_allin"
            return clamp_raise(lg, lg.max_raise_to)
        if lg.can_call and eq * realisation >= po + 0.01:
            self.last_info["decision"] = "call"
            return Action.call()
        return give_up(lg)

    def _postflop(self, obs: Observation) -> Action:
        lg = obs.legal
        n_opp = max(1, obs.n_opponents_active)
        facing = obs.to_call > 0
        flt = betting_filter(obs.board, self.bluff_rate, self.rng) if facing else None
        est = monte_carlo_equity(obs.hole_cards, obs.board, n_opp, self.samples, self.rng, flt, max_rejections=200)
        po = pot_odds(obs.to_call, obs.pot)
        self.last_info = {
            **est.as_dict(),
            "pot_odds": round(po, 5),
            "opponent_model": f"betting_range(bluff_rate={self.bluff_rate})" if facing else "uniform_random",
            "component": "postflop",
        }
        if facing:
            if est.equity >= 0.75 and lg.can_raise:
                self.last_info["decision"] = "raise_value"
                return clamp_raise(lg, obs.current_bet * 3)
            if est.equity >= po + 0.02:
                self.last_info["decision"] = "call"
                return Action.call()
            return Action.fold()
        # not facing a bet
        value_threshold = 0.62 if n_opp == 1 else 0.5 + 0.08 * n_opp
        if est.equity >= value_threshold and lg.can_raise:
            self.last_info["decision"] = "value_bet"
            return clamp_raise(lg, int(obs.pot * 0.6))
        was_aggressor = any(a.street == "preflop" and a.kind == "raise" for a in obs.history) and (
            [a.seat for a in obs.history if a.street == "preflop" and a.kind == "raise"][-1] == obs.seat
        )
        if was_aggressor and n_opp == 1 and obs.street is Street.FLOP and lg.can_raise and self.rng.random() < self.cbet_freq:
            self.last_info["decision"] = "cbet"
            return clamp_raise(lg, max(obs.big_blind, int(obs.pot * 0.4)))
        self.last_info["decision"] = "check"
        return Action.check() if lg.can_check else give_up(lg)


class HybridAdaptiveAgent(HybridAgent):
    """hybrid-v2-adaptive: v1 + adjustments from opponents' observed public behaviour.

    - Steal sizing of the range: estimated probability that all players behind fold, from
      their observed fold-to-steal (prior 0.75 per unknown player, shrunk with n_prior=10).
      Open range is narrowed when resistance is high and widened when it is low.
    - Re-raise range: when a player 3-bets us, assume a range as wide as their observed
      3-bet frequency (shrunk toward 6%), instead of a fixed top 6%.
    """

    PRIOR_FOLD = 0.75
    N_PRIOR = 10

    def _fold_prob(self, obs: Observation, seat: int) -> float:
        st = self.model.get(obs.seats[seat].player_id)
        n = st.vs_steal_opps if st else 0
        folds = st.vs_steal_folds if st else 0
        return (folds + self.PRIOR_FOLD * self.N_PRIOR) / (n + self.N_PRIOR)

    def _open_fraction(self, obs: Observation, behind: list[int]) -> tuple[float, dict[str, Any]]:
        base, _ = super()._open_fraction(obs, behind)
        if len(behind) > 2:
            return base, {}
        p_all_fold = 1.0
        for k in behind:
            p_all_fold *= self._fold_prob(obs, k)
        prior = self.PRIOR_FOLD ** len(behind)
        # scale the open fraction with observed vs prior resistance, bounded
        scale = max(0.5, min(1.35, (p_all_fold / prior) ** 1.5))
        return min(0.8, base * scale), {"p_all_fold_est": round(p_all_fold, 3), "open_scale": round(scale, 3)}

    def _reraise_range(self, obs: Observation, raiser_seat: int) -> tuple[dict[str, float], str]:
        st = self.model.get(obs.seats[raiser_seat].player_id)
        if not st or st.threebet_opps == 0:
            return super()._reraise_range(obs, raiser_seat)
        rate = (st.threebets + 0.06 * self.N_PRIOR) / (st.threebet_opps + self.N_PRIOR)
        return top_range(max(0.03, min(0.35, rate))), f"+3bet(rate={rate:.2f})"
