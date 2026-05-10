-- =============================================================
-- Hedge Fund Control Tower — SQLite-Compatible Schema
-- Apply with: python -m engine.db.db
-- (PostgreSQL: swap SERIAL→SERIAL, TEXT→JSONB, remove compat comments)
-- =============================================================

-- ─────────────────────────────────────────────────────────────
-- MARKET DATA
-- ─────────────────────────────────────────────────────────────

-- Core OHLCV price data — all prices stored in EUR
CREATE TABLE IF NOT EXISTS prices (
    date         TEXT        NOT NULL,
    ticker       TEXT        NOT NULL,
    open         REAL,
    high         REAL,
    low          REAL,
    close        REAL        NOT NULL,
    volume       INTEGER,
    adj_close    REAL,
    currency     TEXT        DEFAULT 'EUR',
    source       TEXT        DEFAULT 'polygon',
    PRIMARY KEY (date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices (ticker, date);

-- ─────────────────────────────────────────────────────────────
-- FEATURE STORE
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS feature_store (
    date          TEXT        NOT NULL,
    ticker        TEXT        NOT NULL,
    feature_name  TEXT        NOT NULL,
    feature_value REAL        NOT NULL,
    computed_at   TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker, feature_name)
);

CREATE INDEX IF NOT EXISTS idx_feature_store_ticker ON feature_store (ticker, date);
CREATE INDEX IF NOT EXISTS idx_feature_store_name   ON feature_store (feature_name, date);

-- ─────────────────────────────────────────────────────────────
-- ALPHA MODEL OUTPUTS
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS signals (
    date             TEXT        NOT NULL,
    ticker           TEXT        NOT NULL,
    model_name       TEXT        NOT NULL,
    expected_return  REAL,
    confidence       REAL,
    raw_score        REAL,
    ic_21d           REAL,
    ic_63d           REAL,
    ic_252d          REAL,
    computed_at      TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker, model_name)
);

CREATE INDEX IF NOT EXISTS idx_signals_model ON signals (model_name, date);

-- Rolling IC for live-approval gating
CREATE TABLE IF NOT EXISTS alpha_signals (
    date        TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    signal      REAL,
    forward_ret REAL,
    ic_21d      REAL,
    ic_63d      REAL,
    ic_252d     REAL,
    PRIMARY KEY (date, model_name, ticker)
);

-- ─────────────────────────────────────────────────────────────
-- OPTIMIZER & PORTFOLIO CONSTRUCTION
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_outputs (
    date             TEXT        NOT NULL,
    ticker           TEXT        NOT NULL,
    suggested_weight REAL,
    current_weight   REAL,
    delta_weight     REAL,
    expected_return  REAL,
    bl_return        REAL,
    computed_at      TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);

-- ─────────────────────────────────────────────────────────────
-- PORTFOLIO STATE
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS positions_history (
    id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    date        TEXT        NOT NULL,
    ticker      TEXT        NOT NULL,
    quantity    REAL,
    price       REAL,
    value_eur   REAL,
    weight      REAL,
    recorded_at TEXT        DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_positions_date   ON positions_history (date, ticker);
CREATE INDEX IF NOT EXISTS idx_positions_ticker ON positions_history (ticker, date);

CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    date         TEXT        NOT NULL,
    ticker       TEXT        NOT NULL,
    action       TEXT        NOT NULL,
    quantity     REAL,
    price_eur    REAL,
    value_eur    REAL,
    slippage_pct REAL        DEFAULT 0.0005,
    fee_eur      REAL        DEFAULT 1.0,
    source       TEXT        DEFAULT 'manual',
    notes        TEXT,
    executed_at  TEXT        DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cash_history (
    id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    date        TEXT        NOT NULL,
    cash_eur    REAL        NOT NULL,
    event_type  TEXT,
    notes       TEXT,
    recorded_at TEXT        DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────
-- RISK
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS risk_metrics (
    date          TEXT        NOT NULL,
    metric_name   TEXT        NOT NULL,
    metric_value  REAL,
    computed_at   TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, metric_name)
);

CREATE TABLE IF NOT EXISTS risk_events (
    id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    date        TEXT        NOT NULL,
    event_type  TEXT,
    ticker      TEXT,
    detail      TEXT,
    logged_at   TEXT        DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────
-- HUMAN-IN-THE-LOOP
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS override_log (
    id               INTEGER     PRIMARY KEY AUTOINCREMENT,
    date             TEXT        NOT NULL,
    ticker           TEXT,
    model_suggestion REAL,
    action_taken     REAL,
    reason           TEXT,
    outcome_30d      REAL,
    outcome_90d      REAL,
    outcome_correct  INTEGER,    -- 1=True, 0=False (SQLite has no BOOLEAN)
    logged_at        TEXT        DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────
-- STRATEGY SCREENS
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS divergence_labels (
    id               INTEGER     PRIMARY KEY AUTOINCREMENT,
    ticker           TEXT        NOT NULL,
    etf_reference    TEXT        NOT NULL,
    detected_at      TEXT        NOT NULL,
    labeled_at       TEXT,
    window_days      INTEGER     DEFAULT 28,
    etf_return_pct   REAL,
    stock_return_pct REAL,
    divergence_pct   REAL,
    scenario_label   INTEGER,
    confidence       TEXT,
    notes            TEXT,
    checklist_answers TEXT,      -- JSON stored as TEXT
    outcome_30d      REAL,
    outcome_90d      REAL,
    outcome_correct  INTEGER,
    UNIQUE (ticker, etf_reference, detected_at)
);

CREATE INDEX IF NOT EXISTS idx_div_labels_unlabeled ON divergence_labels (detected_at);

CREATE TABLE IF NOT EXISTS laggard_screen_results (
    id            INTEGER     PRIMARY KEY AUTOINCREMENT,
    screen_date   TEXT        NOT NULL,
    ticker        TEXT        NOT NULL,
    sector        TEXT,
    period_return REAL,
    relative_rank REAL,
    catch_up_gap  REAL,
    conviction    TEXT,
    notes         TEXT,
    logged_at     TEXT        DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────
-- RECONCILIATION & DATA QUALITY
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS reconciliation_log (
    id              INTEGER     PRIMARY KEY AUTOINCREMENT,
    reconciled_at   TEXT        DEFAULT (datetime('now')),
    positions_match INTEGER,
    cash_match      INTEGER,
    discrepancies   TEXT,       -- JSON as TEXT
    action_taken    TEXT
);

CREATE TABLE IF NOT EXISTS data_validation_log (
    id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    date        TEXT,
    ticker      TEXT,
    issue_type  TEXT,
    raw_value   REAL,
    action      TEXT,
    detail      TEXT,
    logged_at   TEXT        DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────────────────
-- SCHEDULER / PIPELINE AUDIT
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    run_date     TEXT        NOT NULL,
    step_name    TEXT        NOT NULL,
    status       TEXT,
    duration_sec REAL,
    error_msg    TEXT,
    started_at   TEXT        DEFAULT (datetime('now'))
);
