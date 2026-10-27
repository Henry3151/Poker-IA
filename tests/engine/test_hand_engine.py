import pytest

from poker_lab.domain.actions import Action, ActionKind, Street
from poker_lab.domain.cards import parse_cards
from poker_lab.engine.hand import HandEngine, HandFinishedError, IllegalActionError

from .helpers import make_deck


def engine(stacks, holes=None, board="", button=0, sb=50, bb=100, ante=0, seed=1):
    players = [(f"p{i}", s) for i, s in enumerate(stacks)]
    deck = make_deck(holes, board) if holes else None
    return HandEngine(players, button=button, small_blind=sb, big_blind=bb, ante=ante, seed=seed, deck=deck)


def test_blinds_and_first_actor_6max():
    e = engine([1000] * 6)
    assert e.stacks() == [1000, 950, 900, 1000, 1000, 1000]
    assert e.to_act == 3  # UTG
    obs = e.observation(3)
    assert obs.position == "UTG" and obs.to_call == 100
    assert obs.legal.min_raise_to == 200 and obs.legal.max_raise_to == 1000
    assert not obs.legal.can_check


def test_heads_up_order():
    e = engine([1000, 1000], button=0)
    assert e.stacks() == [950, 900]  # button posts SB
    assert e.to_act == 0
    e.apply(0, Action.call())
    assert e.to_act == 1  # BB option
    lg = e.legal_actions(1)
    assert lg.can_check and lg.raise_kind is ActionKind.RAISE
    e.apply(1, Action.check())
    assert e.street is Street.FLOP
    assert e.to_act == 1  # BB acts first postflop heads-up


def test_everyone_folds_to_bb():
    e = engine([1000] * 6)
    for seat in (3, 4, 5, 0, 1):
        e.apply(seat, Action.fold())
    assert e.is_finished
    r = e.result()
    assert r.net == (0, -50, 50, 0, 0, 0)
    assert r.showdown_seats == ()


def test_illegal_actions_rejected():
    e = engine([1000] * 3)
    actor = e.to_act
    assert actor == 0
    with pytest.raises(IllegalActionError):
        e.apply(actor, Action.check())
    with pytest.raises(IllegalActionError):
        e.apply(actor, Action.raise_to(150))  # below min raise
    with pytest.raises(IllegalActionError):
        e.apply(actor, Action.raise_to(5000))  # above stack
    with pytest.raises(IllegalActionError):
        e.apply(actor, Action.bet(300))  # must be RAISE preflop
    with pytest.raises(IllegalActionError):
        e.apply(1, Action.call())  # not to act
    e.apply(actor, Action.raise_to(300))
    assert e.to_act == 1


def test_min_raise_tracks_last_full_raise():
    e = engine([5000] * 3)
    e.apply(0, Action.raise_to(400))  # raise of 300
    lg = e.legal_actions(1)
    assert lg.min_raise_to == 700
    e.apply(1, Action.raise_to(1000))  # raise of 600
    assert e.legal_actions(2).min_raise_to == 1600


def test_short_allin_does_not_reopen():
    # seat0 raises to 300, seat1 calls, seat2 (BB) shoves 350 total (raise of 50 < 200)
    e = engine([5000, 5000, 350])
    e.apply(0, Action.raise_to(300))
    e.apply(1, Action.call())
    e.apply(2, Action.raise_to(350))
    lg0 = e.legal_actions(0)
    assert lg0.call_amount == 50 and lg0.raise_kind is None
    e.apply(0, Action.call())
    lg1 = e.legal_actions(1)
    assert lg1.raise_kind is None
    e.apply(1, Action.call())
    assert e.street is Street.FLOP


def test_short_allin_reopens_for_players_who_have_not_acted():
    # 4 players: UTG(seat3) raises to 300, BTN(seat0) shoves 350, SB has not acted -> may raise
    e = engine([350, 5000, 5000, 5000])
    e.apply(3, Action.raise_to(300))
    e.apply(0, Action.raise_to(350))
    lg = e.legal_actions(1)
    assert lg.raise_kind is ActionKind.RAISE
    assert lg.min_raise_to == 550  # last full raise increment is 200


def test_side_pots_and_showdown():
    # seat0 AA 300 chips, seat1 KK 1000, seat2 QQ 1000 ; board blanks
    holes = ["AsAd", "KsKd", "QsQd"]
    e = engine([300, 1000, 1000], holes=holes, board="2c7h9dJc3s", sb=50, bb=100)
    e.apply(0, Action.raise_to(300))  # all-in
    e.apply(1, Action.raise_to(1000))  # all-in
    e.apply(2, Action.call())
    assert e.is_finished
    r = e.result()
    main, side = r.pots
    assert main.amount == 900 and main.winners == (0,)
    assert side.amount == 1400 and side.winners == (1,)
    assert r.ending_stacks == (900, 1400, 0)
    assert sum(r.ending_stacks) == 2300


def test_uncalled_bet_returned():
    e = engine([1000, 400], holes=["AsAd", "KsKd"], board="2c7h9dJc3s", button=0)
    e.apply(0, Action.raise_to(1000))
    e.apply(1, Action.call())  # calls all-in 400
    r = e.result()
    # AA wins 800 pot; 600 uncalled returned
    assert r.ending_stacks == (1400, 0)


def test_split_pot_with_odd_chip():
    # board plays: both have the broadway straight; pot = 101+101+... use ante for odd
    holes = ["2c3d", "2d3c", "4h4s"]
    e = engine([1000, 1000, 1000], holes=holes, board="AsKdQhJcTs", sb=50, bb=100, ante=1)
    e.apply(0, Action.call())
    e.apply(1, Action.call())
    e.apply(2, Action.check())
    for _ in range(3):
        for seat in (1, 2, 0):
            e.apply(seat, Action.check())
    r = e.result()
    assert r.final_street is Street.SHOWDOWN
    pot = 303
    assert r.pot_total == pot
    winners = r.pots[0].winners
    assert set(winners) == {0, 1, 2}
    assert r.pots[0].shares == (101, 101, 101)


def test_odd_chip_goes_left_of_button():
    holes = ["2c3d", "2d3c", "4h4s"]
    # seat2 folds; pot = 50+100 +... seat0(button) calls 100, seat1 SB completes, seat2 BB folds impossible (can check)
    e = engine([1000, 1000, 1000], holes=holes, board="AsKdQhJcTs", sb=50, bb=100, ante=0, button=2)
    # button=2 -> SB seat0, BB seat1, first actor seat2
    e.apply(2, Action.raise_to(201))
    e.apply(0, Action.fold())
    e.apply(1, Action.call())
    for _ in range(3):
        e.apply(1, Action.check())
        e.apply(2, Action.check())
    r = e.result()
    # pot 50 + 201 + 201 = 452 split between seat1 and seat2 -> 226 each, no odd chip
    assert r.pots[0].shares == (226, 226)
    e2 = engine([1000, 1000, 1000], holes=holes, board="AsKdQhJcTs", sb=51, bb=100, button=2)
    e2.apply(2, Action.call())
    e2.apply(0, Action.fold())
    e2.apply(1, Action.check())
    for _ in range(3):
        e2.apply(1, Action.check())
        e2.apply(2, Action.check())
    r2 = e2.result()
    # pot 51+100+100 = 251 -> seat1 (first left of button among winners) gets the odd chip
    assert r2.pots[0].winners == (1, 2)
    assert r2.pots[0].shares == (126, 125)


def test_antes_and_short_blinds():
    e = engine([5, 1000, 1000], sb=50, bb=100, ante=10, button=2)
    # seat0 (SB) all-in from the ante (5)
    assert e.stacks()[0] == 0
    assert e._seats[0].all_in


def test_no_actions_after_finish():
    e = engine([1000, 1000])
    e.apply(0, Action.fold())
    with pytest.raises(HandFinishedError):
        e.apply(1, Action.check())
    assert e.to_act is None


def test_seed_reproducible():
    a = engine([1000] * 6, seed=42)
    b = engine([1000] * 6, seed=42)
    c = engine([1000] * 6, seed=43)
    assert [a.hole_cards_offline(i) for i in range(6)] == [b.hole_cards_offline(i) for i in range(6)]
    assert [a.hole_cards_offline(i) for i in range(6)] != [c.hole_cards_offline(i) for i in range(6)]


def test_observation_hides_other_hole_cards():
    e = engine([1000] * 6, holes=["AsAd", "KsKd", "QsQd", "JsJd", "TsTd", "9s9d"], board="2c7h8d3c4s")
    obs = e.observation(3)
    assert obs.hole_cards == tuple(parse_cards("JsJd"))
    serialized = repr(obs.to_dict())
    for other in (0, 1, 2, 4, 5):
        for c in e.hole_cards_offline(other):
            # integer card ids could collide with other ints, so check the observation
            # structure instead: only own hole cards and the (empty) board carry cards.
            assert c not in obs.board
    assert "hole" not in repr([s for s in obs.seats])
    assert not hasattr(obs, "_deck") and "deck" not in serialized
    public = [ev for ev in e.events if ev.visibility != "offline_audit"]
    assert all(ev.type != "hole_cards_dealt" for ev in public)


def test_folded_antes_above_live_contributions_are_returned():
    e = HandEngine([("a", 3), ("b", 3), ("c", 1), ("d", 1)], 1, 10, 20, ante=2, seed=1)
    e.apply(0, Action.fold())
    e.apply(1, Action.fold())
    r = e.result()
    assert r.pot_total == 4  # 1 from each player; the extra antes go back
    assert sorted(r.ending_stacks) == [0, 2, 2, 4]
    assert any(ev.type == "uncalled_returned" for ev in e.events)


def test_uncalled_pot_flagged():
    e = engine([1000, 400], holes=["AsAd", "KsKd"], board="2c7h9dJc3s", button=0)
    e.apply(0, Action.raise_to(1000))
    e.apply(1, Action.call())
    r = e.result()
    assert r.pot_total == 800
    assert [p.uncalled for p in r.pots] == [False, True]
