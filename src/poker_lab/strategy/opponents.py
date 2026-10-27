"""Opponent statistics from *public* actions only (VPIP, PFR, aggression factor).

Fed with observations: each observation carries the public history of the current hand,
so the model incrementally counts actions it has not yet seen. It never uses hidden
cards. Profiles are only assigned after ``min_hands`` observed hands; before that the
profile is ``unknown`` (insufficient evidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from poker_lab.domain.observation import Observation


@dataclass
class PlayerStats:
    hands: int = 0
    vpip_hands: int = 0
    pfr_hands: int = 0
    aggressive_actions: int = 0  # bets + raises postflop
    calls: int = 0  # calls postflop

    @property
    def vpip(self) -> float:
        return self.vpip_hands / self.hands if self.hands else 0.0

    @property
    def pfr(self) -> float:
        return self.pfr_hands / self.hands if self.hands else 0.0

    @property
    def aggression_factor(self) -> float:
        return self.aggressive_actions / self.calls if self.calls else float(self.aggressive_actions)


def classify(stats: PlayerStats, min_hands: int = 30) -> str:
    if stats.hands < min_hands:
        return "unknown"
    loose = stats.vpip > 0.35
    aggressive = stats.aggression_factor > 1.5 or stats.pfr > 0.6 * max(stats.vpip, 1e-9)
    if loose and aggressive:
        return "loose_aggressive"
    if loose:
        return "loose_passive"
    if aggressive:
        return "tight_aggressive"
    return "tight_passive"


@dataclass
class OpponentModel:
    min_hands: int = 30
    stats: dict[str, PlayerStats] = field(default_factory=dict)
    _seen: dict[str, int] = field(default_factory=dict)  # hand_id -> actions processed
    _flags: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    _hands_order: list[str] = field(default_factory=list)

    def observe(self, obs: Observation) -> None:
        hid = obs.hand_id
        if hid not in self._seen:
            self._seen[hid] = 0
            self._hands_order.append(hid)
            for s in obs.seats:
                if s.player_id != obs.player_id:
                    self.stats.setdefault(s.player_id, PlayerStats()).hands += 1
            if len(self._hands_order) > 5000:  # bound memory
                old = self._hands_order.pop(0)
                self._seen.pop(old, None)
        seat_to_pid = {s.seat: s.player_id for s in obs.seats}
        for a in obs.history[self._seen[hid] :]:
            pid = seat_to_pid.get(a.seat)
            if pid is None or pid == obs.player_id:
                continue
            st = self.stats.setdefault(pid, PlayerStats())
            flags = self._flags.setdefault((hid, pid), set())
            if a.street == "preflop":
                if a.kind in ("call", "raise", "bet") and "vpip" not in flags:
                    flags.add("vpip")
                    st.vpip_hands += 1
                if a.kind == "raise" and "pfr" not in flags:
                    flags.add("pfr")
                    st.pfr_hands += 1
            else:
                if a.kind in ("bet", "raise"):
                    st.aggressive_actions += 1
                elif a.kind == "call":
                    st.calls += 1
        self._seen[hid] = len(obs.history)

    def profile(self, player_id: str) -> str:
        st = self.stats.get(player_id)
        return classify(st, self.min_hands) if st else "unknown"
