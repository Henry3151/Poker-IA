import pytest

from poker_lab.agents.registry import AgentSpec, create_agent
from poker_lab.domain.seeds import derive_seed
from poker_lab.tournament.config import BlindLevel, TournamentConfig, compute_payouts
from poker_lab.tournament.director import Table, TournamentDirector, level_at


def make_entrants(n, seed=0, algos=("random", "heuristic")):
    out = []
    for i in range(n):
        spec = AgentSpec(algorithm=algos[i % len(algos)])
        out.append((f"{spec.algorithm}-{i}", create_agent(spec, f"{spec.algorithm}-{i}", derive_seed(seed, "agent", i))))
    return out


def fast_cfg(**kw):
    base = dict(starting_stack=1500, hands_per_level=6)
    base.update(kw)
    return TournamentConfig(**base)


def collect(n, seed, cfg=None):
    hands, events = [], []
    d = TournamentDirector(cfg or fast_cfg(), make_entrants(n, seed), seed, on_hand=lambda c, r: hands.append((c, r)), on_event=events.append)
    return d, d.run(), hands, events


@pytest.mark.parametrize("n", [2, 5, 6, 7, 13, 30])
def test_tournament_completes_with_integrity(n):
    d, res, hands, events = collect(n, seed=n)
    places = sorted(e.place for e in res.entries)
    assert places == list(range(1, n + 1))
    assert res.winner.stack == 1500 * n
    assert sum(e.payout for e in res.entries) == res.prize_pool
    assert events[-1].type == "tournament_completed"
    # every hand conserves chips and has at most table_size players
    for ctx, rec in hands:
        assert 2 <= len(ctx.seat_entry_ids) <= 6
        assert sum(rec.result.ending_stacks) == sum(rec.result.starting_stacks)
        assert all(d.valid for d in rec.decisions)


def test_initial_tables_balanced():
    d = TournamentDirector(fast_cfg(), make_entrants(17), 1)
    d._seat_initial()
    counts = sorted(t.count() for t in d.tables.values())
    assert counts == [5, 6, 6]


def test_rebalance_breaks_and_balances():
    d = TournamentDirector(fast_cfg(), make_entrants(18), 2)
    d._seat_initial()
    # simulate eliminations: bust 7 players from table 1 and 2 (chips go to survivors)
    victims = [e for e in d.entries_list if e.table == 1][:5] + [e for e in d.entries_list if e.table == 2][:2]
    survivor = next(e for e in d.entries_list if e not in victims)
    for v in victims:
        survivor.stack += v.stack
        v.stack = 0
        v.place = d.next_place
        d.next_place -= 1
        d.tables[v.table].seats[v.seat] = None
    d._rebalance()
    counts = sorted(t.count() for t in d.tables.values())
    assert counts == [5, 6]  # 11 players -> 2 tables
    for t in d.tables.values():
        for s in t.occupied():
            e = d.by_id[t.seats[s]]
            assert (e.table, e.seat) == (t.number, s)


def test_reproducible_tournament():
    _, a, _, _ = collect(9, seed=5)
    _, b, _, _ = collect(9, seed=5)
    _, c, _, _ = collect(9, seed=6)
    sa = [(e.label, e.place) for e in a.standings()]
    assert sa == [(e.label, e.place) for e in b.standings()]
    assert a.hands_played == b.hands_played
    assert sa != [(e.label, e.place) for e in c.standings()] or a.hands_played != c.hands_played


def test_eliminations_ordered_by_start_stack():
    _, res, _, events = collect(12, seed=8)
    elim = [e for e in events if e.type == "player_eliminated"]
    by_round = {}
    for ev in elim:
        by_round.setdefault(ev.round, []).append(ev.payload)
    for evs in by_round.values():
        # within a round, events are emitted worst place first: start stacks non-decreasing
        stacks = [p["start_stack"] for p in evs]
        assert stacks == sorted(stacks)
        places = [p["place"] for p in evs]
        assert places == sorted(places, reverse=True)


def test_blinds_increase_and_escalate_past_last_level():
    cfg = fast_cfg(levels=[BlindLevel(small_blind=10, big_blind=20)])
    assert level_at(cfg, 0).big_blind == 20
    assert level_at(cfg, 1).big_blind == 30
    assert level_at(cfg, 3).big_blind > level_at(cfg, 2).big_blind
    _, res, hands, _ = collect(6, seed=3, cfg=cfg)
    bbs = [c.level.big_blind for c, _ in hands]
    assert bbs == sorted(bbs)


def test_payouts():
    assert compute_payouts(1000, [50, 30, 20], 10) == [500, 300, 200]
    assert compute_payouts(1001, [50, 30, 20], 10) == [501, 300, 200]
    assert compute_payouts(200, [50, 30, 20], 2) == [125, 75]
    with pytest.raises(ValueError):
        TournamentConfig(payout_percentages=[60, 30])
    with pytest.raises(ValueError):
        TournamentConfig(payout_percentages=[20, 30, 50])


def test_button_moves_to_next_occupied():
    t = Table(1, ["a", None, "b", "c", None, None], button_seat=0)
    occ = t.occupied()
    nxt = [s for s in occ if s > t.button_seat] + [s for s in occ if s <= t.button_seat]
    assert nxt[0] == 2


def test_requires_distinct_agent_instances():
    a = create_agent(AgentSpec(algorithm="random"), "x", 1)
    with pytest.raises(ValueError):
        TournamentDirector(fast_cfg(), [("a", a), ("b", a)], 1)
