-- engine/db/tax_schema.sql
-- Schema for Tax and Accounting Engine

CREATE TABLE IF NOT EXISTS tax_raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    account_id TEXT,
    event_type TEXT NOT NULL,
    binance_event_id TEXT UNIQUE,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_time TIMESTAMP NOT NULL,
    raw_json TEXT NOT NULL,
    payload_hash TEXT
);

CREATE TABLE IF NOT EXISTS tax_ledger_entries (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TIMESTAMP NOT NULL,
    timestamp_local TIMESTAMP,
    asset TEXT NOT NULL,
    quantity REAL NOT NULL,
    direction TEXT NOT NULL, -- BUY, SELL, FEE, TRANSFER
    transaction_type TEXT NOT NULL,
    fiat_value_eur REAL,
    price_eur REAL,
    fee_asset TEXT,
    fee_quantity REAL,
    fee_eur REAL,
    exchange TEXT,
    symbol TEXT,
    order_id TEXT,
    trade_id TEXT,
    source_event_id INTEGER,
    is_internal_transfer BOOLEAN DEFAULT 0,
    wallet_from TEXT,
    wallet_to TEXT,
    tx_hash TEXT,
    FOREIGN KEY(source_event_id) REFERENCES tax_raw_events(id)
);

CREATE TABLE IF NOT EXISTS tax_lots (
    lot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    acquisition_timestamp TIMESTAMP NOT NULL,
    quantity_original REAL NOT NULL,
    quantity_remaining REAL NOT NULL,
    acquisition_cost_eur REAL NOT NULL,
    acquisition_fee_eur REAL NOT NULL,
    wallet TEXT,
    method TEXT NOT NULL, -- FIFO, LIFO, etc.
    source_ledger_id INTEGER,
    FOREIGN KEY(source_ledger_id) REFERENCES tax_ledger_entries(ledger_id)
);

CREATE TABLE IF NOT EXISTS tax_disposals (
    disposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset TEXT NOT NULL,
    disposal_timestamp TIMESTAMP NOT NULL,
    quantity REAL NOT NULL,
    sale_value_eur REAL NOT NULL,
    sale_fee_eur REAL NOT NULL,
    acquisition_lot_id INTEGER NOT NULL,
    acquisition_timestamp TIMESTAMP NOT NULL,
    acquisition_cost_eur REAL NOT NULL,
    holding_period_days INTEGER NOT NULL,
    holding_period_seconds INTEGER NOT NULL,
    gain_loss_eur REAL NOT NULL,
    tax_category TEXT,
    tax_year INTEGER NOT NULL,
    method_used TEXT NOT NULL,
    FOREIGN KEY(acquisition_lot_id) REFERENCES tax_lots(lot_id)
);

CREATE TABLE IF NOT EXISTS tax_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_year INTEGER NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_gains_eur REAL,
    total_losses_eur REAL,
    net_eur REAL,
    method TEXT,
    exchange TEXT,
    manifest_json TEXT
);
