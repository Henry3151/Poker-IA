-- 0002_financials_evaluation (ADDITIVE ONLY: new tables, new nullable/defaulted columns, views, backfill).
-- Nothing is dropped or rewritten. Down-migration: docs/MIGRATIONS.md (restore the verified backup).

CREATE TABLE evaluation_runs (
    evaluation_run_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    protocol_json TEXT NOT NULL CHECK (json_valid(protocol_json)),
    code_version TEXT NOT NULL,
    seed INTEGER NOT NULL CHECK (seed >= 0),
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
    report_artifact_id TEXT REFERENCES artifacts(artifact_id),
    started_at TEXT NOT NULL,
    completed_at TEXT
);

-- Tournament economics (simulated units, never real money in this phase).
ALTER TABLE tournaments ADD COLUMN fee_per_entry INTEGER NOT NULL DEFAULT 0 CHECK (fee_per_entry >= 0);
ALTER TABLE tournaments ADD COLUMN reentry_levels INTEGER NOT NULL DEFAULT 0 CHECK (reentry_levels >= 0);
ALTER TABLE tournaments ADD COLUMN max_entries_per_player INTEGER NOT NULL DEFAULT 1 CHECK (max_entries_per_player >= 1);
ALTER TABLE tournaments ADD COLUMN total_entries INTEGER;
ALTER TABLE tournaments ADD COLUMN evaluation_run_id TEXT REFERENCES evaluation_runs(evaluation_run_id);
ALTER TABLE tournaments ADD COLUMN scenario_label TEXT;

ALTER TABLE tournament_entries ADD COLUMN entries_count INTEGER NOT NULL DEFAULT 1 CHECK (entries_count >= 1);
ALTER TABLE tournament_entries ADD COLUMN role TEXT NOT NULL DEFAULT 'field' CHECK (role IN ('hero','field'));

ALTER TABLE hands ADD COLUMN phase TEXT CHECK (phase IS NULL OR phase IN ('early','middle','bubble','itm','final_table','finished'));
ALTER TABLE hands ADD COLUMN players_remaining INTEGER;



-- Single source of truth for money flows. Signed from the player's perspective:
-- buy-ins and fees are negative, payouts positive. One row per (entry, kind, sequence):
-- the UNIQUE idempotency key makes double counting of re-entries/fees impossible.
CREATE TABLE financial_ledger (
    ledger_id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    entry_id TEXT NOT NULL REFERENCES tournament_entries(entry_id) ON DELETE CASCADE,
    agent_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    kind TEXT NOT NULL CHECK (kind IN ('buy_in','fee','payout')),
    entry_number INTEGER NOT NULL CHECK (entry_number >= 1),
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'SIM' CHECK (currency = 'SIM'),
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    CHECK ((kind IN ('buy_in','fee') AND amount <= 0) OR (kind = 'payout' AND amount >= 0))
);
CREATE INDEX ix_ledger_entry ON financial_ledger(entry_id);
CREATE INDEX ix_ledger_tournament ON financial_ledger(tournament_id);
CREATE INDEX ix_ledger_agent ON financial_ledger(agent_version_id);

CREATE TABLE entry_reentries (
    tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    entry_id TEXT NOT NULL REFERENCES tournament_entries(entry_id) ON DELETE CASCADE,
    entry_number INTEGER NOT NULL CHECK (entry_number >= 2),
    round INTEGER NOT NULL,
    level INTEGER NOT NULL,
    busted_hand_id TEXT REFERENCES hands(hand_id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (entry_id, entry_number)
);

-- Offline, per-decision analysis computed ONLY from what the agent could see at decision time
-- (own cards, board, public state). Approximations are labelled in equity_basis.
CREATE TABLE decision_metrics (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(decision_id) ON DELETE CASCADE,
    phase TEXT,
    stack_bucket TEXT NOT NULL,
    effective_bb REAL NOT NULL,
    spr REAL,
    pot_odds REAL NOT NULL,
    pot_type TEXT NOT NULL CHECK (pot_type IN ('unopened','limped','single_raised','three_bet_plus','postflop_heads_up','postflop_multiway')),
    players_in_pot INTEGER NOT NULL,
    outs INTEGER,
    outs_p_next REAL,
    equity REAL CHECK (equity IS NULL OR equity BETWEEN 0 AND 1),
    equity_basis TEXT NOT NULL,
    equity_stderr REAL,
    ev_call_chips REAL,
    breakeven_fold_equity REAL,
    icm_breakeven_equity REAL,
    chip_breakeven_equity REAL,
    field_profile TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX ix_dm_phase ON decision_metrics(phase);
CREATE INDEX ix_dm_bucket ON decision_metrics(stack_bucket);

CREATE INDEX ix_tournaments_eval ON tournaments(evaluation_run_id);
CREATE INDEX ix_hands_phase ON hands(phase);

-- Backfill ledger for tournaments recorded before 0002 (buy-in from tournaments.buy_in, fee 0).
INSERT INTO financial_ledger(ledger_id, tournament_id, entry_id, agent_version_id, kind, entry_number, amount, idempotency_key, created_at)
SELECT lower(hex(randomblob(16))), e.tournament_id, e.entry_id, e.agent_version_id, 'buy_in', 1, -t.buy_in,
       e.tournament_id || ':' || e.entry_id || ':buy_in:1', COALESCE(t.completed_at, t.started_at, '1970-01-01T00:00:00Z')
FROM tournament_entries e JOIN tournaments t ON t.tournament_id = e.tournament_id
WHERE t.status = 'completed';

INSERT INTO financial_ledger(ledger_id, tournament_id, entry_id, agent_version_id, kind, entry_number, amount, idempotency_key, created_at)
SELECT lower(hex(randomblob(16))), e.tournament_id, e.entry_id, e.agent_version_id, 'payout', 1, e.simulated_payout,
       e.tournament_id || ':' || e.entry_id || ':payout:1', COALESCE(t.completed_at, t.started_at, '1970-01-01T00:00:00Z')
FROM tournament_entries e JOIN tournaments t ON t.tournament_id = e.tournament_id
WHERE t.status = 'completed';

UPDATE tournaments SET total_entries = entrant_count WHERE total_entries IS NULL AND status = 'completed';

-- Per-entry financials derived from the ledger (documented in docs/FINANCIAL_METRICS.md).
CREATE VIEW v_entry_financials AS
SELECT e.entry_id,
       e.tournament_id,
       e.agent_version_id,
       e.participant_label,
       e.role,
       e.final_place,
       e.entries_count,
       -COALESCE(SUM(CASE WHEN l.kind = 'buy_in' THEN l.amount END), 0) AS buy_ins_total,
       -COALESCE(SUM(CASE WHEN l.kind = 'fee' THEN l.amount END), 0) AS fees_total,
       COALESCE(SUM(CASE WHEN l.kind = 'payout' THEN l.amount END), 0) AS payout,
       COALESCE(SUM(l.amount), 0) AS net_profit,
       CASE WHEN COALESCE(SUM(CASE WHEN l.kind IN ('buy_in','fee') THEN -l.amount END), 0) > 0
            THEN 1.0 * COALESCE(SUM(l.amount), 0) / SUM(CASE WHEN l.kind IN ('buy_in','fee') THEN -l.amount END)
       END AS roi,
       CASE WHEN COALESCE(SUM(CASE WHEN l.kind = 'payout' THEN l.amount END), 0) > 0 THEN 1 ELSE 0 END AS itm
FROM tournament_entries e
LEFT JOIN financial_ledger l ON l.entry_id = e.entry_id
GROUP BY e.entry_id;
