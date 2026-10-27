"""Equity/pot-odds agent: Monte Carlo equity vs. the number of active opponents."""

from __future__ import annotations

from typing import Any

from poker_lab.agents.base import Agent, clamp_raise, give_up
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.observation import Observation
from poker_lab.strategy.equity import monte_carlo_equity, pot_odds, top_fraction_filter
from poker_lab.strategy.icm import icm_call_decision
from poker_lab.strategy.opponents import OpponentModel


class EquityAgent(Agent):
    algorithm = "equity"

    def __init__(
        self,
        name: str | None = None,
        version_label: str = "v1",
        seed: int = 0,
        samples: int = 300,
        call_margin: float = 0.03,
        value_multiplier: float = 1.5,
        raised_range: float = 0.25,
        icm: bool = False,
        adaptive: bool = False,
    ) -> None:
        super().__init__(name, version_label, seed)
        self.samples = samples
        self.call_margin = call_margin
        self.value_multiplier = value_multiplier
        self.raised_range = raised_range
        self.icm = icm
        self.adaptive = adaptive
        self.model = OpponentModel()

    def config(self) -> dict[str, Any]:
        return {
            **super().config(),
            "samples": self.samples,
            "call_margin": self.call_margin,
            "value_multiplier": self.value_multiplier,
            "raised_range": self.raised_range,
            "icm": self.icm,
            "adaptive": self.adaptive,
        }

    PROFILE_RANGES = {
        "loose_aggressive": 0.45,
        "loose_passive": 0.35,
        "tight_aggressive": 0.18,
        "tight_passive": 0.12,
    }

    def _raiser_range(self, obs: Observation) -> tuple[float, str]:
        if not self.adaptive:
            return self.raised_range, "static"
        raiser = next((a.seat for a in reversed(obs.history) if a.street == "preflop" and a.kind == "raise"), None)
        pid = next((s.player_id for s in obs.seats if s.seat == raiser), None)
        prof = self.model.profile(pid) if pid else "unknown"
        return self.PROFILE_RANGES.get(prof, self.raised_range), prof

    def _icm_threshold(self, obs: Observation, equity: float) -> dict[str, Any] | None:
        t = obs.tournament
        if not self.icm or t is None or t.phase not in ("bubble", "itm", "final_table") or obs.to_call <= 0:
            return None
        live = [s for s in obs.seats if not s.folded]
        if len(live) != 2:
            return None
        me = next(s for s in obs.seats if s.seat == obs.seat)
        vil = next(s for s in live if s.seat != obs.seat)
        if not (vil.all_in or obs.to_call >= obs.stack):
            return None
        hero_total = me.stack + me.total_commitment
        vil_total = vil.stack + vil.total_commitment
        dead = obs.pot - me.total_commitment - vil.total_commitment
        others = [s.stack for s in obs.seats if s.folded and s.stack > 0] + list(t.other_table_stacks)
        try:
            d = icm_call_decision(hero_total, me.total_commitment, vil_total, dead, others, list(t.payouts), equity)
        except ValueError:
            return None
        return {k: round(v, 5) for k, v in d.items()}

    def act(self, obs: Observation) -> Action:
        lg = obs.legal
        if self.adaptive:
            self.model.observe(obs)
        n_opp = max(1, obs.n_opponents_active)
        facing_preflop_raise = obs.street is Street.PREFLOP and obs.current_bet > obs.big_blind
        rng_frac, profile = self._raiser_range(obs)
        flt = top_fraction_filter(rng_frac) if facing_preflop_raise else None
        est = monte_carlo_equity(obs.hole_cards, obs.board, n_opp, self.samples, self.rng, flt)
        po = pot_odds(obs.to_call, obs.pot)
        fair = 1.0 / (n_opp + 1)
        eff_bb = obs.effective_stack / obs.big_blind
        self.last_info = {
            **est.as_dict(),
            "pot_odds": round(po, 5),
            "fair_share": round(fair, 5),
            "opponent_model": f"top{int(rng_frac * 100)}pct" if flt else "uniform_random",
            "opponent_profile": profile,
            "phase": obs.tournament.phase if obs.tournament else None,
        }
        icm = self._icm_threshold(obs, est.equity)
        if icm is not None:
            self.last_info["icm"] = icm
            need = icm["icm_breakeven_equity"] + self.call_margin
            self.last_info["rule"] = "icm_call" if est.equity >= need else "icm_fold"
            return Action.call() if est.equity >= need else give_up(lg)
        value_line = est.equity >= min(0.85, fair * self.value_multiplier)
        if obs.street is Street.PREFLOP and eff_bb <= 12:
            self.last_info["rule"] = "short_stack_shove"
            if est.equity >= min(0.8, fair * 1.25) and lg.can_raise:
                return clamp_raise(lg, lg.max_raise_to)
            if lg.can_call and est.equity >= po + self.call_margin:
                return Action.call()
            return give_up(lg)
        if value_line and lg.can_raise:
            self.last_info["rule"] = "value_raise"
            target = obs.current_bet + int(0.75 * (obs.pot + obs.to_call))
            return clamp_raise(lg, max(target, 2 * obs.big_blind))
        if obs.to_call > 0:
            self.last_info["rule"] = "pot_odds_call" if est.equity >= po + self.call_margin else "pot_odds_fold"
            return Action.call() if est.equity >= po + self.call_margin else Action.fold()
        self.last_info["rule"] = "check"
        return Action.check()
