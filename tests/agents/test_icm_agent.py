from poker_lab.agents.equity_agent import EquityAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.tournament.config import TournamentConfig
from poker_lab.tournament.director import TournamentDirector


def test_icm_path_is_used_near_the_money_and_stays_legal():
    infos = []
    hands = []

    def on_hand(ctx, rec):
        hands.append(rec)
        infos.extend(d.info for d in rec.decisions if d.player_id.startswith("icm"))

    ents = [(f"icm{i}", EquityAgent(f"icm{i}", seed=i, samples=40, icm=True, adaptive=True)) for i in range(4)]
    ents += [(f"r{i}", RandomAgent(f"r{i}", seed=10 + i)) for i in range(4)]
    for seed in range(4):
        for _, a in ents:
            a.reseed(seed)
        TournamentDirector(TournamentConfig(starting_stack=1500, hands_per_level=5), ents, seed, on_hand=on_hand).run()
    icm = [i for i in infos if "icm" in i]
    assert icm, "ICM decisions expected on the bubble / final table"
    for i in icm:
        assert 0 <= i["icm"]["icm_breakeven_equity"] <= 1
        assert i["phase"] in ("bubble", "itm", "final_table")
    assert all(d.valid for h in hands for d in h.decisions)
