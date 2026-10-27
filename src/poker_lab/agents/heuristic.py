"""Rule-based baseline: Chen preflop score + made-hand strength postflop."""

from __future__ import annotations

from poker_lab.agents.base import Agent, clamp_raise, give_up, passive
from poker_lab.domain.actions import Action, Street
from poker_lab.domain.observation import Observation
from poker_lab.engine.evaluator import PAIR, TWO_PAIR, category_of, evaluate
from poker_lab.strategy.preflop import chen_score

OPEN_THRESHOLD = {"UTG": 9, "UTG1": 9, "UTG2": 9, "MP": 8, "LJ": 8, "HJ": 8, "CO": 7, "BTN": 6, "SB": 7, "BB": 7}


def _board_only_category(board: tuple[int, ...]) -> int:
    if len(board) >= 5:
        return category_of(evaluate(list(board)))
    counts: dict[int, int] = {}
    for c in board:
        counts[c >> 2] = counts.get(c >> 2, 0) + 1
    m = sorted(counts.values(), reverse=True)
    if m[0] == 4:
        return 7
    if m[0] == 3:
        return 3
    if m[0] == 2:
        return TWO_PAIR if len(m) > 1 and m[1] == 2 else PAIR
    return 0


def made_hand_level(hole: tuple[int, int], board: tuple[int, ...]) -> int:
    """0 = nothing, 1 = weak pair/board pair, 2 = pair improved by hole cards, 3 = two pair or better from hole."""
    if len(board) < 3:
        return 0
    full = evaluate([*hole, *board])
    cat = category_of(full)
    uses_hole = _board_only_category(board) < cat
    if cat >= TWO_PAIR and uses_hole:
        return 3
    if cat >= PAIR and uses_hole:
        board_ranks = sorted((c >> 2 for c in board), reverse=True)
        hole_ranks = [c >> 2 for c in hole]
        top = board_ranks[0]
        if hole_ranks[0] == hole_ranks[1] and hole_ranks[0] > top:
            return 3  # overpair counts as strong
        if top in hole_ranks:
            return 2
        return 1
    return 0


class HeuristicAgent(Agent):
    algorithm = "heuristic"

    def __init__(
        self,
        *args: object,
        bluff_freq: float = 0.08,
        tightness: int = 0,
        aggression: float = 0.5,
        stickiness: float = 1.0,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.bluff_freq = bluff_freq
        self.tightness = tightness  # added to every preflop Chen threshold (+ = tighter)
        self.aggression = aggression  # bet/raise frequency with medium hands
        self.stickiness = stickiness  # multiplies postflop call thresholds (> 1 = calls more)

    def config(self) -> dict[str, object]:
        return {
            **super().config(),
            "bluff_freq": self.bluff_freq,
            "tightness": self.tightness,
            "aggression": self.aggression,
            "stickiness": self.stickiness,
        }

    def act(self, obs: Observation) -> Action:
        lg = obs.legal
        bb = obs.big_blind
        if obs.street is Street.PREFLOP:
            score = chen_score(obs.hole_cards)
            eff_bb = obs.effective_stack / bb
            self.last_info = {"method": "chen_preflop", "chen": score, "effective_bb": round(eff_bb, 2)}
            if eff_bb <= 12:
                push = (8 if obs.current_bet <= bb else 10) + self.tightness
                if score >= push:
                    return clamp_raise(lg, lg.max_raise_to) if lg.can_raise else passive(lg)
                return give_up(lg)
            unopened = obs.current_bet <= bb
            if unopened:
                if score >= OPEN_THRESHOLD.get(obs.position, 8) + self.tightness:
                    return clamp_raise(lg, int(2.5 * bb))
                if lg.can_check:
                    return Action.check()
                if obs.position == "SB" and score >= 6 + self.tightness:
                    return Action.call()
                return Action.fold()
            if score >= 12 + self.tightness:
                return clamp_raise(lg, 3 * obs.current_bet)
            if score >= 9 + self.tightness and obs.to_call <= 0.15 * obs.stack * self.stickiness:
                return Action.call()
            return give_up(lg)

        level = made_hand_level(obs.hole_cards, obs.board)
        pot = obs.pot
        self.last_info = {"method": "made_hand_level", "level": level}
        if level == 3:
            return clamp_raise(lg, obs.current_bet + int(pot * 0.66)) if lg.can_raise else passive(lg)
        if level == 2:
            if lg.can_check:
                if self.rng.random() < self.aggression and lg.can_raise:
                    return clamp_raise(lg, int(pot * 0.5))
                return Action.check()
            if lg.can_raise and self.rng.random() < self.aggression * 0.3:
                return clamp_raise(lg, obs.current_bet * 3)
            return Action.call() if obs.to_call <= pot * 0.6 * self.stickiness else Action.fold()
        if level == 1:
            if lg.can_check:
                return Action.check()
            return Action.call() if obs.to_call <= pot * 0.25 * self.stickiness else Action.fold()
        if lg.can_check:
            if lg.can_raise and self.rng.random() < self.bluff_freq:
                return clamp_raise(lg, int(pot * 0.5))
            return Action.check()
        if self.stickiness >= 2.0 and obs.to_call <= pot * 0.15 * self.stickiness:
            return Action.call()  # calling-station behaviour: floats with nothing
        return Action.fold()
