"""Adaptive opponents for robustness tests (field agents, not candidates).

Built on HeuristicAgent. They track every opponent's public preflop behaviour (steal
rate, 3-bet rate, fold to steal) with OpponentModel and adjust:
- blind defence vs frequent stealers: re-steal (3-bet) a wider range and call wider;
- response to 3-bets from frequent 3-bettors: 4-bet/call wider instead of folding;
- their own stealing when the blinds behind them fold too often.
Only legally observable information is used (actions; no hidden cards).
"""

from __future__ import annotations

from poker_lab.agents.base import clamp_raise, give_up
from poker_lab.agents.heuristic import HeuristicAgent
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.cards import hand_class
from poker_lab.domain.observation import Observation
from poker_lab.strategy.opponents import OpponentModel
from poker_lab.strategy.ranges import class_rank_fraction

MIN_OBS = 12


class AdaptiveHeuristicAgent(HeuristicAgent):
    algorithm = "heuristic"

    def __init__(
        self,
        *args: object,
        defend_pct: float = 0.35,
        resteal_pct: float = 0.12,
        steal_wide_pct: float = 0.45,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.defend_pct = defend_pct
        self.resteal_pct = resteal_pct
        self.steal_wide_pct = steal_wide_pct
        self.model = OpponentModel()

    def config(self) -> dict[str, object]:
        return {
            **super().config(),
            "adaptive": True,
            "defend_pct": self.defend_pct,
            "resteal_pct": self.resteal_pct,
            "steal_wide_pct": self.steal_wide_pct,
        }

    def act(self, obs: Observation) -> Action:
        self.model.observe(obs)
        if obs.street is Street.PREFLOP:
            a = self._adaptive_preflop(obs)
            if a is not None:
                return a
        return super().act(obs)

    def _adaptive_preflop(self, obs: Observation) -> Action | None:
        lg = obs.legal
        pre = [a for a in obs.history if a.street == "preflop"]
        raises = [a for a in pre if a.kind == "raise"]
        calls = [a for a in pre if a.kind == "call"]
        frac = class_rank_fraction(hand_class(obs.hole_cards))
        if obs.effective_stack / obs.big_blind <= 12:
            return None  # short stacks: base push/fold logic
        # 1) blinds facing a single late-position open from a frequent stealer
        if len(raises) == 1 and not calls and obs.position in ("SB", "BB"):
            opener = obs.seats[raises[0].seat]
            st = self.model.get(opener.player_id)
            if opener.position in ("CO", "BTN", "SB") and st and st.steal_opps >= MIN_OBS and st.steal_rate >= 0.35:
                self.last_info = {"method": "adaptive_blind_defence", "opener_steal_rate": round(st.steal_rate, 3)}
                if frac <= self.resteal_pct and lg.can_raise:
                    return clamp_raise(lg, 3 * obs.current_bet + obs.big_blind)
                if frac <= self.defend_pct and lg.can_call:
                    return Action.call()
                return give_up(lg)
        # 2) we opened and face a 3-bet from a frequent 3-bettor
        if len(raises) == 2 and raises[0].seat == obs.seat:
            three = obs.seats[raises[1].seat]
            st = self.model.get(three.player_id)
            if st and st.threebet_opps >= MIN_OBS and st.threebet_rate >= 0.15:
                self.last_info = {"method": "adaptive_vs_3bet", "threebet_rate": round(st.threebet_rate, 3)}
                if frac <= 0.06 and lg.can_raise:
                    return clamp_raise(lg, lg.max_raise_to)
                if frac <= 0.18 and lg.can_call:
                    return Action.call()
                return give_up(lg)
        # 3) steal wider when the remaining blinds fold too often
        if not raises and not calls and obs.position in ("CO", "BTN", "SB"):
            blinds = [s for s in obs.seats if s.position in ("SB", "BB") and s.seat != obs.seat and not s.folded]
            stats = [self.model.get(s.player_id) for s in blinds]
            known = [st for st in stats if st and st.vs_steal_opps >= MIN_OBS]
            if known and len(known) == len(blinds) and min(st.fold_to_steal for st in known) >= 0.75:
                self.last_info = {"method": "adaptive_steal", "min_fold_to_steal": round(min(st.fold_to_steal for st in known), 3)}
                if frac <= self.steal_wide_pct and lg.can_raise:
                    return clamp_raise(lg, int(2.2 * obs.big_blind))
        return None
