import json

import pytest

from poker_lab.agents.policy_agent import PolicyAgent
from poker_lab.agents.random_agent import RandomAgent
from poker_lab.application.hand_runner import play_hand, play_session
from poker_lab.application.training_service import run_pushfold_training
from poker_lab.domain.actions import Action
from poker_lab.engine.hand import HandEngine
from poker_lab.persistence import db as dbmod
from poker_lab.training.checkpoints import load_checkpoint, save_checkpoint
from poker_lab.training.games import KuhnPoker, PushFoldGame
from poker_lab.training.mccfr import ExternalSamplingMCCFR, exploitability, policy_value
from poker_lab.training.pushfold_tables import build_table, save_table
from poker_lab.training.pushfold_trainer import train_pushfold
from tests.engine.helpers import make_deck


@pytest.fixture(scope="session")
def small_table(tmp_path_factory):
    t = build_table(samples=16, seed=3)
    p = tmp_path_factory.mktemp("tables") / "t.json"
    save_table(t, p)
    return t


def test_kuhn_converges_to_known_value():
    g = KuhnPoker()
    m = ExternalSamplingMCCFR(g, seed=11)
    m.run(30000)
    avg = m.average_strategy()
    assert exploitability(g, avg) < 0.01
    assert abs(policy_value(g, avg) - (-1 / 18)) < 0.01


def test_best_response_of_uniform_kuhn_is_large():
    g = KuhnPoker()
    assert exploitability(g, {}) > 0.3  # uniform random is very exploitable


def test_mccfr_reproducible_and_resumable():
    g = KuhnPoker()
    a = ExternalSamplingMCCFR(g, seed=5)
    a.run(2000)
    b = ExternalSamplingMCCFR(g, seed=5)
    b.run(1000)
    b2 = ExternalSamplingMCCFR(g, seed=5, state=b.state.from_json(json.loads(json.dumps(b.state.to_json()))))
    b2.run(1000)
    assert a.state.regret_sum == b2.state.regret_sum
    assert a.state.strategy_sum == b2.state.strategy_sum


def test_pushfold_game_utilities(small_table):
    g = PushFoldGame(10, small_table["classes"], small_table["equity"], small_table["weights"])
    o = g.sample_chance(__import__("random").Random(1))
    assert g.utility(("f",), o) == -0.5
    assert g.utility(("p", "f"), o) == 1.0
    assert -10 <= g.utility(("p", "c"), o) <= 10
    assert abs(sum(p for p, _ in g.chance_outcomes()) - 1) < 1e-9


def test_pushfold_training_sane_and_reproducible(small_table, tmp_path):
    s1 = train_pushfold(small_table, 6000, seed=9, stacks=[6.0, 20.0])
    s2 = train_pushfold(small_table, 6000, seed=9, stacks=[6.0, 20.0], evaluate=False)
    assert s1.checkpoint.policy.sb_push == s2.checkpoint.policy.sb_push
    m = s1.metrics["per_stack"]
    assert m["6"]["push_pct_combos"] > m["20"]["push_pct_combos"]
    assert s1.checkpoint.policy.sb_push["6"]["AA"] > 0.95
    assert s1.checkpoint.policy.bb_call["20"]["72o"] < 0.1
    assert m["6"]["exploitability_bb"] < 0.2
    # resume: 3000 + 3000 == 6000
    half = train_pushfold(small_table, 3000, seed=9, stacks=[6.0, 20.0], evaluate=False)
    rest = train_pushfold(small_table, 3000, seed=9, resume=half.checkpoint, evaluate=False)
    assert rest.checkpoint.policy.sb_push == s1.checkpoint.policy.sb_push
    assert rest.checkpoint.iterations == {"6": 6000, "20": 6000}


def test_checkpoint_roundtrip_and_tamper_detection(small_table, tmp_path):
    s = train_pushfold(small_table, 500, seed=1, stacks=[10.0], evaluate=False)
    p = tmp_path / "ck.json"
    meta = save_checkpoint(s.checkpoint, p)
    assert len(meta["sha256"]) == 64
    assert load_checkpoint(p).policy == s.checkpoint.policy
    p.write_text(p.read_text().replace('"seed":1', '"seed":2'))
    with pytest.raises(ValueError, match="checksum"):
        load_checkpoint(p)
    bad = json.loads(s.checkpoint.model_dump_json())
    bad["policy"]["sb_push"]["10"]["AA"] = 1.5
    from poker_lab.training.checkpoints import Checkpoint

    with pytest.raises(ValueError):
        Checkpoint.model_validate(bad)


def _policy(small_table):
    s = train_pushfold(small_table, 3000, seed=4, stacks=[5.0, 10.0, 15.0, 20.0], evaluate=False)
    return s.checkpoint


def test_policy_agent_uses_trained_policy_only_in_scope(small_table):
    ck = _policy(small_table)
    # heads-up 10bb: SB first-in uses the trained policy
    agent = PolicyAgent(ck, "pf", seed=1, fallback_samples=30)
    e = HandEngine([("pf", 1000), ("r", 1000)], 0, 50, 100, deck=make_deck(["AsAd", "7c2d"]))
    obs = e.observation(0)
    act = agent.act(obs)
    assert agent.last_info["path"] == "trained_policy" and agent.last_info["hand_class"] == "AA"
    assert act.amount == 1000
    # BB facing the shove
    e.apply(0, act)
    bb = PolicyAgent(ck, "pf2", seed=2, fallback_samples=30)
    bb.act(e.observation(1))
    assert bb.last_info["situation"] == "bb_vs_shove"
    # deep stacks -> fallback
    deep = HandEngine([("pf", 100000), ("r", 100000)], 0, 50, 100, seed=1)
    agent.act(deep.observation(0))
    assert agent.last_info["path"] == "equity_fallback"
    # 6-max UTG -> fallback
    six = HandEngine([(f"p{i}", 1000) for i in range(6)], 0, 50, 100, seed=2)
    agent.act(six.observation(six.to_act))
    assert agent.last_info["path"] == "equity_fallback"
    # 6-max folded to SB -> trained policy
    six2 = HandEngine([(f"p{i}", 1000) for i in range(6)], 0, 50, 100, seed=3)
    for seat in (3, 4, 5, 0):
        six2.apply(seat, Action.fold())
    agent.act(six2.observation(1))
    assert agent.last_info["path"] == "trained_policy"


def test_policy_agent_plays_legal_hu_session(small_table):
    ck = _policy(small_table)
    agents = [PolicyAgent(ck, "pf", seed=1, fallback_samples=30), RandomAgent("r", seed=2)]
    res = play_session(agents, 200, starting_stack=1000, small_blind=50, big_blind=100, seed=5)
    assert res.invalid_actions == 0
    used = []
    for h in range(20):
        e = HandEngine([("pf", 1000), ("r", 1000)], h % 2, 50, 100, seed=h)
        rec = play_hand(e, agents)
        used += [d.info.get("path") for d in rec.decisions if d.player_id == "pf"]
    assert "trained_policy" in used


def test_training_service_records_run(tmp_path, small_table, monkeypatch):
    import poker_lab.application.training_service as ts

    monkeypatch.setattr(ts, "get_or_build", lambda path, samples, seed: (save_table(small_table, path), small_table)[1])
    conn = dbmod.open_db(tmp_path / "t.db")
    out = run_pushfold_training(conn, iterations=800, seed=3, version_label="t1", artifacts_dir=tmp_path / "art", stacks=[10.0])
    run = conn.execute("SELECT * FROM training_runs WHERE training_run_id=?", (out["training_run_id"],)).fetchone()
    assert run["status"] == "completed" and run["iteration_end"] == 800 and run["peak_memory_mb"] > 0
    av = conn.execute("SELECT * FROM agent_versions WHERE agent_version_id=?", (out["agent_version_id"],)).fetchone()
    assert av["status"] == "candidate" and av["checkpoint_sha256"] == out["sha256"]
    with pytest.raises(FileExistsError):
        run_pushfold_training(conn, iterations=10, seed=3, version_label="t1", artifacts_dir=tmp_path / "art", stacks=[10.0])
    child = run_pushfold_training(
        conn, iterations=200, seed=3, version_label="t2", artifacts_dir=tmp_path / "art", resume_path=out["checkpoint_path"]
    )
    av2 = conn.execute("SELECT * FROM agent_versions WHERE agent_version_id=?", (child["agent_version_id"],)).fetchone()
    assert av2["parent_version_id"] == out["agent_version_id"]
