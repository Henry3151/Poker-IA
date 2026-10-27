"""Equity/pot-odds agent: Monte Carlo equity vs. the number of active opponents."""

from __future__ import annotations

from typing import Any

from poker_lab.agents.base import Agent, clamp_raise, give_up
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.observation import Observation
from poker_lab.strategy.equity import monte_carlo_equity, pot_odds, top_fraction_filter


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
    ) -> None:
        super().__init__(name, version_label, seed)
        self.samples = samples
        self.call_margin = call_margin
        self.value_multiplier = value_multiplier
        self.raised_range = raised_range

    def config(self) -> dict[str, Any]:
        return {
            **super().config(),
            "samples": self.samples,
            "call_margin": self.call_margin,
            "value_multiplier": self.value_multiplier,
            "raised_range": self.raised_range,
        }

    def act(self, obs: Observation) -> Action:
        lg = obs.legal
        n_opp = max(1, obs.n_opponents_active)
        facing_preflop_raise = obs.street is Street.PREFLOP and obs.current_bet > obs.big_blind
        flt = top_fraction_filter(self.raised_range) if facing_preflop_raise else None
        est = monte_carlo_equity(obs.hole_cards, obs.board, n_opp, self.samples, self.rng, flt)
        po = pot_odds(obs.to_call, obs.pot)
        fair = 1.0 / (n_opp + 1)
        eff_bb = obs.effective_stack / obs.big_blind
        self.last_info = {
            **est.as_dict(),
            "pot_odds": round(po, 5),
            "fair_share": round(fair, 5),
            "opponent_model": f"top{int(self.raised_range * 100)}pct" if flt else "uniform_random",
        }
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
