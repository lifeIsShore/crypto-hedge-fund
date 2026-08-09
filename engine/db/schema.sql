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
-- FX RATES  (Stream 1)
-- ─────────────────────────────────────────────────────────────

-- Daily FX rates used for currency conversion.
-- Stored separately so the dashboard can show raw FX history
-- and the feature store can pull rate-of-change as a macro signal.
-- pair examples: 'USDEUR', 'GBPEUR'
CREATE TABLE IF NOT EXISTS fx_rates (
    date        TEXT    NOT NULL,
    pair        TEXT    NOT NULL,   -- e.g. 'USDEUR'
    rate        REAL    NOT NULL,   -- EUR per 1 unit of foreign currency
    source      TEXT    DEFAULT 'yfinance',
    recorded_at TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (date, pair)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_pair ON fx_rates (pair, date);

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
    signal_breakdown TEXT,       -- I2: JSON, e.g. {"momentum": 58.0, "ml_model": 31.0}
    computed_at      TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);

-- ─────────────────────────────────────────────────────────────
-- PRICE TARGETS  (Stream 3)
-- ─────────────────────────────────────────────────────────────

-- Probabilistic price targets computed daily after portfolio construction.
-- All price values are in EUR. Used by the Risk/Strategy dashboard (Stream 4).
CREATE TABLE IF NOT EXISTS price_targets (
    date                TEXT    NOT NULL,
    ticker              TEXT    NOT NULL,
    current_price_eur   REAL,
    expected_21d_eur    REAL,   -- median of lognormal at t=21d
    target_1sigma_eur   REAL,   -- 84th percentile (upside target)
    stop_1sigma_eur     REAL,   -- 16th percentile (hard stop)
    stop_tight_eur      REAL,   -- 0.5σ stop (tight)
    resistance_ma50     REAL,
    resistance_ma200    REAL,
    resistance_bb_upper REAL,
    support_bb_lower    REAL,
    high_52w            REAL,
    low_52w             REAL,
    risk_reward_ratio   REAL,   -- (target - current) / (current - stop)
    up_proba            REAL,   -- ML up_proba_21d used
    vol_ann             REAL,   -- annualised vol used
    kelly_half          REAL,   -- Half-Kelly position size % (0-25)
    computed_at         TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_price_targets_ticker ON price_targets (ticker, date);

-- ─────────────────────────────────────────────────────────────
-- EARNINGS CALENDAR  (J4 — pre-earnings position throttle + PEAD trigger)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS earnings_calendar (
    ticker           TEXT NOT NULL,
    report_date      TEXT NOT NULL,
    report_time      TEXT,     -- 'bmo' (before open) / 'amc' (after close) / 'dmh'
    eps_estimate     REAL,
    revenue_estimate REAL,
    fetched_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, report_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings_calendar (report_date);

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
-- REGIME HISTORY  (Stream 5 — SQLite migration)
-- ─────────────────────────────────────────────────────────────

-- Replaces regime_history.csv. JOINable with signals and price_targets
-- for regime-stratified hit rate queries.
CREATE TABLE IF NOT EXISTS regime_history (
    date               TEXT    NOT NULL,
    region             TEXT    NOT NULL DEFAULT 'US',
    regime_risk        TEXT,   -- 'Risk-On' | 'Risk-Off' | 'Neutral'
    regime_rates       TEXT,   -- 'Easing'  | 'Tightening' | 'Neutral'
    regime_growth      TEXT,   -- 'Expansion' | 'Slowdown' | 'Contraction' | 'Recovery'
    regime_composite   TEXT,   -- e.g. 'RiskOn_Easing_Expansion'
    transition_warning INTEGER DEFAULT 0,
    ew_active_count    INTEGER DEFAULT 0,
    vix                REAL,
    yield_spread       REAL,
    hy_spread          REAL,
    fed_funds          REAL,
    computed_at        TEXT    DEFAULT (datetime('now')),
    PRIMARY KEY (date, region)
);

-- ─────────────────────────────────────────────────────────────
-- PEAD SETUPS  (Stream 5 — SQLite migration)
-- ─────────────────────────────────────────────────────────────

-- Replaces pead_setups.csv. JOINable with regime_history for
-- regime-stratified PEAD hit rate analysis.
CREATE TABLE IF NOT EXISTS pead_setups (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                TEXT    NOT NULL,
    earnings_date         TEXT    NOT NULL,
    entry_date            TEXT,
    direction             TEXT,   -- 'long' | 'short'
    pead_setup_quality    TEXT,
    surprise_pct          REAL,
    underreaction_flag    INTEGER DEFAULT 0,
    reaction_gap          REAL,
    drift_21d             REAL,
    drift_63d             REAL,
    outcome_label_correct INTEGER,
    regime_risk           TEXT,
    regime_growth         TEXT,
    regime_composite      TEXT,
    sector                TEXT,
    created_at            TEXT    DEFAULT (datetime('now')),
    UNIQUE(ticker, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_pead_setups_ticker ON pead_setups (ticker, earnings_date);

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

-- ─────────────────────────────────────────────────────────────
-- PERFORMANCE HISTORY  (daily portfolio value + returns)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS performance_history (
    date                  TEXT    PRIMARY KEY,
    portfolio_value_eur   REAL,
    cash_eur              REAL,
    invested_eur          REAL,
    benchmark_value_eur   REAL,   -- e.g. MSCI World ETF proxy
    daily_return_pct      REAL,
    cumulative_return_pct REAL,
    computed_at           TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_history (date);

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

-- ─────────────────────────────────────────────────────────────
-- PIPELINE LOGS  (structured logs readable by health.html)
-- Written by all pipeline scripts via log_pipeline_event().
-- Replaces reading flat .log files from disk.
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at   TEXT    DEFAULT (datetime('now')),
    level       TEXT    NOT NULL DEFAULT 'INFO',  -- INFO | WARNING | ERROR | CRITICAL
    step_name   TEXT,                              -- e.g. 'data_ingestion', 'ml_pipeline'
    message     TEXT    NOT NULL,
    detail      TEXT,                              -- optional JSON payload
    run_date    TEXT    DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_date  ON pipeline_logs (run_date, logged_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_logs_level ON pipeline_logs (level, logged_at DESC);

-- ─────────────────────────────────────────────────────────────
-- PORTFOLIO LAB
-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS saved_portfolios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    tickers     TEXT NOT NULL, -- JSON array of tickers
    weights     TEXT NOT NULL, -- JSON object of ticker -> weight
    objective   TEXT,
    metrics     TEXT,          -- JSON object of metrics
    saved_at    TEXT DEFAULT (datetime('now'))
);

