-- 0001_initial: Poker AI Tournament Lab schema (SQLite).
-- Conventions: TEXT UUID ids, UTC ISO-8601 timestamps, integer chips, JSON in *_json columns.
-- Decisions/events are append-only; notes are editable (updated_at).

CREATE TABLE experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hypothesis TEXT,
    algorithm TEXT NOT NULL,
    code_version TEXT NOT NULL,
    config_json TEXT NOT NULL CHECK (json_valid(config_json)),
    seed INTEGER CHECK (seed IS NULL OR seed >= 0),
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','running','completed','failed')),
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('checkpoint','report','export','equity_table','database_backup','other')),
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    metadata_json TEXT CHECK (metadata_json IS NULL OR json_valid(metadata_json)),
    created_at TEXT NOT NULL
);

CREATE TABLE agent_versions (
    agent_version_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                     -- lineage name, e.g. 'pushfold'
    algorithm TEXT NOT NULL CHECK (algorithm IN ('random','heuristic','equity','policy')),
    version_label TEXT NOT NULL,
    checkpoint_artifact_id TEXT REFERENCES artifacts(artifact_id),
    checkpoint_sha256 TEXT,
    config_json TEXT CHECK (config_json IS NULL OR json_valid(config_json)),
    code_version TEXT,
    parent_version_id TEXT REFERENCES agent_versions(agent_version_id),
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('baseline','candidate','challenger','champion','retired','rejected')),
    created_at TEXT NOT NULL,
    UNIQUE (name, version_label)
);
-- at most one champion per lineage
CREATE UNIQUE INDEX ux_agent_versions_champion ON agent_versions(name) WHERE status = 'champion';

CREATE TABLE tournaments (
    tournament_id TEXT PRIMARY KEY,
    experiment_id TEXT REFERENCES experiments(experiment_id),
    name TEXT NOT NULL,
    config_json TEXT NOT NULL CHECK (json_valid(config_json)),
    seed INTEGER NOT NULL CHECK (seed >= 0),
    entrant_count INTEGER NOT NULL CHECK (entrant_count >= 2),
    table_size INTEGER NOT NULL DEFAULT 6 CHECK (table_size BETWEEN 2 AND 10),
    starting_stack INTEGER NOT NULL CHECK (starting_stack > 0),
    buy_in INTEGER NOT NULL DEFAULT 0 CHECK (buy_in >= 0),
    prize_pool INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created','running','completed','failed')),
    hands_played INTEGER NOT NULL DEFAULT 0,
    rounds_played INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE tournament_entries (
    entry_id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    agent_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    participant_label TEXT NOT NULL,
    starting_table INTEGER,
    starting_seat INTEGER,
    final_place INTEGER CHECK (final_place IS NULL OR final_place >= 1),
    final_stack INTEGER CHECK (final_stack IS NULL OR final_stack >= 0),
    simulated_payout INTEGER NOT NULL DEFAULT 0 CHECK (simulated_payout >= 0),
    hands_played INTEGER NOT NULL DEFAULT 0,
    eliminated_round INTEGER,
    eliminated_hand_id TEXT,
    UNIQUE (tournament_id, participant_label)
);
CREATE UNIQUE INDEX ux_entries_place ON tournament_entries(tournament_id, final_place) WHERE final_place IS NOT NULL;

CREATE TABLE tournament_events (
    event_id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    round INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('tournament_started','level_started','player_moved','table_broken','player_eliminated','tournament_completed')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL,
    UNIQUE (tournament_id, sequence_number)
);

CREATE TABLE hands (
    hand_id TEXT PRIMARY KEY,
    tournament_id TEXT REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    experiment_id TEXT REFERENCES experiments(experiment_id),
    table_number INTEGER,
    hand_number INTEGER NOT NULL,
    round INTEGER,
    level_index INTEGER,
    small_blind INTEGER NOT NULL,
    big_blind INTEGER NOT NULL,
    ante INTEGER NOT NULL DEFAULT 0,
    button_seat INTEGER NOT NULL,
    player_count INTEGER NOT NULL CHECK (player_count BETWEEN 2 AND 10),
    final_street TEXT NOT NULL CHECK (final_street IN ('preflop','flop','turn','river','showdown')),
    board_json TEXT NOT NULL CHECK (json_valid(board_json)),
    pot_total INTEGER NOT NULL CHECK (pot_total >= 0),
    chips_conserved INTEGER NOT NULL CHECK (chips_conserved IN (0,1)),
    seed INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

-- Public per-seat outcome of a hand (no private cards here).
CREATE TABLE hand_players (
    hand_id TEXT NOT NULL REFERENCES hands(hand_id) ON DELETE CASCADE,
    seat INTEGER NOT NULL,
    entry_id TEXT REFERENCES tournament_entries(entry_id),
    agent_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    participant_label TEXT NOT NULL,
    position TEXT NOT NULL,
    starting_stack INTEGER NOT NULL,
    ending_stack INTEGER NOT NULL CHECK (ending_stack >= 0),
    net_chips INTEGER NOT NULL,
    went_to_showdown INTEGER NOT NULL CHECK (went_to_showdown IN (0,1)),
    won_at_showdown INTEGER NOT NULL CHECK (won_at_showdown IN (0,1)),
    eliminated INTEGER NOT NULL CHECK (eliminated IN (0,1)),
    allin_equity REAL,                      -- offline estimate when all-in before river, else NULL
    allin_ev_chips REAL,                    -- offline chip EV of the all-in, else NULL
    PRIMARY KEY (hand_id, seat)
);

-- Offline audit truth: every player's hole cards. NEVER read during a decision.
CREATE TABLE offline_hole_cards (
    hand_id TEXT NOT NULL REFERENCES hands(hand_id) ON DELETE CASCADE,
    seat INTEGER NOT NULL,
    hole_cards_json TEXT NOT NULL CHECK (json_valid(hole_cards_json)),
    shown_at_showdown INTEGER NOT NULL CHECK (shown_at_showdown IN (0,1)),
    PRIMARY KEY (hand_id, seat)
);

CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL REFERENCES hands(hand_id) ON DELETE CASCADE,
    seq_in_hand INTEGER NOT NULL,
    agent_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    participant_label TEXT NOT NULL,
    seat INTEGER NOT NULL,
    street TEXT NOT NULL CHECK (street IN ('preflop','flop','turn','river')),
    position TEXT NOT NULL,
    own_hole_cards_json TEXT NOT NULL CHECK (json_valid(own_hole_cards_json)),
    board_json TEXT NOT NULL CHECK (json_valid(board_json)),
    pot_before INTEGER NOT NULL,
    to_call INTEGER NOT NULL,
    stack_before INTEGER NOT NULL,
    effective_stack INTEGER NOT NULL,
    big_blind INTEGER NOT NULL,
    observation_json TEXT NOT NULL CHECK (json_valid(observation_json)),  -- exactly what the agent saw
    legal_actions_json TEXT NOT NULL CHECK (json_valid(legal_actions_json)),
    requested_action_json TEXT CHECK (requested_action_json IS NULL OR json_valid(requested_action_json)),
    applied_action_json TEXT NOT NULL CHECK (json_valid(applied_action_json)),
    action_type TEXT NOT NULL CHECK (action_type IN ('fold','check','call','bet','raise')),
    action_amount INTEGER,
    chips_added INTEGER NOT NULL DEFAULT 0,
    action_valid INTEGER NOT NULL CHECK (action_valid IN (0,1)),
    fallback_applied INTEGER NOT NULL CHECK (fallback_applied IN (0,1)),
    issue TEXT CHECK (issue IS NULL OR issue IN ('invalid_action','agent_exception','timeout')),
    error_message TEXT,
    equity_estimate REAL CHECK (equity_estimate IS NULL OR equity_estimate BETWEEN 0 AND 1),
    equity_method TEXT,
    equity_samples INTEGER,
    equity_stderr REAL,
    pot_odds REAL,
    agent_info_json TEXT CHECK (agent_info_json IS NULL OR json_valid(agent_info_json)),
    decision_latency_ms REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (hand_id, seq_in_hand)
);

CREATE TABLE action_events (
    event_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL REFERENCES hands(hand_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('public_observation','private_agent_observation','offline_audit')),
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    created_at TEXT NOT NULL,
    UNIQUE (hand_id, sequence_number)
);

CREATE TABLE training_runs (
    training_run_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
    agent_version_id TEXT REFERENCES agent_versions(agent_version_id),
    algorithm TEXT NOT NULL,
    game TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed')),
    seed INTEGER NOT NULL,
    config_json TEXT NOT NULL CHECK (json_valid(config_json)),
    iteration_start INTEGER NOT NULL DEFAULT 0,
    iteration_end INTEGER,
    elapsed_seconds REAL,
    peak_memory_mb REAL,
    throughput_per_second REAL,
    checkpoint_artifact_id TEXT REFERENCES artifacts(artifact_id),
    metrics_json TEXT CHECK (metrics_json IS NULL OR json_valid(metrics_json)),
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE evaluations (
    evaluation_id TEXT PRIMARY KEY,
    experiment_id TEXT REFERENCES experiments(experiment_id),
    champion_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    challenger_version_id TEXT NOT NULL REFERENCES agent_versions(agent_version_id),
    suite_json TEXT NOT NULL CHECK (json_valid(suite_json)),
    metric TEXT NOT NULL,
    n_samples INTEGER NOT NULL,
    champion_mean REAL,
    challenger_mean REAL,
    diff_mean REAL,
    ci_low REAL,
    ci_high REAL,
    confidence_level REAL NOT NULL,
    invalid_actions INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL CHECK (decision IN ('promote','keep_champion','inconclusive','challenger_failed')),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Explanations of results: always category + evidence + confidence/limitation + origin.
CREATE TABLE explanations (
    explanation_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK (scope IN ('tournament_entry','hand','decision')),
    tournament_id TEXT REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    entry_id TEXT REFERENCES tournament_entries(entry_id) ON DELETE CASCADE,
    hand_id TEXT REFERENCES hands(hand_id) ON DELETE CASCADE,
    decision_id TEXT REFERENCES decisions(decision_id) ON DELETE CASCADE,
    agent_version_id TEXT REFERENCES agent_versions(agent_version_id),
    category TEXT NOT NULL CHECK (category IN ('decision_quality','variance','opponent_adaptation','tournament_dynamics','execution_issue','rule_or_engine_bug','insufficient_evidence')),
    origin TEXT NOT NULL CHECK (origin IN ('rule','automatic_calculation','human_review')),
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN ('fact','estimate','hypothesis','review')),
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json)),
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    limitations TEXT NOT NULL,
    reviewer TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_issues (
    issue_id TEXT PRIMARY KEY,
    issue_type TEXT NOT NULL CHECK (issue_type IN ('invalid_action','agent_exception','timeout','chip_inconsistency','missing_data','reconciliation_mismatch','engine_error')),
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error','critical')),
    tournament_id TEXT REFERENCES tournaments(tournament_id) ON DELETE CASCADE,
    hand_id TEXT REFERENCES hands(hand_id) ON DELETE CASCADE,
    decision_id TEXT REFERENCES decisions(decision_id) ON DELETE CASCADE,
    detail_json TEXT NOT NULL CHECK (json_valid(detail_json)),
    created_at TEXT NOT NULL
);

CREATE TABLE notes (
    note_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body_markdown TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'observation' CHECK (category IN ('observation','hypothesis','hand_review','bug','experiment_log','decision_review')),
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','low','medium','high')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','resolved')),
    tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
    author TEXT NOT NULL DEFAULT 'local',
    experiment_id TEXT REFERENCES experiments(experiment_id) ON DELETE SET NULL,
    agent_version_id TEXT REFERENCES agent_versions(agent_version_id) ON DELETE SET NULL,
    tournament_id TEXT REFERENCES tournaments(tournament_id) ON DELETE SET NULL,
    hand_id TEXT REFERENCES hands(hand_id) ON DELETE SET NULL,
    decision_id TEXT REFERENCES decisions(decision_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_tournaments_experiment ON tournaments(experiment_id);
CREATE INDEX ix_tournaments_created ON tournaments(started_at);
CREATE INDEX ix_entries_tournament ON tournament_entries(tournament_id);
CREATE INDEX ix_entries_agent ON tournament_entries(agent_version_id);
CREATE INDEX ix_tevents_tournament ON tournament_events(tournament_id);
CREATE INDEX ix_hands_tournament ON hands(tournament_id);
CREATE INDEX ix_hands_experiment ON hands(experiment_id);
CREATE INDEX ix_hands_completed ON hands(completed_at);
CREATE INDEX ix_hand_players_agent ON hand_players(agent_version_id);
CREATE INDEX ix_hand_players_entry ON hand_players(entry_id);
CREATE INDEX ix_decisions_hand ON decisions(hand_id);
CREATE INDEX ix_decisions_agent ON decisions(agent_version_id);
CREATE INDEX ix_decisions_created ON decisions(created_at);
CREATE INDEX ix_decisions_issue ON decisions(issue) WHERE issue IS NOT NULL;
CREATE INDEX ix_action_events_hand ON action_events(hand_id);
CREATE INDEX ix_training_experiment ON training_runs(experiment_id);
CREATE INDEX ix_evaluations_challenger ON evaluations(challenger_version_id);
CREATE INDEX ix_explanations_tournament ON explanations(tournament_id);
CREATE INDEX ix_explanations_category ON explanations(category);
CREATE INDEX ix_explanations_entry ON explanations(entry_id);
CREATE INDEX ix_audit_tournament ON audit_issues(tournament_id);
CREATE INDEX ix_notes_tournament ON notes(tournament_id);
CREATE INDEX ix_notes_hand ON notes(hand_id);
CREATE INDEX ix_notes_decision ON notes(decision_id);
CREATE INDEX ix_notes_experiment ON notes(experiment_id);
