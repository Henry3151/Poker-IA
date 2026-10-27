"""Run ONE Open Poker session with the experimental cash policy ``cash6max-v0`` (virtual chips only).

The MTT champion (hybrid-v1) is NOT used here; see ``policy.py``.

    set OPEN_POKER_ENABLED=1 and OPEN_POKER_API_KEY in the environment (never in files), then:
    python -m poker_lab.integrations.openpoker.run --max-hands 30 --buy-in 2000

Stop at any time by creating the kill-switch file (default artifacts/openpoker/STOP) or Ctrl+C.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from poker_lab.integrations.openpoker.client import OpenPokerSession, websocket_connector
from poker_lab.integrations.openpoker.config import IntegrationDisabled, load_config
from poker_lab.integrations.openpoker.policy import CASH_POLICY_LABEL, cash_policy_spec, create_cash_policy
from poker_lab.integrations.openpoker.recorder import OnlineRecorder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-hands", type=int, default=30)
    ap.add_argument("--buy-in", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        cfg = load_config(max_hands=args.max_hands, buy_in=args.buy_in)
    except IntegrationDisabled as exc:
        print(f"[disabled] {exc}")
        return 2
    if cfg.kill_switch.exists():
        print(f"[stopped] kill switch present: {cfg.kill_switch}")
        return 3
    agent = create_cash_policy(args.seed)
    rec = OnlineRecorder(cfg.db_path, CASH_POLICY_LABEL, {"spec": cash_policy_spec().model_dump(), "seed": args.seed})
    session = OpenPokerSession(cfg, agent, lambda: websocket_connector(cfg), rec, agent_label=CASH_POLICY_LABEL)
    stats = asyncio.run(session.run())
    print(json.dumps(stats.__dict__, indent=1))
    print(f"session_id={rec.session_id} db={cfg.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
