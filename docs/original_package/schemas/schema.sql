PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hypothesis TEXT,
    algorithm TEXT NOT NULL,
    code_version TEXT NOT NULL,
    config_json TEXT NOT NULL,
    seed INTEGER,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_versions (
    agent_version_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    version_label TEXT NOT NULL,
    checkpoint_path TEXT,
    checkpoint_sha256 TEXT,
    config_json TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL,
    UNIQUE(name, version_label)
);

CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    config_json TEXT NOT NULL,
    seed INTEGER,
    entrant_count INTEGER NOT NULL,
    table_size INTEGER NOT NULL DEFAULT 6,
    status TEXT NOT NULL DEFAULT 'created',
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

CREATE TABLE IF NOT EXISTS tournament_entries (
    entry_id TEXT PRIMARY KEY,
    tournament_id TEXT NOT NULL,
    agent_version_id TEXT NOT NULL,
    participant_label TEXT NOT NULL,
    final_place INTEGER,
    final_stack INTEGER,
    simulated_payout REAL,
    eliminated_at TEXT,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (agent_version_id) REFERENCES agent_versions(agent_version_id)
);

CREATE TABLE IF NOT EXISTS hands (
    hand_id TEXT PRIMARY KEY,
    tournament_id TEXT,
    table_number INTEGER,
    hand_number INTEGER NOT NULL,
    button_seat INTEGER,
    final_street TEXT,
    board_json TEXT,
    pot_total INTEGER,
    result_json TEXT,
    seed INTEGER,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    agent_version_id TEXT NOT NULL,
    participant_label TEXT NOT NULL,
    street TEXT NOT NULL,
    position TEXT,
    observation_json TEXT NOT NULL,
    legal_actions_json TEXT NOT NULL,
    chosen_action_json TEXT NOT NULL,
    action_valid INTEGER NOT NULL,
    equity_estimate REAL,
    equity_method TEXT,
    equity_samples INTEGER,
    pot_odds REAL,
    decision_latency_ms REAL,
    outcome_delta_chips INTEGER,
    review_category TEXT,
    review_confidence REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (hand_id) REFERENCES hands(hand_id),
    FOREIGN KEY (agent_version_id) REFERENCES agent_versions(agent_version_id)
);

CREATE TABLE IF NOT EXISTS action_events (
    event_id TEXT PRIMARY KEY,
    hand_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    public_payload_json TEXT NOT NULL,
    audit_payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (hand_id) REFERENCES hands(hand_id),
    UNIQUE(hand_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS training_runs (
    training_run_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    agent_version_id TEXT,
    iteration_start INTEGER,
    iteration_end INTEGER,
    episodes INTEGER,
    elapsed_seconds REAL,
    peak_memory_mb REAL,
    throughput_per_second REAL,
    metrics_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id),
    FOREIGN KEY (agent_version_id) REFERENCES agent_versions(agent_version_id)
);

CREATE TABLE IF NOT EXISTS notes (
    note_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'observation',
    status TEXT NOT NULL DEFAULT 'open',
    tags_json TEXT,
    experiment_id TEXT,
    tournament_id TEXT,
    hand_id TEXT,
    decision_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (hand_id) REFERENCES hands(hand_id),
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tournaments_experiment ON tournaments(experiment_id);
CREATE INDEX IF NOT EXISTS idx_hands_tournament ON hands(tournament_id);
CREATE INDEX IF NOT EXISTS idx_decisions_hand ON decisions(hand_id);
CREATE INDEX IF NOT EXISTS idx_decisions_agent ON decisions(agent_version_id);
CREATE INDEX IF NOT EXISTS idx_decisions_review ON decisions(review_category);
CREATE INDEX IF NOT EXISTS idx_notes_tournament ON notes(tournament_id);
CREATE INDEX IF NOT EXISTS idx_notes_hand ON notes(hand_id);
CREATE INDEX IF NOT EXISTS idx_training_experiment ON training_runs(experiment_id);
