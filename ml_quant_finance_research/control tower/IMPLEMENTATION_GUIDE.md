# Hedge Fund System — Ultimate Implementation Guide
### Sprint-by-Sprint Build Plan from Current Codebase to Production Control Tower

---

## What You Already Have (Do Not Rebuild)

Before any sprint starts, understand your existing assets so you extend rather than duplicate them.

| Location | What exists | Status |
|---|---|---|
| `portfolio/src/math_optimizer.py` | SLSQP optimizer, 3 objectives (max Sharpe, min var, max return) | ✅ Working |
| `portfolio/src/rules_engine.py` | Trend filter (200MA), drift thresholds, trade signal generator | ✅ Working |
| `portfolio/src/config.py` | Full asset universe (100+ tickers), rebalance params, fee logic | ✅ Working |
| `portfolio/src/data_loader.py` | yfinance data fetching | ✅ Working — will be extended |
| `portfolio/backtest_portfolio.py` | Backtester | ✅ Working |
| `general_research/src/regime.py` | Composite regime engine (vol + corr compression, stress score) | ✅ Research-grade, promote to prod |
| `general_research/src/factor_model.py` | FF3 regression, full Black-Litterman implementation | ✅ Research-grade, promote to prod |
| `general_research/src/correlation.py` | Rolling corr, stability scores, tradeability scoring, lead-lag | ✅ Research-grade, promote to prod |
| `general_research/notebooks/` | 5 research notebooks (correlation, regime, factor, BL, lead-lag) | ✅ Keep as research layer |
| `quant_research/regime_engine/` | Standalone regime engine with DB | ✅ Will merge into main system |
| `quant_research/pead_engine/` | PEAD screener with regression model | ✅ Will become Alpha Model #4 |
| `ml_research/stock_ml_lab/` | ML pipeline with feature builder, evaluator, scenario engine | ✅ Will become Alpha Model #5 |

**The architecture your todos describe already exists in fragments across these folders. The sprints below connect, harden, and complete the system.**

---

## Project Structure After All Sprints Complete

```
hedge-fund/
├── portfolio/                        ← existing (extended)
│   └── src/
│       ├── config.py                 ← extended with new params
│       ├── data_loader.py            ← upgraded to multi-provider
│       ├── math_optimizer.py         ← upgraded with BL + constraints
│       ├── rules_engine.py           ← upgraded with regime integration
│       └── performance.py            ← existing
│
├── ml_quant_finance_research/        ← existing (research layer, untouched)
│
├── engine/                           ← NEW — production system
│   ├── data/
│   │   ├── ingestion.py              ← Sprint 1
│   │   ├── validation.py             ← Sprint 1
│   │   └── corporate_actions.py      ← Sprint 1
│   ├── features/
│   │   └── feature_store.py          ← Sprint 2
│   ├── alpha/
│   │   ├── momentum.py               ← Sprint 3
│   │   ├── mean_reversion.py         ← Sprint 3
│   │   ├── vol_timing.py             ← Sprint 3
│   │   ├── pead_alpha.py             ← Sprint 5 (wraps existing pead_engine)
│   │   └── ml_alpha.py               ← Sprint 5 (wraps existing ml_lab)
│   ├── portfolio/
│   │   ├── black_litterman.py        ← Sprint 4 (promotes factor_model.py)
│   │   └── optimizer.py              ← Sprint 4 (upgrades math_optimizer.py)
│   ├── risk/
│   │   ├── pre_trade.py              ← Sprint 5
│   │   └── post_trade.py             ← Sprint 5
│   ├── execution/
│   │   └── order_manager.py          ← Sprint 6
│   ├── reconciliation/
│   │   └── state_reconciler.py       ← Sprint 6
│   ├── screens/
│   │   ├── laggard_screen.py         ← Sprint 7
│   │   └── etf_divergence.py         ← Sprint 7
│   ├── db/
│   │   ├── schema.sql                ← Sprint 1
│   │   └── db.py                     ← Sprint 1
│   └── scheduler.py                  ← Sprint 8
│
├── dashboard/                        ← NEW — control tower UI
│   ├── app.py                        ← Sprint 8 (Streamlit)
│   ├── pages/
│   │   ├── overview.py
│   │   ├── rebalance.py
│   │   ├── risk.py
│   │   ├── models.py
│   │   ├── screens.py
│   │   └── divergence_labeler.py     ← Sprint 7
│   └── components/
│       ├── regime_gauge.py
│       └── stress_table.py
│
└── todos/                            ← existing (reference only)
```

---

## Sprint Overview

| Sprint | Focus | Weeks | Depends on |
|---|---|---|---|
| **Sprint 1** | Database + data pipeline | 1–2 | Nothing |
| **Sprint 2** | Feature store (promotes existing research code) | 2–3 | Sprint 1 |
| **Sprint 3** | Alpha models + IC tracking | 3–4 | Sprint 2 |
| **Sprint 4** | Black-Litterman + upgraded optimizer | 4–5 | Sprint 3 |
| **Sprint 5** | Risk engine + PEAD/ML alpha integration | 5–6 | Sprint 4 |
| **Sprint 6** | Execution engine + state reconciliation | 6–7 | Sprint 5 |
| **Sprint 7** | Strategy screens (laggard + ETF divergence) | 7–8 | Sprint 4 |
| **Sprint 8** | Dashboard + scheduler + alerts | 8–10 | All |

---

## Sprint 1 — Database & Data Pipeline

**Goal:** Replace yfinance-only, file-based data with a validated, PostgreSQL-backed pipeline with a fallback provider. Everything downstream depends on clean data here.

**What changes from current code:**
- `portfolio/src/data_loader.py` currently uses raw yfinance with a 30% anomaly gate. That gate stays but becomes part of a formal validation layer.
- Add Polygon.io (or Alpaca) as primary; yfinance becomes fallback.
- Replace any `ledger.csv` / `engine_state.json` files with DB tables.

---

### 1.1 Install dependencies

```bash
pip install psycopg2-binary sqlalchemy polygon-api-client asyncio aiohttp tenacity
```

For local Docker PostgreSQL:
```bash
docker run --name hedgefund-db -e POSTGRES_PASSWORD=yourpassword -e POSTGRES_DB=hedgefund -p 5432:5432 -d postgres:15
```

---

### 1.2 Create `engine/db/schema.sql`

```sql
-- Core price data
CREATE TABLE IF NOT EXISTS prices (
    date         DATE        NOT NULL,
    ticker       VARCHAR(20) NOT NULL,
    open         FLOAT,
    high         FLOAT,
    low          FLOAT,
    close        FLOAT       NOT NULL,
    volume       BIGINT,
    adj_close    FLOAT,
    source       VARCHAR(20) DEFAULT 'polygon',
    PRIMARY KEY (date, ticker)
);

-- Feature store (all computed signals)
CREATE TABLE IF NOT EXISTS feature_store (
    date          DATE        NOT NULL,
    ticker        VARCHAR(20) NOT NULL,
    feature_name  VARCHAR(60) NOT NULL,
    feature_value FLOAT       NOT NULL,
    computed_at   TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, ticker, feature_name)
);

-- Alpha model outputs
CREATE TABLE IF NOT EXISTS signals (
    date             DATE        NOT NULL,
    ticker           VARCHAR(20) NOT NULL,
    model_name       VARCHAR(40) NOT NULL,
    expected_return  FLOAT,
    confidence       FLOAT,
    raw_score        FLOAT,
    computed_at      TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, ticker, model_name)
);

-- Optimizer outputs
CREATE TABLE IF NOT EXISTS model_outputs (
    date             DATE        NOT NULL,
    ticker           VARCHAR(20) NOT NULL,
    suggested_weight FLOAT,
    current_weight   FLOAT,
    delta_weight     FLOAT,
    expected_return  FLOAT,
    bl_return        FLOAT,
    computed_at      TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, ticker)
);

-- All historical positions
CREATE TABLE IF NOT EXISTS positions_history (
    id           SERIAL      PRIMARY KEY,
    date         DATE        NOT NULL,
    ticker       VARCHAR(20) NOT NULL,
    quantity     FLOAT,
    price        FLOAT,
    value_eur    FLOAT,
    weight       FLOAT,
    recorded_at  TIMESTAMP   DEFAULT NOW()
);

-- Full trade log
CREATE TABLE IF NOT EXISTS trades (
    id             SERIAL      PRIMARY KEY,
    date           DATE        NOT NULL,
    ticker         VARCHAR(20) NOT NULL,
    action         VARCHAR(10) NOT NULL,   -- BUY / SELL
    quantity       FLOAT,
    price_eur      FLOAT,
    value_eur      FLOAT,
    slippage_pct   FLOAT       DEFAULT 0.0005,
    source         VARCHAR(20) DEFAULT 'manual',
    notes          TEXT,
    executed_at    TIMESTAMP   DEFAULT NOW()
);

-- Risk metrics (daily snapshot)
CREATE TABLE IF NOT EXISTS risk_metrics (
    date          DATE        NOT NULL,
    metric_name   VARCHAR(60) NOT NULL,
    metric_value  FLOAT,
    computed_at   TIMESTAMP   DEFAULT NOW(),
    PRIMARY KEY (date, metric_name)
);

-- Override log (human-in-the-loop)
CREATE TABLE IF NOT EXISTS override_log (
    id               SERIAL     PRIMARY KEY,
    date             DATE       NOT NULL,
    ticker           VARCHAR(20),
    model_suggestion FLOAT,
    action_taken     FLOAT,
    reason           TEXT,
    outcome_30d      FLOAT,
    outcome_90d      FLOAT,
    logged_at        TIMESTAMP  DEFAULT NOW()
);

-- Divergence labels (ETF divergence screen — ML training data)
CREATE TABLE IF NOT EXISTS divergence_labels (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker              VARCHAR(20) NOT NULL,
    etf_reference       VARCHAR(20) NOT NULL,
    detected_at         DATE        NOT NULL,
    labeled_at          TIMESTAMP,
    window_days         INTEGER     DEFAULT 28,
    etf_return_pct      FLOAT,
    stock_return_pct    FLOAT,
    divergence_pct      FLOAT,
    scenario_label      INTEGER,               -- 1/2/3/4
    confidence          VARCHAR(10),           -- low/medium/high
    notes               TEXT,
    checklist_answers   JSONB,
    outcome_30d         FLOAT,
    outcome_90d         FLOAT,
    outcome_correct     BOOLEAN
);

-- State reconciliation log
CREATE TABLE IF NOT EXISTS reconciliation_log (
    id              SERIAL     PRIMARY KEY,
    reconciled_at   TIMESTAMP  DEFAULT NOW(),
    positions_match BOOLEAN,
    cash_match      BOOLEAN,
    discrepancies   JSONB,
    action_taken    TEXT
);

-- Data validation events
CREATE TABLE IF NOT EXISTS data_validation_log (
    id          SERIAL     PRIMARY KEY,
    date        DATE,
    ticker      VARCHAR(20),
    issue_type  VARCHAR(40),   -- price_spike, missing_day, stale_data
    raw_value   FLOAT,
    action      VARCHAR(20),   -- rejected, flagged, auto_filled
    logged_at   TIMESTAMP  DEFAULT NOW()
);
```

---

### 1.3 Create `engine/db/db.py`

```python
# engine/db/db.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:yourpassword@localhost:5432/hedgefund"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

def execute_schema(schema_path: str = "engine/db/schema.sql"):
    with open(schema_path) as f:
        sql = f.read()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("Schema applied.")
```

---

### 1.4 Create `engine/data/ingestion.py`

This replaces raw yfinance calls with a validated, dual-source pipeline. Your existing `MAX_DAILY_MOVE_ANOMALY = 0.30` gate from `config.py` moves into `validation.py`.

```python
# engine/data/ingestion.py
import asyncio
import aiohttp
import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# ── Primary: Polygon.io ──────────────────────────────────────────────
POLYGON_API_KEY = "YOUR_POLYGON_KEY"   # set via env var in prod

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_polygon(session: aiohttp.ClientSession, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
    params = {"adjusted": "true", "sort": "asc", "apiKey": POLYGON_API_KEY}
    async with session.get(url, params=params) as resp:
        data = await resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Polygon returned no data for {ticker}")
    rows = [{"date": pd.Timestamp(r["t"], unit="ms").date(),
             "open": r["o"], "high": r["h"], "low": r["l"],
             "close": r["c"], "volume": r["v"], "adj_close": r["c"],
             "ticker": ticker, "source": "polygon"} for r in data["results"]]
    return pd.DataFrame(rows)

# ── Fallback: yfinance ────────────────────────────────────────────────
def fetch_yfinance(ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Existing yfinance logic — your current data_loader.py core."""
    raw = yf.download(ticker, start=from_date, end=to_date, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame()
    raw = raw.reset_index()
    raw.columns = [c.lower().replace(" ", "_") for c in raw.columns]
    raw["ticker"] = ticker
    raw["source"] = "yfinance"
    raw["adj_close"] = raw["close"]
    return raw[["date", "open", "high", "low", "close", "volume", "adj_close", "ticker", "source"]]

# ── Main orchestrator ─────────────────────────────────────────────────
async def fetch_all_async(tickers: list, from_date: str, to_date: str) -> pd.DataFrame:
    """Async multi-ticker fetch with per-ticker fallback."""
    frames = []
    async with aiohttp.ClientSession() as http_session:
        tasks = {ticker: fetch_polygon(http_session, ticker, from_date, to_date)
                 for ticker in tickers}
        for ticker, coro in tasks.items():
            try:
                df = await coro
                frames.append(df)
                logger.info(f"[Polygon] {ticker}: {len(df)} rows")
            except Exception as e:
                logger.warning(f"[Polygon] {ticker} failed ({e}) — falling back to yfinance")
                df = fetch_yfinance(ticker, from_date, to_date)
                if not df.empty:
                    frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def persist_prices(df: pd.DataFrame):
    """Upsert price rows into the prices table."""
    if df.empty:
        return
    session = get_session()
    for _, row in df.iterrows():
        session.execute(text("""
            INSERT INTO prices (date, ticker, open, high, low, close, volume, adj_close, source)
            VALUES (:date, :ticker, :open, :high, :low, :close, :volume, :adj_close, :source)
            ON CONFLICT (date, ticker) DO UPDATE SET
                adj_close = EXCLUDED.adj_close,
                source    = EXCLUDED.source
        """), dict(row))
    session.commit()
    session.close()
    logger.info(f"Persisted {len(df)} price rows.")

def run_ingestion(tickers: list, from_date: str, to_date: str):
    df_raw = asyncio.run(fetch_all_async(tickers, from_date, to_date))
    from engine.data.validation import validate_prices
    df_clean = validate_prices(df_raw)
    persist_prices(df_clean)
    return df_clean
```

---

### 1.5 Create `engine/data/validation.py`

Formalises your existing `MAX_DAILY_MOVE_ANOMALY` gate and adds missing-day detection.

```python
# engine/data/validation.py
import pandas as pd
import numpy as np
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)
MAX_DAILY_MOVE = 0.30   # from portfolio/src/config.py — keep consistent


def validate_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs all validation checks. Returns clean rows only.
    Logs violations to data_validation_log table.
    """
    if df.empty:
        return df

    clean_rows = []
    violations = []

    for ticker, group in df.groupby("ticker"):
        group = group.sort_values("date").reset_index(drop=True)
        group["daily_return"] = group["adj_close"].pct_change()

        for _, row in group.iterrows():
            ret = row.get("daily_return", np.nan)

            # Price spike check (your existing 30% gate)
            if not np.isnan(ret) and abs(ret) > MAX_DAILY_MOVE:
                violations.append({
                    "date": row["date"], "ticker": ticker,
                    "issue_type": "price_spike",
                    "raw_value": ret, "action": "rejected"
                })
                logger.warning(f"Rejected {ticker} on {row['date']}: {ret:.1%} move > 30% gate")
                continue

            clean_rows.append(row.to_dict())

    # Log violations to DB
    if violations:
        session = get_session()
        for v in violations:
            session.execute(text("""
                INSERT INTO data_validation_log (date, ticker, issue_type, raw_value, action)
                VALUES (:date, :ticker, :issue_type, :raw_value, :action)
            """), v)
        session.commit()
        session.close()

    result = pd.DataFrame(clean_rows).drop(columns=["daily_return"], errors="ignore")
    logger.info(f"Validation: {len(result)} clean rows, {len(violations)} rejected")
    return result
```

---

### Sprint 1 Checklist

- [ ] Docker PostgreSQL running locally
- [ ] `schema.sql` applied — all tables exist
- [ ] `engine/db/db.py` connects successfully
- [ ] `run_ingestion()` fetches 2 years of history for 10 test tickers
- [ ] Validation rejects a synthetic 40% spike in test data
- [ ] Violations appear in `data_validation_log` table
- [ ] Fallback to yfinance works when Polygon key is absent

---

## Sprint 2 — Feature Store

**Goal:** Promote your existing research functions from `general_research/src/` into a production feature pipeline that writes to the `feature_store` table daily.

**What changes from current code:**
- `regime.py`, `correlation.py`, `factor_model.py` stay unchanged in `general_research/` (research layer). You wrap them in a new `engine/features/feature_store.py` that reads from the DB and writes results back.

---

### 2.1 Create `engine/features/feature_store.py`

```python
# engine/features/feature_store.py
import numpy as np
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import logging
import sys
sys.path.insert(0, ".")  # allow importing from research layer

logger = logging.getLogger(__name__)


# ── Data loading from DB ───────────────────────────────────────────────

def load_returns_from_db(tickers: list, lookback_days: int = 504) -> pd.DataFrame:
    """Loads adj_close from prices table, computes log returns."""
    session = get_session()
    result = session.execute(text("""
        SELECT date, ticker, adj_close FROM prices
        WHERE ticker = ANY(:tickers)
        ORDER BY date ASC
    """), {"tickers": tickers})
    rows = result.fetchall()
    session.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "ticker", "adj_close"])
    pivot = df.pivot(index="date", columns="ticker", values="adj_close")
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index().tail(lookback_days)
    log_returns = np.log(pivot / pivot.shift(1)).dropna()
    return log_returns


# ── Feature computation functions ────────────────────────────────────

def compute_momentum_features(prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-sectional momentum ranks: 1M, 3M, 6M, 12M.
    Skips last 21 days to avoid short-term reversal contamination (standard).
    """
    skip = 21
    windows = {"mom_1m": 21, "mom_3m": 63, "mom_6m": 126, "mom_12m": 252}
    features = {}
    for name, lookback in windows.items():
        if len(prices_df) < lookback + skip:
            continue
        raw = prices_df.shift(skip) / prices_df.shift(lookback + skip) - 1
        features[name] = raw.iloc[-1].rank(pct=True)  # cross-sectional rank 0-1
    return pd.DataFrame(features)


def compute_volatility_features(log_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Realized vol (21D, 63D annualised) and vol-of-vol.
    Promotes your existing regime.py compute_realised_vol logic.
    """
    features = {}
    features["vol_21d"] = log_returns.tail(21).std() * np.sqrt(252)
    features["vol_63d"] = log_returns.tail(63).std() * np.sqrt(252)
    vol_short = log_returns.rolling(21).std() * np.sqrt(252)
    vol_long  = log_returns.rolling(63).std() * np.sqrt(252)
    vol_of_vol = ((vol_short - vol_long) / vol_long).iloc[-1]
    features["vol_of_vol"] = vol_of_vol
    return pd.DataFrame(features)


def compute_technical_features(prices_df: pd.DataFrame) -> pd.DataFrame:
    """RSI(14) for each ticker. You can add MACD here as a follow-on."""
    features = {}
    rsi_values = {}
    for ticker in prices_df.columns:
        series = prices_df[ticker].dropna()
        if len(series) < 20:
            continue
        delta = series.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        rsi_values[ticker] = float(rsi.iloc[-1])
    features["rsi_14"] = pd.Series(rsi_values)
    return pd.DataFrame(features)


def compute_regime_features(log_returns: pd.DataFrame, tickers: list) -> dict:
    """
    Wraps your existing general_research/src/regime.py.
    Returns portfolio-level stress score + regime label.
    """
    from ml_quant_finance_research.general_research.src.regime import compute_composite_regime
    portfolio_returns = log_returns[tickers].mean(axis=1)
    regime_df = compute_composite_regime(portfolio_returns, log_returns)
    latest = regime_df.iloc[-1]
    return {
        "stress_score":   float(latest["stress_score"]),
        "regime":         latest["regime"],
        "vol_component":  float(latest["vol_component"]),
        "corr_component": float(latest["corr_component"]),
    }


# ── Persistence ───────────────────────────────────────────────────────

def persist_features(date: str, feature_df: pd.DataFrame):
    """
    Writes computed features to feature_store.
    feature_df index = tickers, columns = feature names.
    """
    session = get_session()
    count = 0
    for ticker in feature_df.index:
        for feature_name in feature_df.columns:
            val = feature_df.loc[ticker, feature_name]
            if pd.isna(val):
                continue
            session.execute(text("""
                INSERT INTO feature_store (date, ticker, feature_name, feature_value)
                VALUES (:date, :ticker, :feature_name, :feature_value)
                ON CONFLICT (date, ticker, feature_name) DO UPDATE
                SET feature_value = EXCLUDED.feature_value,
                    computed_at   = NOW()
            """), {"date": date, "ticker": ticker,
                   "feature_name": feature_name, "feature_value": float(val)})
            count += 1
    session.commit()
    session.close()
    logger.info(f"Feature store: persisted {count} feature values for {date}")


# ── Daily runner ─────────────────────────────────────────────────────

def run_feature_pipeline(tickers: list, date: str = None):
    """Entry point — called by scheduler daily after market close."""
    import datetime
    if date is None:
        date = str(datetime.date.today())

    log_returns = load_returns_from_db(tickers)
    if log_returns.empty:
        logger.error("No price data in DB — run ingestion first.")
        return

    prices = np.exp(log_returns.cumsum())   # reconstruct price index

    mom_features  = compute_momentum_features(prices)
    vol_features  = compute_volatility_features(log_returns)
    tech_features = compute_technical_features(prices)

    # Merge all feature frames on ticker
    all_features = pd.concat([mom_features, vol_features, tech_features], axis=1)
    all_features.index.name = "ticker"

    persist_features(date, all_features)
    logger.info(f"Feature pipeline complete: {date}, {len(all_features)} tickers")
    return all_features
```

---

### Sprint 2 Checklist

- [ ] `run_feature_pipeline()` runs without error on 20 tickers
- [ ] `feature_store` table populated — verify with `SELECT COUNT(*) FROM feature_store`
- [ ] Momentum ranks are between 0 and 1 for all tickers
- [ ] RSI values between 0 and 100
- [ ] Vol features annualised (typical range 0.10–0.80)
- [ ] Regime features return stress_score + label for current date

---

## Sprint 3 — Alpha Models + IC Tracking

**Goal:** Build three independent alpha models that each produce `(expected_return, confidence)` in a standardised format. IC tracking enables automatic confidence adjustment.

**What changes from current code:**
- Your existing `portfolio/src/math_optimizer.py` uses `mean_returns = log_returns.mean() * 252` as its expected return estimate. Alpha models replace this raw historical mean.

---

### 3.1 Create `engine/alpha/base.py`

```python
# engine/alpha/base.py
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from sqlalchemy import text
from engine.db.db import get_session
from scipy.stats import pearsonr
import logging

logger = logging.getLogger(__name__)


class AlphaModel(ABC):
    name: str = "base"

    @abstractmethod
    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Returns DataFrame with columns:
            ticker, expected_return, confidence, raw_score
        """
        pass

    def persist_signals(self, date: str, signals_df: pd.DataFrame):
        session = get_session()
        for _, row in signals_df.iterrows():
            session.execute(text("""
                INSERT INTO signals (date, ticker, model_name, expected_return, confidence, raw_score)
                VALUES (:date, :ticker, :model_name, :expected_return, :confidence, :raw_score)
                ON CONFLICT (date, ticker, model_name) DO UPDATE SET
                    expected_return = EXCLUDED.expected_return,
                    confidence      = EXCLUDED.confidence,
                    raw_score       = EXCLUDED.raw_score,
                    computed_at     = NOW()
            """), {
                "date": date, "ticker": row["ticker"], "model_name": self.name,
                "expected_return": row["expected_return"],
                "confidence": row["confidence"], "raw_score": row["raw_score"]
            })
        session.commit()
        session.close()

    def compute_rolling_ic(self, lookback_days: int = 63) -> float:
        """
        Information Coefficient: Pearson corr between yesterday's signal
        and today's actual return, rolled over lookback_days.
        A higher IC = model has been performing → increases confidence.
        """
        session = get_session()
        result = session.execute(text("""
            SELECT s.date, s.ticker, s.raw_score, p.adj_close
            FROM signals s
            JOIN prices p ON s.date = p.date AND s.ticker = p.ticker
            WHERE s.model_name = :model AND s.date >= CURRENT_DATE - :days
            ORDER BY s.date, s.ticker
        """), {"model": self.name, "days": lookback_days + 5})
        rows = result.fetchall()
        session.close()

        if len(rows) < 20:
            return 0.05   # default IC when insufficient history

        df = pd.DataFrame(rows, columns=["date", "ticker", "raw_score", "adj_close"])
        df["fwd_return"] = df.groupby("ticker")["adj_close"].pct_change().shift(-1)
        df = df.dropna()

        if len(df) < 10:
            return 0.05

        ic, _ = pearsonr(df["raw_score"], df["fwd_return"])
        return max(0.01, float(ic))   # floor at 1% to avoid zero confidence
```

---

### 3.2 Create `engine/alpha/momentum.py`

```python
# engine/alpha/momentum.py
import pandas as pd
import numpy as np
from engine.alpha.base import AlphaModel
from engine.db.db import get_session
from sqlalchemy import text

# IC-to-return mapping (calibrated): top quintile momentum stocks
# historically return ~3-4% annualised alpha above equilibrium
RETURN_SCALE = 0.04   # 4% expected excess for rank=1.0

class MomentumAlpha(AlphaModel):
    name = "momentum"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        session = get_session()
        # Pull 12M momentum rank from feature_store
        result = session.execute(text("""
            SELECT ticker, feature_value FROM feature_store
            WHERE date = :date AND feature_name = 'mom_12m'
              AND ticker = ANY(:tickers)
        """), {"date": date, "tickers": tickers})
        rows = result.fetchall()
        session.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["ticker", "raw_score"])
        ic = self.compute_rolling_ic()

        # Convert rank (0-1) to expected return: top decile → +RETURN_SCALE
        df["expected_return"] = (df["raw_score"] - 0.5) * 2 * RETURN_SCALE
        df["confidence"] = ic    # IC directly controls BL view weight
        df["raw_score"] = df["raw_score"]
        return df[["ticker", "expected_return", "confidence", "raw_score"]]
```

---

### 3.3 Create `engine/alpha/mean_reversion.py`

```python
# engine/alpha/mean_reversion.py
import pandas as pd
import numpy as np
from engine.alpha.base import AlphaModel
from engine.db.db import get_session
from sqlalchemy import text

RETURN_SCALE = 0.025   # mean reversion is a weaker signal — 2.5% scale

class MeanReversionAlpha(AlphaModel):
    name = "mean_reversion"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        session = get_session()
        result = session.execute(text("""
            SELECT ticker, feature_value FROM feature_store
            WHERE date = :date AND feature_name = 'rsi_14'
              AND ticker = ANY(:tickers)
        """), {"date": date, "tickers": tickers})
        rows = result.fetchall()
        session.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["ticker", "raw_score"])
        ic = self.compute_rolling_ic()

        # RSI < 30 → expected bounce (positive return)
        # RSI > 70 → expected pullback (negative return)
        # Normalise RSI to [-1, +1]
        df["rsi_norm"] = (50 - df["raw_score"]) / 50   # -1 to +1, oversold=positive
        df["expected_return"] = df["rsi_norm"] * RETURN_SCALE
        df["confidence"] = ic
        return df[["ticker", "expected_return", "confidence", "raw_score"]]
```

---

### 3.4 Create `engine/alpha/vol_timing.py`

```python
# engine/alpha/vol_timing.py
import pandas as pd
import numpy as np
from engine.alpha.base import AlphaModel
from engine.db.db import get_session
from sqlalchemy import text

class VolTimingAlpha(AlphaModel):
    name = "vol_timing"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        session = get_session()
        result = session.execute(text("""
            SELECT ticker, feature_name, feature_value FROM feature_store
            WHERE date = :date AND feature_name IN ('vol_21d', 'vol_63d')
              AND ticker = ANY(:tickers)
        """), {"date": date, "tickers": tickers})
        rows = result.fetchall()
        session.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["ticker", "feature_name", "feature_value"])
        pivot = df.pivot(index="ticker", columns="feature_name", values="feature_value")
        pivot = pivot.dropna()
        ic = self.compute_rolling_ic()

        # If short vol < long vol: vol is compressing → risk-on signal
        # If short vol > long vol: vol is expanding → risk-off
        pivot["vol_ratio"] = pivot["vol_21d"] / pivot["vol_63d"]
        pivot["raw_score"] = pivot["vol_ratio"]
        # Invert: low ratio = positive signal (low vol regime = higher expected returns)
        pivot["expected_return"] = (1 - pivot["vol_ratio"].rank(pct=True)) * 0.02
        pivot["confidence"] = ic
        pivot = pivot.reset_index()
        return pivot[["ticker", "expected_return", "confidence", "raw_score"]]
```

---

### Sprint 3 Checklist

- [ ] `MomentumAlpha().generate_signals(date, tickers)` returns a non-empty DataFrame
- [ ] `MeanReversionAlpha().generate_signals()` returns RSI-based signals
- [ ] `VolTimingAlpha().generate_signals()` returns vol-ratio signals
- [ ] `persist_signals()` writes to `signals` table for all three models
- [ ] `compute_rolling_ic()` returns 0.05 (default) with < 20 observations
- [ ] Verify signals table: `SELECT model_name, COUNT(*) FROM signals GROUP BY model_name`
- [ ] All `expected_return` values are in realistic range (approx −0.10 to +0.10)

---

## Sprint 4 — Black-Litterman + Upgraded Optimizer

**Goal:** Replace the raw historical mean in `math_optimizer.py` with BL posterior returns. Promote `factor_model.py`'s BL implementation into the production engine. Add turnover penalty and transaction cost modeling.

**What changes from current code:**
- `portfolio/src/math_optimizer.py` currently calls `mean_returns = log_returns.mean() * 252`. Sprint 4 replaces this input with BL posterior returns.
- Your existing `factor_model.py` has a working `black_litterman()` function — promote it directly.

---

### 4.1 Create `engine/portfolio/black_litterman.py`

This is a thin production wrapper around your existing research implementation.

```python
# engine/portfolio/black_litterman.py
"""
Production wrapper around general_research/src/factor_model.py.
Loads alpha model signals from DB, constructs BL views, returns posterior returns.
"""
import pandas as pd
import numpy as np
from sqlalchemy import text
from engine.db.db import get_session
import sys
sys.path.insert(0, ".")

# Import your existing research implementation directly
from ml_quant_finance_research.general_research.src.factor_model import (
    black_litterman, compute_market_implied_returns
)
import logging

logger = logging.getLogger(__name__)


def load_signals_from_db(date: str, tickers: list) -> pd.DataFrame:
    """Loads all model signals for a given date."""
    session = get_session()
    result = session.execute(text("""
        SELECT ticker, model_name, expected_return, confidence
        FROM signals
        WHERE date = :date AND ticker = ANY(:tickers)
    """), {"date": date, "tickers": tickers})
    rows = result.fetchall()
    session.close()
    return pd.DataFrame(rows, columns=["ticker", "model_name", "expected_return", "confidence"])


def build_bl_views(signals_df: pd.DataFrame, tickers: list) -> list:
    """
    Converts alpha model signals into Black-Litterman view dicts.
    Each model-ticker combination becomes one view.
    Confidence (IC) controls omega — higher IC = lower uncertainty = more influence.
    """
    views = []
    for _, row in signals_df.iterrows():
        if row["ticker"] not in tickers:
            continue
        ic = max(0.01, float(row["confidence"]))
        # Omega inversely proportional to IC squared
        omega = 0.0004 / (ic ** 2)
        views.append({
            "assets":  [row["ticker"]],
            "weights": [1.0],
            "Q":       float(row["expected_return"]),
            "omega":   omega,
        })
    return views


def build_regime_view(regime_info: dict, tickers: list, benchmark: str) -> list:
    """
    Injects regime as a BL view on the benchmark.
    Uses your existing build_regime_views logic from factor_model.py.
    """
    from ml_quant_finance_research.general_research.src.factor_model import build_regime_views
    return build_regime_views(
        tickers=tickers,
        benchmark_ticker=benchmark,
        regime=regime_info.get("regime", "medium"),
        stress_score=regime_info.get("stress_score", 0.5),
    )


def run_black_litterman(
    tickers: list,
    cov_matrix: pd.DataFrame,
    market_weights: pd.Series,
    date: str,
    regime_info: dict = None,
    benchmark: str = "EUNL.DE",
    tau: float = 0.05,
    risk_aversion: float = 2.5,
) -> pd.Series:
    """
    Full BL pipeline:
    1. Load alpha signals from DB
    2. Build views (alpha signals + regime view)
    3. Run BL formula → posterior expected returns
    Returns pd.Series indexed by ticker.
    """
    signals_df = load_signals_from_db(date, tickers)
    alpha_views = build_bl_views(signals_df, tickers)

    regime_views = []
    if regime_info:
        regime_views = build_regime_view(regime_info, tickers, benchmark)

    all_views = alpha_views + regime_views
    logger.info(f"BL: {len(alpha_views)} alpha views + {len(regime_views)} regime view")

    # Use your existing BL implementation from factor_model.py
    mu_bl = black_litterman(
        cov_matrix=cov_matrix,
        market_weights=market_weights,
        views=all_views,
        tau=tau,
        risk_aversion=risk_aversion,
    )
    return mu_bl
```

---

### 4.2 Create `engine/portfolio/optimizer.py`

Extends `math_optimizer.py` with BL returns, turnover penalty, and transaction costs.

```python
# engine/portfolio/optimizer.py
"""
Extended optimizer: BL returns + turnover penalty + cost model.
Extends portfolio/src/math_optimizer.py — does not replace it.
The original is still used for the simple backtester.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import logging
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

# Constraints (extend from config.py values)
MAX_POSITION     = 0.10   # 10% max per asset (tighter than config's 25% for BL output)
MAX_SECTOR_SHARE = 0.30   # 30% max in any one sector
TURNOVER_PENALTY = 0.002  # penalty per unit of turnover
SLIPPAGE_PCT     = 0.0005 # 0.05% per trade (from architecture doc)


def build_sector_constraints(tickers: list, sector_map: dict, max_sector: float = MAX_SECTOR_SHARE) -> list:
    """Generates one inequality constraint per sector."""
    sectors = {}
    for i, t in enumerate(tickers):
        s = sector_map.get(t, "other")
        sectors.setdefault(s, []).append(i)
    constraints = []
    for sector, indices in sectors.items():
        constraints.append({
            "type": "ineq",
            "fun": lambda w, idx=indices: max_sector - np.sum(w[idx])
        })
    return constraints


def optimize_with_bl(
    mu_bl: pd.Series,
    cov_matrix: pd.DataFrame,
    current_weights: pd.Series,
    sector_map: dict = None,
    risk_aversion: float = 2.5,
) -> pd.Series:
    """
    Constrained optimizer using BL posterior returns.

    Objective:
        maximize  mu_BL · w  −  (δ/2) wᵀΣw  −  turnover_penalty · |Δw|  −  costs · |Δw|
    """
    tickers = mu_bl.index.tolist()
    n = len(tickers)

    # Align current weights
    w0 = np.array([current_weights.get(t, 0.0) for t in tickers])
    mu = mu_bl.values
    Sigma = cov_matrix.loc[tickers, tickers].values

    def objective(w):
        ret       = np.dot(mu, w)
        risk      = 0.5 * risk_aversion * w @ Sigma @ w
        delta_w   = np.abs(w - w0)
        turnover  = TURNOVER_PENALTY * np.sum(delta_w)
        costs     = SLIPPAGE_PCT * np.sum(delta_w)
        return -(ret - risk - turnover - costs)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if sector_map:
        constraints += build_sector_constraints(tickers, sector_map)

    bounds = [(0, MAX_POSITION)] * n

    result = minimize(
        objective, x0=w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9}
    )

    if not result.success:
        logger.warning(f"BL optimizer did not converge: {result.message}")

    weights = pd.Series(np.round(result.x, 4), index=tickers)
    return weights


def persist_model_outputs(date: str, suggested: pd.Series, current: pd.Series, mu_bl: pd.Series):
    session = get_session()
    for ticker in suggested.index:
        session.execute(text("""
            INSERT INTO model_outputs
                (date, ticker, suggested_weight, current_weight, delta_weight, bl_return)
            VALUES (:date, :ticker, :suggested, :current, :delta, :bl_return)
            ON CONFLICT (date, ticker) DO UPDATE SET
                suggested_weight = EXCLUDED.suggested_weight,
                delta_weight     = EXCLUDED.delta_weight,
                bl_return        = EXCLUDED.bl_return,
                computed_at      = NOW()
        """), {
            "date": date, "ticker": ticker,
            "suggested": float(suggested.get(ticker, 0)),
            "current":   float(current.get(ticker, 0)),
            "delta":     float(suggested.get(ticker, 0) - current.get(ticker, 0)),
            "bl_return": float(mu_bl.get(ticker, 0)),
        })
    session.commit()
    session.close()
    logger.info(f"Model outputs persisted: {date}, {len(suggested)} tickers")
```

---

### Sprint 4 Checklist

- [ ] `run_black_litterman()` returns a `pd.Series` of posterior returns for all tickers
- [ ] Returns are sensible: range approximately −0.15 to +0.15 annualised
- [ ] Regime view injects correctly (stress_score shifts benchmark return down in high_stress)
- [ ] `optimize_with_bl()` produces weights summing to 1.0
- [ ] No single weight exceeds 10%
- [ ] Sector constraint is respected (verify with a simple test sector_map)
- [ ] `model_outputs` table populated: `SELECT * FROM model_outputs ORDER BY date DESC LIMIT 20`
- [ ] Turnover penalty reduces trading frequency vs. no-penalty baseline (verify on test run)

---

## Sprint 5 — Risk Engine + PEAD/ML Alpha Integration

**Goal:** Build pre-trade and post-trade risk controls. Wire in your existing `pead_engine` and `stock_ml_lab` as Alpha Models 4 and 5.

---

### 5.1 Create `engine/risk/pre_trade.py`

```python
# engine/risk/pre_trade.py
import pandas as pd
import numpy as np
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MAX_POSITION    = 0.10
MAX_SECTOR      = 0.30
MAX_LEVERAGE    = 1.0
MIN_ADV_RATIO   = 0.01    # order must be < 1% of 30-day avg daily volume


def check_position_limits(suggested_weights: pd.Series) -> list:
    violations = []
    for ticker, w in suggested_weights.items():
        if w > MAX_POSITION:
            violations.append(f"{ticker}: weight {w:.1%} exceeds max {MAX_POSITION:.0%}")
    return violations


def check_leverage(suggested_weights: pd.Series) -> list:
    total = suggested_weights.sum()
    if total > MAX_LEVERAGE + 0.001:
        return [f"Total weight {total:.3f} exceeds max leverage {MAX_LEVERAGE}"]
    return []


def check_sector_exposure(suggested_weights: pd.Series, sector_map: dict) -> list:
    sector_totals = {}
    for ticker, w in suggested_weights.items():
        s = sector_map.get(ticker, "other")
        sector_totals[s] = sector_totals.get(s, 0) + w
    violations = []
    for sector, total in sector_totals.items():
        if total > MAX_SECTOR:
            violations.append(f"Sector {sector}: {total:.1%} exceeds {MAX_SECTOR:.0%} limit")
    return violations


def run_pre_trade_checks(suggested_weights: pd.Series, sector_map: dict = None) -> dict:
    """
    Runs all pre-trade checks. Returns result with pass/fail and list of violations.
    Violations block order submission.
    """
    violations = []
    violations += check_position_limits(suggested_weights)
    violations += check_leverage(suggested_weights)
    if sector_map:
        violations += check_sector_exposure(suggested_weights, sector_map)

    result = {
        "passed": len(violations) == 0,
        "violations": violations,
    }

    if not result["passed"]:
        logger.warning(f"Pre-trade FAILED: {violations}")
    else:
        logger.info("Pre-trade checks: ALL PASSED")

    # Log to DB
    session = get_session()
    for v in violations:
        session.execute(text("""
            INSERT INTO risk_events (date, metric_name, metric_value)
            VALUES (CURRENT_DATE, :name, 1)
        """), {"name": f"pre_trade_violation: {v[:60]}"})
    session.commit()
    session.close()

    return result
```

---

### 5.2 Create `engine/risk/post_trade.py`

```python
# engine/risk/post_trade.py
"""
Post-trade risk monitoring: VaR, CVaR, drawdown, regime detection.
Promotes your existing regime.py and research metrics.
"""
import numpy as np
import pandas as pd
from scipy import stats
from engine.features.feature_store import load_returns_from_db
from engine.db.db import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def historical_var_cvar(returns: pd.Series, confidence: float = 0.95) -> dict:
    """Historical simulation VaR and CVaR — no normality assumption."""
    sorted_ret = returns.sort_values()
    cutoff_idx = int((1 - confidence) * len(sorted_ret))
    var  = float(sorted_ret.iloc[cutoff_idx])
    cvar = float(sorted_ret.iloc[:cutoff_idx].mean())
    return {"var_95": round(var, 4), "cvar_95": round(cvar, 4)}


def drawdown_metrics(equity_curve: pd.Series) -> dict:
    rolling_max  = equity_curve.cummax()
    drawdown     = (equity_curve - rolling_max) / rolling_max
    max_dd       = float(drawdown.min())
    current_dd   = float(drawdown.iloc[-1])
    return {"max_drawdown": round(max_dd, 4), "current_drawdown": round(current_dd, 4)}


def portfolio_returns_from_weights(
    weights: dict, log_returns: pd.DataFrame, lookback: int = 252
) -> pd.Series:
    tickers = [t for t in weights if t in log_returns.columns]
    w = np.array([weights[t] for t in tickers])
    w = w / w.sum()
    return log_returns[tickers].tail(lookback).dot(w)


def compute_regime_stress(tickers: list) -> dict:
    """
    Wraps your existing composite regime engine from regime.py.
    Returns current stress score and regime label.
    """
    log_returns = load_returns_from_db(tickers)
    if log_returns.empty:
        return {"stress_score": 0.5, "regime": "medium"}

    from ml_quant_finance_research.general_research.src.regime import compute_composite_regime
    portfolio_ret = log_returns.mean(axis=1)
    regime_df = compute_composite_regime(portfolio_ret, log_returns)
    latest = regime_df.iloc[-1]
    return {
        "stress_score":  float(latest["stress_score"]),
        "regime":        latest["regime"],
        "vol_component": float(latest["vol_component"]),
    }


def run_post_trade_risk(weights: dict, tickers: list) -> dict:
    """Full post-trade risk snapshot. Called after every rebalance."""
    log_returns = load_returns_from_db(tickers)
    port_returns = portfolio_returns_from_weights(weights, log_returns)
    equity_curve = (1 + port_returns).cumprod()

    var_cvar = historical_var_cvar(port_returns)
    dd       = drawdown_metrics(equity_curve)
    regime   = compute_regime_stress(tickers)

    metrics = {**var_cvar, **dd, **regime}

    # Stress tests — hardcoded historical scenarios
    stress_shocks = {
        "gfc_2008":       -0.45,
        "covid_2020":     -0.34,
        "rate_shock_2022":-0.20,
        "mild_correction":-0.10,
    }
    equity_weight = sum(w for t, w in weights.items() if t != "CASH")
    for scenario, shock in stress_shocks.items():
        metrics[f"stress_{scenario}"] = round(equity_weight * shock, 4)

    # Persist to DB
    session = get_session()
    for metric_name, val in metrics.items():
        if isinstance(val, (int, float)):
            session.execute(text("""
                INSERT INTO risk_metrics (date, metric_name, metric_value)
                VALUES (CURRENT_DATE, :name, :val)
                ON CONFLICT (date, metric_name) DO UPDATE SET metric_value = EXCLUDED.metric_value
            """), {"name": metric_name, "val": float(val)})
    session.commit()
    session.close()
    logger.info(f"Post-trade risk: VaR={var_cvar['var_95']:.2%}, CVaR={var_cvar['cvar_95']:.2%}, Regime={regime['regime']}")
    return metrics
```

---

### 5.3 Wire in PEAD Engine as Alpha Model 4

Your `quant_research/pead_engine/` already runs independently. Create a thin wrapper:

```python
# engine/alpha/pead_alpha.py
"""
Wraps the existing pead_engine screener as Alpha Model 4.
The PEAD engine already has its own DB (pead_db.py) and screener.
This adapter reads its output and converts to the standard signal format.
"""
import pandas as pd
import sys
sys.path.insert(0, ".")
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)

PEAD_RETURN_SCALE = 0.03   # PEAD alpha — 3% expected excess for top-ranked stocks


class PEADAlpha(AlphaModel):
    name = "pead"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        try:
            from ml_quant_finance_research.quant_research.pead_engine.screener import run_screener
            pead_results = run_screener()   # returns DataFrame with ticker + score columns
        except Exception as e:
            logger.warning(f"PEAD engine failed: {e} — skipping PEAD alpha")
            return pd.DataFrame()

        if pead_results is None or pead_results.empty:
            return pd.DataFrame()

        ic = self.compute_rolling_ic()

        # Normalise PEAD score to [0,1] rank, convert to expected return
        pead_results["rank"] = pead_results["score"].rank(pct=True)
        pead_results["expected_return"] = (pead_results["rank"] - 0.5) * 2 * PEAD_RETURN_SCALE
        pead_results["confidence"] = ic
        pead_results["raw_score"] = pead_results["score"]
        pead_results = pead_results.rename(columns={"symbol": "ticker"})

        result = pead_results[pead_results["ticker"].isin(tickers)]
        return result[["ticker", "expected_return", "confidence", "raw_score"]]
```

---

### 5.4 Wire in ML Lab as Alpha Model 5

```python
# engine/alpha/ml_alpha.py
"""
Wraps stock_ml_lab as Alpha Model 5.
Reads saved model predictions and converts to signal format.
"""
import pandas as pd
import os
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)
ML_RESULTS_PATH = "ml_quant_finance_research/ml_research/stock_ml_lab/results/"


class MLAlpha(AlphaModel):
    name = "ml_model"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        # Look for today's prediction file
        pred_file = os.path.join(ML_RESULTS_PATH, f"predictions_{date}.csv")
        if not os.path.exists(pred_file):
            logger.warning(f"No ML predictions for {date} — skipping ML alpha")
            return pd.DataFrame()

        df = pd.read_csv(pred_file)
        ic = self.compute_rolling_ic()

        df["confidence"] = ic
        df["raw_score"] = df.get("predicted_return", df.get("score", 0))
        df["expected_return"] = df["raw_score"]

        if "ticker" not in df.columns and "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})

        result = df[df["ticker"].isin(tickers)]
        return result[["ticker", "expected_return", "confidence", "raw_score"]]
```

---

### Sprint 5 Checklist

- [ ] `run_pre_trade_checks()` blocks a test weight of 0.50 on a single stock
- [ ] Pre-trade passes for a valid 10-stock equally weighted portfolio
- [ ] `run_post_trade_risk()` returns VaR, CVaR, drawdown, stress test values
- [ ] Stress test values are negative (portfolio loses money in each scenario)
- [ ] Regime detection returns a regime label and stress_score
- [ ] `PEADAlpha.generate_signals()` runs without crashing (even if PEAD engine returns empty)
- [ ] `MLAlpha.generate_signals()` returns empty gracefully when no prediction file exists

---

## Sprint 6 — Execution Engine + State Reconciliation

**Goal:** Build the order state machine and state reconciliation. Since trades are executed manually, the execution engine generates a structured to-execute list and logs what you actually did.

---

### 6.1 Create `engine/execution/order_manager.py`

```python
# engine/execution/order_manager.py
"""
Order state machine for manual execution.
You review the queue, execute on your broker (Trade Republic),
then confirm execution via the dashboard form.
States: CREATED → REVIEWED → CONFIRMED / SKIPPED
"""
import pandas as pd
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from sqlalchemy import text
from engine.db.db import get_session
import logging

logger = logging.getLogger(__name__)


class OrderState(Enum):
    CREATED   = "CREATED"
    REVIEWED  = "REVIEWED"
    CONFIRMED = "CONFIRMED"
    SKIPPED   = "SKIPPED"
    FAILED    = "FAILED"


@dataclass
class Order:
    ticker:      str
    action:      str       # BUY or SELL
    value_eur:   float
    state:       OrderState = OrderState.CREATED
    order_id:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notes:       str = ""
    slippage_pct:float = 0.0005


def generate_order_queue(
    suggested_weights: pd.Series,
    current_weights: pd.Series,
    total_portfolio_eur: float,
    min_trade_eur: float = 25.0,
) -> list:
    """
    Generates a list of Orders from the weight delta.
    Applies your existing MIN_TRADE_EUR_FLOOR and drift thresholds.
    """
    orders = []
    for ticker in suggested_weights.index:
        target_w  = float(suggested_weights.get(ticker, 0))
        current_w = float(current_weights.get(ticker, 0))
        delta_w   = target_w - current_w
        delta_eur = delta_w * total_portfolio_eur

        if abs(delta_eur) < min_trade_eur:
            continue

        action = "BUY" if delta_eur > 0 else "SELL"
        orders.append(Order(
            ticker=ticker, action=action, value_eur=abs(delta_eur)
        ))

    orders.sort(key=lambda o: abs(o.value_eur), reverse=True)
    logger.info(f"Order queue: {len(orders)} orders generated")
    return orders


def confirm_order(order_id: str, actual_value_eur: float, price_eur: float, notes: str = ""):
    """Called from dashboard when you confirm you executed an order manually."""
    session = get_session()
    session.execute(text("""
        INSERT INTO trades (date, ticker, action, quantity, price_eur, value_eur, source, notes)
        VALUES (CURRENT_DATE, :ticker, :action, :qty, :price, :value, 'manual', :notes)
    """), {
        "ticker": "UNKNOWN",   # replaced by dashboard with actual ticker
        "action": "BUY",
        "qty": actual_value_eur / price_eur if price_eur > 0 else 0,
        "price": price_eur, "value": actual_value_eur, "notes": notes
    })
    session.commit()
    session.close()
```

---

### 6.2 Create `engine/reconciliation/state_reconciler.py`

```python
# engine/reconciliation/state_reconciler.py
"""
State reconciliation — compare internal DB to your actual broker positions.
Since Trade Republic has no public API, this uses a manual entry form.
The dashboard shows a side-by-side view: DB positions vs. what you enter from the app.
"""
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import json
import logging

logger = logging.getLogger(__name__)


def get_db_positions() -> pd.DataFrame:
    """Latest positions from internal DB."""
    session = get_session()
    result = session.execute(text("""
        SELECT DISTINCT ON (ticker) ticker, quantity, price, value_eur, weight
        FROM positions_history
        ORDER BY ticker, date DESC
    """))
    rows = result.fetchall()
    session.close()
    return pd.DataFrame(rows, columns=["ticker", "quantity", "price", "value_eur", "weight"])


def reconcile(broker_positions: dict) -> dict:
    """
    broker_positions: dict of {ticker: {"quantity": x, "price": y}}
    Returns reconciliation result + discrepancies.
    Manual entry from Trade Republic app → this function.
    """
    db_df = get_db_positions()
    db_dict = {row["ticker"]: row for _, row in db_df.iterrows()}

    discrepancies = []
    for ticker, broker_pos in broker_positions.items():
        db_pos = db_dict.get(ticker)
        if db_pos is None:
            discrepancies.append({
                "ticker": ticker,
                "issue": "in_broker_not_in_db",
                "broker_qty": broker_pos["quantity"],
                "db_qty": None
            })
        else:
            qty_diff = abs(float(broker_pos["quantity"]) - float(db_pos["quantity"]))
            if qty_diff > 0.01:
                discrepancies.append({
                    "ticker": ticker,
                    "issue": "quantity_mismatch",
                    "broker_qty": broker_pos["quantity"],
                    "db_qty": float(db_pos["quantity"]),
                    "diff": qty_diff
                })

    # Log reconciliation
    session = get_session()
    session.execute(text("""
        INSERT INTO reconciliation_log
            (positions_match, cash_match, discrepancies, action_taken)
        VALUES (:pos_match, TRUE, :disc, :action)
    """), {
        "pos_match": len(discrepancies) == 0,
        "disc": json.dumps(discrepancies),
        "action": "manual_review_required" if discrepancies else "clean"
    })
    session.commit()
    session.close()

    if discrepancies:
        logger.warning(f"Reconciliation: {len(discrepancies)} discrepancies found")
    else:
        logger.info("Reconciliation: CLEAN — DB matches broker")

    return {"clean": len(discrepancies) == 0, "discrepancies": discrepancies}
```

---

### Sprint 6 Checklist

- [ ] `generate_order_queue()` produces correct BUY/SELL orders for a test weight delta
- [ ] Orders below `min_trade_eur` are suppressed
- [ ] Orders are sorted by size descending
- [ ] Trades table receives entries after `confirm_order()` is called
- [ ] `get_db_positions()` returns positions from DB
- [ ] `reconcile()` correctly flags a quantity mismatch of 0.5 shares
- [ ] Reconciliation log row inserted after every reconcile call

---

## Sprint 7 — Strategy Screens

**Goal:** Build the laggard screen and ETF divergence screen as standalone modules that feed into the dashboard. The divergence labeler creates your ML training dataset.

---

### 7.1 Create `engine/screens/laggard_screen.py`

Implements the 5-phase workflow from `laggard_screen_strategy.md`.

```python
# engine/screens/laggard_screen.py
"""
Laggard Stock Screen — as specified in laggard_screen_strategy.md.
Phases 1-5 implemented as composable functions.
"""
import pandas as pd
import numpy as np
from engine.features.feature_store import load_returns_from_db
from engine.db.db import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Configuration (mirrors strategy doc)
SECTOR_ETF_MAP = {
    "tech":        "EXXT.DE",   # Nasdaq-100 ETF
    "europe":      "EXS1.DE",   # DAX ETF
    "world":       "EUNL.DE",   # MSCI World ETF
}

LAGGARD_BOTTOM_QUARTILE = 0.25   # bottom 25% of peer group = laggard candidate


def detect_rising_sectors(
    sector_etf_map: dict,
    min_return_pct: float = 0.08,
    lookback_days: int = 126,   # ~6 months
) -> list:
    """Phase 1: Identify sectors with sustained upward momentum (8-25% over 1-6M)."""
    session = get_session()
    rising = []
    for sector, etf in sector_etf_map.items():
        result = session.execute(text("""
            SELECT adj_close FROM prices
            WHERE ticker = :etf
            ORDER BY date DESC
            LIMIT :days
        """), {"etf": etf, "days": lookback_days + 1})
        prices = [r[0] for r in result.fetchall()]
        if len(prices) < 2:
            continue
        period_return = (prices[0] - prices[-1]) / prices[-1]
        if period_return >= min_return_pct:
            rising.append({"sector": sector, "etf": etf, "return": round(period_return, 4)})
            logger.info(f"Rising sector: {sector} ({period_return:.1%} over {lookback_days}d)")
    session.close()
    return rising


def score_peer_group(tickers: list, lookback_days: int = 126) -> pd.DataFrame:
    """
    Phase 3: Rank tickers by relative performance.
    Returns DataFrame with ticker + relative_rank (0=worst, 1=best).
    """
    log_returns = load_returns_from_db(tickers, lookback_days=lookback_days + 21)
    if log_returns.empty:
        return pd.DataFrame()

    period_returns = (log_returns.tail(lookback_days).sum())   # cumulative log return
    df = pd.DataFrame({"ticker": period_returns.index, "period_return": period_returns.values})
    df["relative_rank"] = df["period_return"].rank(pct=True)
    return df.sort_values("relative_rank")


def run_disqualifier_checks(tickers: list) -> dict:
    """
    Phase 4: Disqualifier checks. Returns dict of {ticker: [disqualification reasons]}.
    Currently checks: short interest proxy via vol spike (placeholder — extend with Fintel API).
    """
    # This is a placeholder framework. In production:
    # - Pull short interest from Fintel/Ortex API
    # - Pull insider transactions from SEC EDGAR
    # - Check news sentiment via news API
    # Returns empty disqualifications by default (manual research required per todo doc)
    return {ticker: [] for ticker in tickers}


def run_laggard_screen(peer_groups: dict) -> list:
    """
    Full laggard screen pipeline. peer_groups = {sector: [tickers]}.
    Returns list of laggard candidates with conviction tier.
    """
    candidates = []

    for sector, tickers in peer_groups.items():
        if len(tickers) < 4:
            continue

        peer_df = score_peer_group(tickers)
        if peer_df.empty:
            continue

        laggards = peer_df[peer_df["relative_rank"] <= LAGGARD_BOTTOM_QUARTILE]
        disqualifiers = run_disqualifier_checks(laggards["ticker"].tolist())

        for _, row in laggards.iterrows():
            ticker = row["ticker"]
            disq = disqualifiers.get(ticker, [])
            if disq:
                logger.info(f"Disqualified: {ticker} — {disq}")
                continue

            # Peer median return for catch-up target
            peer_median_return = float(peer_df["period_return"].median())
            catch_up_gap = peer_median_return - float(row["period_return"])

            candidates.append({
                "ticker":             ticker,
                "sector":             sector,
                "period_return":      round(float(row["period_return"]), 4),
                "relative_rank":      round(float(row["relative_rank"]), 4),
                "peer_median_return": round(peer_median_return, 4),
                "catch_up_gap":       round(catch_up_gap, 4),
                "conviction":         "high" if row["relative_rank"] <= 0.10 else "medium",
                "disqualifiers":      disq,
            })

    candidates.sort(key=lambda x: x["catch_up_gap"], reverse=True)
    logger.info(f"Laggard screen: {len(candidates)} candidates identified")
    return candidates
```

---

### 7.2 Create `engine/screens/etf_divergence.py`

Implements the 4-scenario detection from `etf_component_divergence_strategy.md` with the labeling DB.

```python
# engine/screens/etf_divergence.py
"""
ETF vs Component Divergence Screen — etf_component_divergence_strategy.md.
Detects divergences, stores them in divergence_labels for human labeling.
"""
import pandas as pd
import uuid
from sqlalchemy import text
from engine.db.db import get_session
from engine.features.feature_store import load_returns_from_db
import logging

logger = logging.getLogger(__name__)

# ETF → component mapping (top positions only — extend as needed)
ETF_COMPONENT_MAP = {
    "EXXT.DE": ["NVDA", "META", "AMZN", "GOOGL", "MSFT", "APC.DE", "TSLA", "CRM", "ADBE", "NFLX"],
    "EXS1.DE": ["SAP.DE", "SIE.DE", "ALV.DE", "MUV2.DE", "DTE.DE", "IFX.DE", "BMW.DE", "BAYN.DE"],
    "EUNL.DE": ["MSF.DE", "APC.DE", "AMZN", "NVDA", "GOOGL", "META", "ASML.AS", "NOV.DE"],
}

# Minimum divergence to trigger checklist (per architecture doc)
MIN_DIVERGENCE_PCT  = 0.05   # stock down 5%+ while ETF up 3%+
ETF_MIN_UP          = 0.03
WINDOW_DAYS         = 28


def detect_divergences(date: str) -> list:
    """
    Scans all ETF-component pairs for divergence over WINDOW_DAYS.
    Returns list of divergence events to be labeled.
    """
    all_tickers = list(ETF_COMPONENT_MAP.keys())
    for etf, components in ETF_COMPONENT_MAP.items():
        all_tickers.extend(components)
    all_tickers = list(set(all_tickers))

    log_returns = load_returns_from_db(all_tickers, lookback_days=WINDOW_DAYS + 5)
    if log_returns.empty:
        return []

    divergences = []
    for etf, components in ETF_COMPONENT_MAP.items():
        if etf not in log_returns.columns:
            continue
        etf_return = float(log_returns[etf].tail(WINDOW_DAYS).sum())

        if etf_return < ETF_MIN_UP:
            continue   # ETF not rising — no divergence signal

        for ticker in components:
            if ticker not in log_returns.columns:
                continue
            stock_return = float(log_returns[ticker].tail(WINDOW_DAYS).sum())
            divergence = etf_return - stock_return

            if divergence >= MIN_DIVERGENCE_PCT:
                divergences.append({
                    "ticker":           ticker,
                    "etf_reference":    etf,
                    "detected_at":      date,
                    "window_days":      WINDOW_DAYS,
                    "etf_return_pct":   round(etf_return, 4),
                    "stock_return_pct": round(stock_return, 4),
                    "divergence_pct":   round(divergence, 4),
                })

    logger.info(f"ETF divergence scan: {len(divergences)} events detected for {date}")
    return divergences


def save_divergence_events(divergences: list):
    """Saves new divergence events to DB for human labeling."""
    session = get_session()
    for d in divergences:
        # Check if already exists
        existing = session.execute(text("""
            SELECT id FROM divergence_labels
            WHERE ticker = :ticker AND etf_reference = :etf AND detected_at = :date
        """), {"ticker": d["ticker"], "etf": d["etf_reference"], "date": d["detected_at"]}).fetchone()

        if existing:
            continue   # don't duplicate

        session.execute(text("""
            INSERT INTO divergence_labels
                (id, ticker, etf_reference, detected_at, window_days,
                 etf_return_pct, stock_return_pct, divergence_pct)
            VALUES (:id, :ticker, :etf, :date, :window, :etf_ret, :stock_ret, :div)
        """), {
            "id": str(uuid.uuid4()), "ticker": d["ticker"],
            "etf": d["etf_reference"], "date": d["detected_at"],
            "window": d["window_days"], "etf_ret": d["etf_return_pct"],
            "stock_ret": d["stock_return_pct"], "div": d["divergence_pct"],
        })

    session.commit()
    session.close()


def apply_scenario_label(divergence_id: str, scenario: int, confidence: str, notes: str, checklist: dict):
    """Called from dashboard when analyst labels a divergence event."""
    session = get_session()
    session.execute(text("""
        UPDATE divergence_labels SET
            scenario_label    = :scenario,
            confidence        = :confidence,
            notes             = :notes,
            checklist_answers = :checklist,
            labeled_at        = NOW()
        WHERE id = :id
    """), {
        "id": divergence_id, "scenario": scenario,
        "confidence": confidence, "notes": notes,
        "checklist": str(checklist)
    })
    session.commit()
    session.close()
    logger.info(f"Divergence {divergence_id} labeled: Scenario {scenario}, confidence={confidence}")


def fill_outcome_data():
    """
    Scheduled job: fills outcome_30d and outcome_90d for labeled events
    where 30/90 days have elapsed since detection.
    Run daily by scheduler.
    """
    session = get_session()
    result = session.execute(text("""
        SELECT dl.id, dl.ticker, dl.detected_at
        FROM divergence_labels dl
        WHERE dl.scenario_label IS NOT NULL
          AND (dl.outcome_30d IS NULL OR dl.outcome_90d IS NULL)
    """))
    rows = result.fetchall()

    for row in rows:
        div_id, ticker, detected_at = row
        for horizon_days, col in [(30, "outcome_30d"), (90, "outcome_90d")]:
            outcome = session.execute(text("""
                SELECT adj_close FROM prices
                WHERE ticker = :ticker AND date >= :start
                ORDER BY date ASC LIMIT 1
            """), {"ticker": ticker, "start": detected_at}).fetchone()

            end_price = session.execute(text("""
                SELECT adj_close FROM prices
                WHERE ticker = :ticker
                  AND date >= :start + INTERVAL ':days days'
                ORDER BY date ASC LIMIT 1
            """), {"ticker": ticker, "start": detected_at, "days": horizon_days}).fetchone()

            if outcome and end_price:
                fwd_return = round((end_price[0] - outcome[0]) / outcome[0], 4)
                session.execute(text(f"""
                    UPDATE divergence_labels SET {col} = :ret WHERE id = :id
                """), {"ret": fwd_return, "id": div_id})

    session.commit()
    session.close()
```

---

### Sprint 7 Checklist

- [ ] `detect_rising_sectors()` returns at least one sector from your ETF list (market dependent)
- [ ] `score_peer_group()` ranks tickers within a test peer group correctly
- [ ] `run_laggard_screen()` returns candidates with catch_up_gap > 0
- [ ] `detect_divergences()` correctly finds a stock that underperformed its ETF by 5%+
- [ ] New divergence events appear in `divergence_labels` table
- [ ] `apply_scenario_label()` updates the row with scenario 1–4
- [ ] `fill_outcome_data()` runs without error (may return no updates if < 30 days old)

---

## Sprint 8 — Dashboard + Scheduler

**Goal:** Build the Streamlit control tower dashboard. Wire everything into a daily scheduler. Add email/Slack alerts.

---

### 8.1 Install Streamlit

```bash
pip install streamlit streamlit-autorefresh plotly
```

---

### 8.2 Create `dashboard/app.py`

```python
# dashboard/app.py
import streamlit as st

st.set_page_config(
    page_title="Hedge Fund Control Tower",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Control Tower")
st.caption("Decision support — you make the final call")

pages = {
    "Portfolio Overview": "dashboard/pages/overview.py",
    "Rebalance Suggestions": "dashboard/pages/rebalance.py",
    "Risk Dashboard": "dashboard/pages/risk.py",
    "Model Health": "dashboard/pages/models.py",
    "Laggard Screen": "dashboard/pages/screens.py",
    "ETF Divergence Labeler": "dashboard/pages/divergence_labeler.py",
}

# Run via: streamlit run dashboard/app.py
```

---

### 8.3 Create `dashboard/pages/rebalance.py` (core page)

```python
# dashboard/pages/rebalance.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import datetime

st.header("Rebalance suggestions")

today = str(datetime.date.today())

session = get_session()
result = session.execute(text("""
    SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return
    FROM model_outputs
    WHERE date = :date
    ORDER BY ABS(delta_weight) DESC
"""), {"date": today})
rows = result.fetchall()
session.close()

if not rows:
    st.info("No model outputs for today — run the daily pipeline first.")
else:
    df = pd.DataFrame(rows, columns=["Ticker", "Current %", "Suggested %", "Δ Weight", "BL Return"])
    df["Current %"]   = (df["Current %"] * 100).round(2)
    df["Suggested %"] = (df["Suggested %"] * 100).round(2)
    df["Δ Weight"]    = (df["Δ Weight"] * 100).round(2)
    df["BL Return"]   = (df["BL Return"] * 100).round(2)

    df["Action"] = df["Δ Weight"].apply(
        lambda x: "🟢 BUY" if x > 0.5 else ("🔴 SELL" if x < -0.5 else "✅ HOLD")
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Log an override")
    col1, col2, col3 = st.columns(3)
    with col1:
        ov_ticker = st.selectbox("Ticker", df["Ticker"].tolist())
    with col2:
        ov_action = st.number_input("Weight you're actually setting (%)", min_value=0.0, max_value=100.0, step=0.5)
    with col3:
        ov_reason = st.text_input("Reason")

    if st.button("Log override"):
        model_suggestion = float(df[df["Ticker"] == ov_ticker]["Suggested %"].values[0]) / 100
        session = get_session()
        session.execute(text("""
            INSERT INTO override_log (date, ticker, model_suggestion, action_taken, reason)
            VALUES (CURRENT_DATE, :ticker, :suggestion, :action, :reason)
        """), {"ticker": ov_ticker, "suggestion": model_suggestion,
               "action": ov_action / 100, "reason": ov_reason})
        session.commit()
        session.close()
        st.success(f"Override logged for {ov_ticker}")
```

---

### 8.4 Create `dashboard/pages/divergence_labeler.py`

```python
# dashboard/pages/divergence_labeler.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
from engine.screens.etf_divergence import apply_scenario_label

st.header("ETF divergence labeler")
st.caption("Label each divergence event. Your labels become ML training data.")

session = get_session()
result = session.execute(text("""
    SELECT id, ticker, etf_reference, detected_at,
           etf_return_pct, stock_return_pct, divergence_pct, scenario_label
    FROM divergence_labels
    WHERE scenario_label IS NULL
    ORDER BY detected_at DESC
    LIMIT 20
"""))
rows = result.fetchall()
session.close()

if not rows:
    st.success("No unlabeled divergence events.")
else:
    df = pd.DataFrame(rows, columns=["id", "ticker", "etf", "detected", "etf_ret", "stock_ret", "divergence", "label"])
    st.dataframe(df[["ticker", "etf", "detected", "etf_ret", "stock_ret", "divergence"]], hide_index=True)

    st.divider()
    st.subheader("Label a divergence")

    selected_id = st.selectbox("Select divergence ID", df["id"].tolist())
    selected = df[df["id"] == selected_id].iloc[0]
    st.write(f"**{selected['ticker']}** vs **{selected['etf']}** — detected {selected['detected']}")
    st.write(f"ETF return: **{selected['etf_ret']:.1%}** | Stock return: **{selected['stock_ret']:.1%}** | Divergence: **{selected['divergence']:.1%}**")

    st.markdown("""
    **Scenario guide:**
    - **1 — Temporary Rotation**: no bad news, capital rotating, ETF confirms macro. → Potential buy.
    - **2 — Stock-specific bad news**: identifiable catalyst, high volume, analyst downgrades. → Watch list.
    - **3 — Valuation compression**: prior large run, mean-reverting to fair value. → Wait.
    - **4 — Thesis break**: sustained divergence, insider selling, short interest rising. → Avoid / exit.
    """)

    scenario    = st.radio("Scenario", [1, 2, 3, 4], horizontal=True)
    confidence  = st.select_slider("Confidence", ["low", "medium", "high"])
    notes       = st.text_area("Notes (what are you seeing?)")

    checklist = {
        "negative_news":     st.checkbox("Is there identifiable negative news?"),
        "prior_large_run":   st.checkbox("Did the stock have a large prior run (>50%)?"),
        "divergence_weeks":  st.checkbox("Has divergence lasted more than 2 weeks?"),
        "peers_weak":        st.checkbox("Are peers in same sub-industry also quietly weak?"),
        "short_int_rising":  st.checkbox("Is short interest rising or insider selling present?"),
    }

    if st.button("Save label", type="primary"):
        apply_scenario_label(selected_id, scenario, confidence, notes, checklist)
        st.success(f"Scenario {scenario} saved for {selected['ticker']}")
        st.rerun()
```

---

### 8.5 Create `engine/scheduler.py`

```python
# engine/scheduler.py
"""
Daily pipeline scheduler. Run via: python engine/scheduler.py
Or schedule with cron: 0 22 * * 1-5 python /path/to/engine/scheduler.py
(22:00 UTC = after US market close)
"""
import logging
import datetime
import traceback
from portfolio.src.config import ASSET_UNIVERSE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

today = str(datetime.date.today())
tickers = ASSET_UNIVERSE[:50]   # start with top 50, expand as performance allows


def run_pipeline():
    logger.info(f"=== Daily pipeline starting: {today} ===")
    steps = [
        ("1. Data ingestion",    lambda: __import__("engine.data.ingestion", fromlist=["run_ingestion"]).run_ingestion(tickers, "2023-01-01", today)),
        ("2. Feature pipeline",  lambda: __import__("engine.features.feature_store", fromlist=["run_feature_pipeline"]).run_feature_pipeline(tickers, today)),
        ("3. Alpha models",      run_alpha_models),
        ("4. Divergence scan",   run_divergence_scan),
        ("5. Outcome fill",      lambda: __import__("engine.screens.etf_divergence", fromlist=["fill_outcome_data"]).fill_outcome_data()),
    ]

    for step_name, step_fn in steps:
        try:
            logger.info(f"Running: {step_name}")
            step_fn()
            logger.info(f"Done: {step_name}")
        except Exception as e:
            logger.error(f"FAILED: {step_name} — {e}")
            logger.error(traceback.format_exc())
            send_alert(f"Pipeline step failed: {step_name}\n{e}")

    logger.info(f"=== Daily pipeline complete: {today} ===")


def run_alpha_models():
    from engine.alpha.momentum import MomentumAlpha
    from engine.alpha.mean_reversion import MeanReversionAlpha
    from engine.alpha.vol_timing import VolTimingAlpha

    for model in [MomentumAlpha(), MeanReversionAlpha(), VolTimingAlpha()]:
        signals = model.generate_signals(today, tickers)
        if not signals.empty:
            model.persist_signals(today, signals)


def run_divergence_scan():
    from engine.screens.etf_divergence import detect_divergences, save_divergence_events
    divergences = detect_divergences(today)
    save_divergence_events(divergences)


def send_alert(message: str):
    """Extend this with email (smtplib) or Slack webhook as needed."""
    logger.critical(f"ALERT: {message}")
    # smtplib email implementation here


if __name__ == "__main__":
    run_pipeline()
```

---

### Sprint 8 Checklist

- [ ] `streamlit run dashboard/app.py` launches without error
- [ ] Rebalance page shows today's model outputs (after running scheduler)
- [ ] Divergence labeler shows unlabeled events from DB
- [ ] Saving a label updates the DB and refreshes the page
- [ ] Override log saves correctly — verify with `SELECT * FROM override_log`
- [ ] Scheduler runs all 5 steps without error on a test run
- [ ] Failed steps do not crash the entire pipeline
- [ ] `send_alert()` logs CRITICAL level (extend to email in production)

---

## Full System Checklist (End of All Sprints)

### Data integrity
- [ ] All price data in PostgreSQL — no flat files used for live data
- [ ] Validation logs visible in `data_validation_log`
- [ ] Polygon primary + yfinance fallback both tested
- [ ] Corporate actions: verify a known split date produces correct adj_close

### Alpha pipeline
- [ ] All 3 core alpha models (momentum, mean reversion, vol timing) producing signals daily
- [ ] PEAD engine wired as Alpha Model 4
- [ ] ML lab wired as Alpha Model 5 (even if just returning empty gracefully)
- [ ] Rolling IC tracked and updating after 20+ observations

### Portfolio construction
- [ ] BL posterior returns replace raw historical mean in optimizer
- [ ] Regime view correctly shifts benchmark return in high_stress
- [ ] Optimizer respects position limit (10%), sector limit (30%), leverage (1.0)
- [ ] Turnover penalty reduces unnecessary trading

### Risk
- [ ] Pre-trade checks block bad orders before queue
- [ ] Post-trade metrics (VaR, CVaR, drawdown) update after each rebalance
- [ ] Stress test values shown in dashboard
- [ ] Regime label + stress_score visible on dashboard gauge

### Execution
- [ ] Order queue generated from weight delta
- [ ] Manual trade confirmation logged to `trades` table
- [ ] Reconciliation runs before each rebalance suggestion

### Screens
- [ ] Laggard screen runs against at least 2 peer groups
- [ ] ETF divergence scanner detects events and saves to DB
- [ ] Divergence labeling UI functional — labels persist
- [ ] Outcome filling job runs daily without error

### Observability
- [ ] Dashboard shows: NAV, daily P&L, regime gauge, rebalance table, stress test, model IC
- [ ] Override log reviewable in dashboard
- [ ] Scheduler runs daily at market close (cron or APScheduler)
- [ ] Alert system fires on pipeline failure

---

## Technology Stack Reference

| Layer | Tool | Install |
|---|---|---|
| Database | PostgreSQL 15 (Docker) | `docker run postgres:15` |
| ORM / SQL | SQLAlchemy + psycopg2 | `pip install sqlalchemy psycopg2-binary` |
| Primary data | Polygon.io | `pip install polygon-api-client` |
| Fallback data | yfinance | already installed |
| Async fetch | aiohttp + tenacity | `pip install aiohttp tenacity` |
| Optimization | scipy (existing) | already installed |
| Stats / ML | arch (GARCH), hmmlearn, statsmodels | `pip install arch hmmlearn statsmodels` |
| Dashboard | Streamlit | `pip install streamlit plotly` |
| Scheduling | APScheduler or cron | `pip install apscheduler` |
| Alerts | smtplib (built-in) or slack_sdk | `pip install slack-sdk` |

---

## Key Principles to Keep in Mind

The system suggests. You decide. Every model output is a recommendation, not an instruction. The override log exists precisely because your judgment sometimes beats the model — and tracking when it does or doesn't is how you get better over time.

The divergence labels are the most valuable long-term asset in this system. Every label you add is a training example no dataset can buy. At 150–200 labeled observations with outcome data filled in, you have the foundation for your first classification model.

The BL model is self-correcting. When your alpha models have low IC (performing poorly), their views carry low confidence and BL stays close to market equilibrium. You don't need to manually adjust anything — the confidence weights do it automatically.

Your existing research code is production-quality. The `regime.py`, `factor_model.py`, and `correlation.py` files in `general_research/src/` are well-structured and mathematically sound. The sprints wrap them, not rewrite them.

---

*Document version 1.0 — Generated from todos analysis*
*Covers: trading_system_architecture.md, trading_system_deep_dive.md, quant_portfolio_framework-research.md, laggard_screen_strategy.md, etf_component_divergence_strategy.md, later-implementations.md*
*Current codebase: portfolio/, ml_quant_finance_research/ (general_research, quant_research, ml_research)*

# Implementation Guide — Addendum
### Gaps filled after full codebase review

Paste this at the end of `IMPLEMENTATION_GUIDE.md`. Everything below corrects or adds to the original guide based on reading your actual code.

---

## Sprint 0 — Backtest Integrity (Must Do Before Sprint 1)

**Why this was missing and why it matters first:** Your `backtest_portfolio.py` runs the real engine components (`run_all_scenarios`, `apply_trend_filter`, `calculate_log_returns`) on historical data. Before you build a production system on top of this, you need to know whether its results are trustworthy. Two bugs found in the existing backtester will silently inflate performance.

---

### 0.1 Bug fix — T+1 execution (currently T+0, causes look-ahead bias)

In `backtest_portfolio.py`, when `i % REBALANCE_DAYS == 0`, the code optimises on prices up to `current_date` and then immediately trades at `current_date`'s price. In reality you can't trade on the same bar you optimise on — prices aren't available until close, but you execute the next open.

**Current code (around line 155):**
```python
if i % REBALANCE_DAYS == 0:
    hist_slice = prices_df.loc[:current_date]
    # ... optimize ...
    # immediately trade at current_date prices  ← T+0 bug
```

**Fix — use next day's open price for execution:**
```python
if i % REBALANCE_DAYS == 0 and i + 1 < len(valid_dates):
    hist_slice = prices_df.loc[:current_date]      # optimise on today's close
    execution_date = valid_dates[i + 1]            # execute at tomorrow's open
    execution_prices = prices_df.loc[execution_date]

    # All trades below must use execution_prices, not latest_prices
    # Replace: latest_prices[ticker]
    # With:    execution_prices.get(ticker, latest_prices.get(ticker))
```

This is a single-day shift but over a 2-year backtest on a monthly rebalance schedule (24 rebalances) it can add 1–3% of spurious return by consistently buying at yesterday's price.

---

### 0.2 Bug fix — Static FX rate inflates USD returns in EUR terms

In `backtest_portfolio.py` line ~113:
```python
self.logger.info("Applying static 0.92 EUR/USD FX rate to US stocks...")
for col in prices_df.columns:
    if not any(col.endswith(s) for s in EUR_SUFFIXES):
        prices_df[col] = prices_df[col] * 0.92
```

Your `data_loader.py` already has `fetch_fx_rate()` which fetches the live rate and falls back to 0.92. But this is a **static scalar applied once** — it doesn't vary over time. In a 2023–2025 backtest, EUR/USD moved from ~1.07 to ~1.05 and back. A static 0.92 (which is the approximate 2022 low) applied to the entire history is wrong.

**Fix — apply a daily rolling FX rate in the backtester:**
```python
# After downloading prices_df, download FX history too
fx_data = yf.download("EURUSD=X", start=fetch_start.strftime('%Y-%m-%d'),
                      end=end_date.strftime('%Y-%m-%d'), auto_adjust=True, progress=False)
fx_series = fx_data["Close"].reindex(prices_df.index, method="ffill").fillna(0.92)

# In the simulation loop, compute usd_to_eur dynamically:
usd_to_eur = float(fx_series.get(current_date, 0.92))

# When pricing US positions:
for ticker, qty in current_holdings.items():
    price = latest_prices.get(ticker, 0.0)
    if not any(ticker.endswith(s) for s in ('.DE', '.AS', '.PA', '.L')):
        price = price * usd_to_eur   # dynamic, not static
    total_equity += qty * price
```

---

### 0.3 Walk-forward validation protocol (before any alpha model goes live)

The guide's Sprint 3 puts alpha models into the signals table and immediately wires them into BL. This is wrong — you don't know if they have any edge. Before a model influences real weights, it must pass this gate:

**Minimum IC threshold to go live:** Rolling 63-day IC must be > 0.05 (5%) for at least 21 consecutive trading days. Below this, the model's BL views get `omega = 999` (essentially zero weight — treated as pure noise).

Add this check to `engine/alpha/base.py`:

```python
def is_live_approved(self, min_ic: float = 0.05, min_consecutive_days: int = 21) -> bool:
    """
    A model should not influence real weights until it has demonstrated
    sustained IC above threshold. Returns False until approved.
    """
    session = get_session()
    result = session.execute(text("""
        SELECT date, AVG(confidence) as avg_ic
        FROM signals
        WHERE model_name = :model
          AND date >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY date
        ORDER BY date DESC
        LIMIT :days
    """), {"model": self.name, "days": min_consecutive_days + 5})
    rows = result.fetchall()
    session.close()

    if len(rows) < min_consecutive_days:
        return False   # not enough history yet

    recent_ics = [float(r[1]) for r in rows[:min_consecutive_days]]
    return all(ic >= min_ic for ic in recent_ics)
```

Then in `engine/portfolio/black_litterman.py`, modify `build_bl_views`:

```python
def build_bl_views(signals_df, tickers, models_dict):
    """models_dict: {model_name: AlphaModel instance}"""
    views = []
    for _, row in signals_df.iterrows():
        if row["ticker"] not in tickers:
            continue
        model = models_dict.get(row["model_name"])
        ic = max(0.01, float(row["confidence"]))

        # Gate: if model not live-approved, set omega extremely high
        if model and not model.is_live_approved():
            omega = 999.0   # effectively ignored by BL
        else:
            omega = 0.0004 / (ic ** 2)   # standard calibration

        views.append({
            "assets":  [row["ticker"]],
            "weights": [1.0],
            "Q":       float(row["expected_return"]),
            "omega":   omega,
        })
    return views
```

---

### 0.4 Out-of-sample regime split test

Before Sprint 4 (BL optimizer) goes live, run this test to verify the regime detection adds value:

```python
# Run once manually — not part of daily pipeline
def regime_split_backtest():
    """
    Splits history into high_stress and low_stress regimes using your
    existing composite_regime engine, then measures whether the trend
    filter (200MA) reduces drawdown in high_stress periods.
    """
    from ml_quant_finance_research.general_research.src.regime import compute_composite_regime
    import pandas as pd
    from portfolio.src.data_loader import fetch_historical, calculate_log_returns
    from portfolio.src.config import ASSET_UNIVERSE, BENCHMARK_TICKER

    prices = fetch_historical([BENCHMARK_TICKER], lookback_days=1260)  # 5 years
    log_ret = calculate_log_returns(prices)
    regime_df = compute_composite_regime(log_ret[BENCHMARK_TICKER], log_ret)

    # Split returns by regime
    ret_series = log_ret[BENCHMARK_TICKER]
    regime_df = regime_df.set_index("date")
    merged = ret_series.to_frame("ret").join(regime_df["regime"], how="inner")

    for regime in ["low_stress", "medium", "high_stress"]:
        subset = merged[merged["regime"] == regime]["ret"]
        ann_ret = subset.mean() * 252
        ann_vol = subset.std() * (252 ** 0.5)
        sharpe  = ann_ret / ann_vol if ann_vol > 0 else 0
        max_dd  = ((1 + subset).cumprod() / (1 + subset).cumprod().cummax() - 1).min()
        print(f"{regime:15s} | days={len(subset):4d} | ann_ret={ann_ret:+.2%} | sharpe={sharpe:.2f} | max_dd={max_dd:.2%}")

    # Expected output: high_stress should show lower sharpe/worse max_dd
    # confirming regime detection is adding real information
```

**Gate:** If `high_stress` Sharpe is NOT meaningfully lower than `low_stress`, the regime view in BL is adding noise not signal. Set `omega = 999` for regime views until this is confirmed.

---

## FX Handling — Correct Implementation

The original guide's feature pipeline and BL optimizer completely ignored the EUR/USD problem. Your `data_loader.py` already has the correct solution — it just needs to be promoted into the production engine properly.

### The problem

Your asset universe mixes:
- **EUR-priced** tickers: `.DE` (Xetra), `.AS` (Amsterdam), `.PA` (Paris) — prices in EUR
- **USD-priced** tickers: no suffix (`NVDA`, `AMZN`, etc.), `.L` (London, GBP) — prices in USD/GBP
- **Critical:** When you compute a covariance matrix mixing EUR and USD price series, you are measuring correlation between different currencies. A 10% return in NVDA (USD) is not the same as 10% return in SAP.DE (EUR) from your portfolio's perspective.

### The fix — apply dynamic FX in the ingestion layer, not ad-hoc

Modify `engine/data/ingestion.py` to apply FX conversion before storing to the DB. This means the `prices` table always contains EUR-equivalent prices.

```python
# Add to engine/data/ingestion.py

EUR_SUFFIXES = ('.DE', '.AS', '.PA')
GBP_SUFFIXES = ('.L',)

def fetch_fx_history(from_date: str, to_date: str) -> dict:
    """
    Returns daily FX rates as dicts: {date: rate}
    USDEUR and GBPEUR fetched from yfinance (same fallback logic as data_loader.py)
    """
    import yfinance as yf
    rates = {"USDEUR": {}, "GBPEUR": {}}
    pairs = {"USDEUR": "EURUSD=X", "GBPEUR": "GBPUSD=X"}   # note: yfinance gives USD/EUR not EUR/USD

    for name, pair in pairs.items():
        try:
            data = yf.download(pair, start=from_date, end=to_date, auto_adjust=True, progress=False)
            series = data["Close"].dropna()
            if name == "USDEUR":
                # EURUSD=X gives EUR per USD — we want USD per EUR so invert
                series = 1 / series
            for date, rate in series.items():
                rates[name][str(date.date())] = float(rate)
        except Exception as e:
            logging.warning(f"FX fetch failed for {pair}: {e} — using fallback 0.92/0.79")

    return rates


def apply_fx_conversion(df: pd.DataFrame, fx_rates: dict) -> pd.DataFrame:
    """
    Converts all non-EUR tickers to EUR using the daily FX rate.
    This is called inside persist_prices() BEFORE writing to DB.
    """
    df = df.copy()
    usd_eur = fx_rates.get("USDEUR", {})
    gbp_eur = fx_rates.get("GBPEUR", {})

    FALLBACK_USDEUR = 0.92
    FALLBACK_GBPEUR = 0.79

    for i, row in df.iterrows():
        ticker = row["ticker"]
        date_str = str(row["date"])

        if any(ticker.endswith(s) for s in EUR_SUFFIXES):
            continue   # already EUR — no conversion

        elif any(ticker.endswith(s) for s in GBP_SUFFIXES):
            rate = gbp_eur.get(date_str, FALLBACK_GBPEUR)
            for col in ["open", "high", "low", "close", "adj_close"]:
                if pd.notna(df.at[i, col]):
                    df.at[i, col] = df.at[i, col] * rate

        else:
            # Treat as USD (covers NVDA, AMZN, etc.)
            rate = usd_eur.get(date_str, FALLBACK_USDEUR)
            for col in ["open", "high", "low", "close", "adj_close"]:
                if pd.notna(df.at[i, col]):
                    df.at[i, col] = df.at[i, col] * rate

    return df
```

Then modify `run_ingestion()` to call this:

```python
def run_ingestion(tickers: list, from_date: str, to_date: str):
    df_raw = asyncio.run(fetch_all_async(tickers, from_date, to_date))
    df_clean = validate_prices(df_raw)

    # Fetch FX rates for the same period and convert before storing
    fx_rates = fetch_fx_history(from_date, to_date)
    df_eur = apply_fx_conversion(df_clean, fx_rates)

    persist_prices(df_eur)   # all prices in DB are now EUR-equivalent
    return df_eur
```

**Result:** Every downstream calculation — feature engineering, covariance matrix, BL optimizer, risk metrics — automatically works in a single currency. No conversion needed anywhere else.

---

## IC-to-Omega Calibration — Correct Formula

The original guide used `omega = 0.0004 / (ic ** 2)` which is a made-up number. Here is the correct derivation from the Black-Litterman literature.

### What omega actually is

Omega is the diagonal of the view uncertainty covariance matrix. The standard BL approach (He & Litterman 1999) sets:

```
Omega = diag( P @ (tau * Sigma) @ P.T )
```

This means each view's uncertainty is proportional to the variance of the portfolio the view represents, scaled by tau. This is the **proportional omega** assumption — it ensures views and the prior are on the same scale.

Your existing `factor_model.py`'s `black_litterman()` function already accepts omega as a raw scalar per view. Replace the ad-hoc formula with the correct one:

```python
# In engine/portfolio/black_litterman.py

def compute_view_omegas(
    P: np.ndarray,          # k × n pick matrix
    cov_matrix: np.ndarray, # n × n covariance
    tau: float,             # scalar — typically 0.05
    ic_weights: np.ndarray, # k-length array of IC values, one per view
) -> np.ndarray:
    """
    Computes view uncertainty matrix Omega using the proportional method,
    then scales each view by the inverse of its IC.

    A model with IC=0.10 (good) gets lower omega (more influence).
    A model with IC=0.02 (weak) gets higher omega (near ignored).

    Returns a k×k diagonal matrix.
    """
    # Base: proportional omega (He & Litterman standard)
    base_omega = np.diag(np.diag(P @ (tau * cov_matrix) @ P.T))

    # IC scaling: divide each diagonal element by IC^2
    # so higher IC = smaller omega = stronger view
    ic_scale = np.diag(1.0 / (np.clip(ic_weights, 0.01, 1.0) ** 2))

    return base_omega @ ic_scale   # element-wise product on diagonal


def build_bl_views_calibrated(
    signals_df: pd.DataFrame,
    tickers: list,
    cov_matrix: pd.DataFrame,
    tau: float = 0.05,
) -> list:
    """
    Drop-in replacement for build_bl_views() that uses the correct omega.
    """
    views = []
    for _, row in signals_df.iterrows():
        if row["ticker"] not in tickers:
            continue
        ticker_idx = tickers.index(row["ticker"])
        n = len(tickers)

        # Build single-row P matrix for this view
        P_row = np.zeros((1, n))
        P_row[0, ticker_idx] = 1.0

        Sigma = cov_matrix.loc[tickers, tickers].values
        ic = max(0.01, float(row["confidence"]))

        # Correct omega
        base = float((P_row @ (tau * Sigma) @ P_row.T)[0, 0])
        omega = base / (ic ** 2)

        views.append({
            "assets":  [row["ticker"]],
            "weights": [1.0],
            "Q":       float(row["expected_return"]),
            "omega":   omega,
        })
    return views
```

Update `run_black_litterman()` in `engine/portfolio/black_litterman.py` to call `build_bl_views_calibrated()` instead of `build_bl_views()`, passing in the covariance matrix.

---

## PEAD Alpha — Correct Interface

The original guide's `pead_alpha.py` called a non-existent `run_screener()` function. Here is the correct adapter based on the actual `run_engine.py` and `screener.py` interfaces.

### What the PEAD engine actually returns

`run_engine.run()` returns a `state` dict with this shape:
```python
{
    "active_setups": [
        {
            "ticker": "NVDA",
            "quality": "High",          # "High" / "Medium" / "Low"
            "direction": "bullish",
            "surprise_pct": 12.3,
            "entry_date": "2025-05-12",
            "drift_window": 45,
            "underreaction": True,
        },
        ...
    ],
    "performance": {
        "overall_hit_rate_21d": 0.64,
        "high_hit_rate_21d": 0.71,
        "overall_avg_drift_21d": 2.3,
        ...
    }
}
```

`screen_recent_earnings()` returns a DataFrame with columns:
`ticker, earnings_date, surprise_pct, pead_setup_quality, direction, entry_date, drift_21d, drift_63d, underreaction_flag, same_day_return, ...`

### Correct `engine/alpha/pead_alpha.py`

```python
# engine/alpha/pead_alpha.py
"""
Correct PEAD alpha adapter — uses the actual run_engine.run() interface.
The PEAD engine runs in its own directory with its own config imports,
so it must be invoked via subprocess or by temporarily adjusting sys.path.
"""
import sys
import os
import pandas as pd
import logging
from engine.alpha.base import AlphaModel

logger = logging.getLogger(__name__)

# Quality → expected return mapping (calibrated from PEAD hit rates in run_engine state)
# High quality setups historically hit 71% of the time (per pead_state performance)
# Medium: ~57%. Low: ~50% (coin flip — no edge, excluded)
QUALITY_RETURN_MAP = {
    "High":   0.035,   # +3.5% expected excess annualised
    "Medium": 0.015,   # +1.5% expected excess
    "Low":    0.000,   # excluded — no edge above baseline
    "Disqualified": 0.000,
}
DIRECTION_SIGN = {"bullish": 1, "bearish": -1}


class PEADAlpha(AlphaModel):
    name = "pead"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Runs the PEAD engine and converts active setups into alpha signals.
        The PEAD engine uses file-based CSV state (pead_setups.csv) —
        we read it directly rather than re-running the full engine each day.
        Scheduler runs the full engine weekly; daily we just read the state.
        """
        pead_db_path = os.path.join(
            "ml_quant_finance_research", "quant_research",
            "pead_engine", "data", "pead_setups.csv"
        )

        if not os.path.exists(pead_db_path):
            logger.warning("PEAD: pead_setups.csv not found — run pead_engine first")
            return pd.DataFrame()

        try:
            setups = pd.read_csv(pead_db_path)
        except Exception as e:
            logger.warning(f"PEAD: failed to read pead_setups.csv: {e}")
            return pd.DataFrame()

        # Filter to active setups: entry_date is within the last 5 trading days
        # and ticker is in our universe
        setups["entry_date"] = pd.to_datetime(setups["entry_date"], errors="coerce")
        current_date = pd.Timestamp(date)
        active_window = current_date - pd.Timedelta(days=7)

        active = setups[
            (setups["entry_date"] >= active_window) &
            (setups["entry_date"] <= current_date) &
            (setups["ticker"].isin(tickers)) &
            (setups["pead_setup_quality"].isin(["High", "Medium"]))
        ].copy()

        if active.empty:
            logger.info(f"PEAD: no active setups for {date}")
            return pd.DataFrame()

        ic = self.compute_rolling_ic()
        rows = []

        for _, row in active.iterrows():
            quality    = row.get("pead_setup_quality", "Low")
            direction  = row.get("direction", "bullish")
            surprise   = float(row.get("surprise_pct", 0))
            underreact = bool(row.get("underreaction_flag", False))

            base_return = QUALITY_RETURN_MAP.get(quality, 0.0)
            if base_return == 0.0:
                continue

            sign = DIRECTION_SIGN.get(direction, 1)
            # Boost expected return if underreaction confirmed
            multiplier = 1.3 if underreact else 1.0
            expected_return = sign * base_return * multiplier

            # Raw score: normalised surprise magnitude (0–1 scale vs max valid 200%)
            raw_score = min(abs(surprise) / 20.0, 1.0) * sign

            rows.append({
                "ticker":          row["ticker"],
                "expected_return": round(expected_return, 4),
                "confidence":      ic,
                "raw_score":       raw_score,
            })

        result = pd.DataFrame(rows)
        logger.info(f"PEAD: {len(result)} signals generated for {date}")
        return result


def run_pead_engine_weekly():
    """
    Call this from the scheduler once per week (not daily) to refresh
    the PEAD setups file. The full engine is slow (fetches earnings from yfinance).
    Add to scheduler.py:
        if datetime.date.today().weekday() == 0:   # Monday only
            run_pead_engine_weekly()
    """
    pead_dir = os.path.join(
        "ml_quant_finance_research", "quant_research", "pead_engine"
    )
    original_dir = os.getcwd()
    try:
        os.chdir(pead_dir)
        # Temporarily add pead_engine dir to path for its local config imports
        sys.path.insert(0, ".")
        from run_engine import run
        state = run(force_refresh=False, lookback_days=90, backfill_models=False)
        logger.info(f"PEAD engine refreshed: {len(state.get('active_setups', []))} active setups")
        return state
    except Exception as e:
        logger.error(f"PEAD weekly refresh failed: {e}")
        return {}
    finally:
        os.chdir(original_dir)
        sys.path.pop(0)
```

**Important scheduler change** — in `engine/scheduler.py`, PEAD runs weekly not daily:

```python
def run_pipeline():
    # ... existing steps 1-4 ...

    # Step 6: PEAD — weekly only (Monday)
    if datetime.date.today().weekday() == 0:
        try:
            logger.info("6. PEAD engine weekly refresh")
            from engine.alpha.pead_alpha import run_pead_engine_weekly
            run_pead_engine_weekly()
        except Exception as e:
            logger.error(f"PEAD weekly refresh failed: {e}")

    # Step 7: PEAD signals — read from file daily
    try:
        logger.info("7. PEAD alpha signals")
        pead = PEADAlpha()
        signals = pead.generate_signals(today, tickers)
        if not signals.empty:
            pead.persist_signals(today, signals)
    except Exception as e:
        logger.error(f"PEAD signals failed: {e}")
```

---

## ML Alpha — Correct Interface

The original guide assumed a `predictions_{date}.csv` file that doesn't exist. The ML lab writes to `portfolio/data/ml_state.json`. Here is the correct adapter.

### What `ml_state.json` actually contains

```json
{
    "model_signals": {
        "NVDA": {
            "up_proba_21d": 0.6823,
            "auc": 0.5934,
            "last_price": 875.40,
            "vol_ann": 0.5821,
            "sector": "Technology"
        },
        ...
    },
    "ensemble": {
        "weighted_score": 0.5821,
        "verdict": "BROADLY BULLISH",
        "n_tickers": 12
    },
    "generated_at": "2025-05-10T14:32:11"
}
```

### Correct `engine/alpha/ml_alpha.py`

```python
# engine/alpha/ml_alpha.py
"""
Correct ML alpha adapter — reads from portfolio/data/ml_state.json.
The ML pipeline (run_ml_pipeline.py) writes this file after each full run.
It takes ~20-40 minutes to run; schedule it weekly or on weekends.
"""
import json
import os
import pandas as pd
import logging
from datetime import datetime, timedelta
from engine.alpha.base import AlphaModel

logger = logging.getLogger(__name__)

ML_STATE_PATH = os.path.join("portfolio", "data", "ml_state.json")

# AUC-to-confidence threshold: models with AUC < 0.53 have no meaningful edge
MIN_AUC_TO_USE = 0.53

# Convert up_proba to expected return:
# up_proba=0.65 → (0.65-0.5)*2 = 0.30 → scaled by 0.04 = +1.2% expected excess
RETURN_SCALE = 0.04


class MLAlpha(AlphaModel):
    name = "ml_model"

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Reads ml_state.json and converts up_proba_21d signals into
        expected returns. Uses AUC as the confidence/IC proxy.
        """
        if not os.path.exists(ML_STATE_PATH):
            logger.warning(f"ML: {ML_STATE_PATH} not found — run run_ml_pipeline.py first")
            return pd.DataFrame()

        try:
            with open(ML_STATE_PATH) as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"ML: failed to read ml_state.json: {e}")
            return pd.DataFrame()

        # Staleness check — warn if file is more than 8 days old
        generated_at = state.get("generated_at", "")
        if generated_at:
            try:
                generated_dt = datetime.fromisoformat(generated_at)
                age_days = (datetime.now() - generated_dt).days
                if age_days > 8:
                    logger.warning(f"ML: ml_state.json is {age_days} days old — consider re-running pipeline")
            except Exception:
                pass

        model_signals = state.get("model_signals", {})
        if not model_signals:
            logger.warning("ML: model_signals is empty in ml_state.json")
            return pd.DataFrame()

        ic = self.compute_rolling_ic()
        rows = []

        for ticker, signal in model_signals.items():
            if ticker not in tickers:
                continue

            up_proba = float(signal.get("up_proba_21d", 0.5))
            auc      = float(signal.get("auc", 0.5))

            # Gate: if this ticker's model has no edge, skip
            if auc < MIN_AUC_TO_USE:
                logger.debug(f"ML: skipping {ticker} — AUC {auc:.3f} below threshold")
                continue

            # Convert probability to expected return
            # up_proba=0.5 → 0 expected return (no edge)
            # up_proba=0.65 → positive expected return
            # up_proba=0.35 → negative expected return (bearish signal)
            prob_edge = (up_proba - 0.5) * 2   # [-1, +1]
            expected_return = prob_edge * RETURN_SCALE

            # Use AUC directly as confidence (replaces IC for ML models)
            # AUC=0.53 → weak, AUC=0.65 → strong
            confidence = min(max((auc - 0.5) * 4, 0.01), 1.0)   # rescale 0.5-0.75 AUC → 0-1

            rows.append({
                "ticker":          ticker,
                "expected_return": round(expected_return, 4),
                "confidence":      round(confidence, 4),
                "raw_score":       round(up_proba, 4),
            })

        result = pd.DataFrame(rows)
        logger.info(f"ML: {len(result)} signals generated (of {len(model_signals)} in state)")
        return result


def run_ml_pipeline_refresh():
    """
    Call from scheduler on weekends or low-priority windows.
    The full pipeline takes 20-40 minutes depending on universe size.
    Add to scheduler.py:
        if datetime.date.today().weekday() == 5:   # Saturday
            run_ml_pipeline_refresh()
    """
    ml_lab_path = os.path.join(
        "ml_quant_finance_research", "ml_research", "stock_ml_lab"
    )
    original_dir = os.getcwd()
    try:
        os.chdir(ml_lab_path)
        import subprocess
        result = subprocess.run(
            ["python", "run_ml_pipeline.py"],
            capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            logger.error(f"ML pipeline failed: {result.stderr[-500:]}")
        else:
            logger.info("ML pipeline complete — ml_state.json updated")
    except subprocess.TimeoutExpired:
        logger.error("ML pipeline timed out after 60 minutes")
    except Exception as e:
        logger.error(f"ML pipeline refresh error: {e}")
    finally:
        os.chdir(original_dir)
```

**Complete scheduler with correct run frequencies:**

```python
# engine/scheduler.py — replace the existing version

import logging
import datetime
import traceback
from portfolio.src.config import ASSET_UNIVERSE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

today = str(datetime.date.today())
weekday = datetime.date.today().weekday()   # 0=Mon, 5=Sat, 6=Sun
tickers = ASSET_UNIVERSE[:50]


def run_pipeline():
    logger.info(f"=== Daily pipeline: {today} (weekday={weekday}) ===")

    # ── Daily steps (every trading day) ───────────────────────────────────
    _run_step("1. Data ingestion", lambda: (
        __import__("engine.data.ingestion", fromlist=["run_ingestion"])
        .run_ingestion(tickers, "2023-01-01", today)
    ))

    _run_step("2. Feature pipeline", lambda: (
        __import__("engine.features.feature_store", fromlist=["run_feature_pipeline"])
        .run_feature_pipeline(tickers, today)
    ))

    _run_step("3. Momentum alpha", lambda: _run_alpha("momentum"))
    _run_step("4. Mean reversion alpha", lambda: _run_alpha("mean_reversion"))
    _run_step("5. Vol timing alpha", lambda: _run_alpha("vol_timing"))

    _run_step("6. PEAD signals (from file)", lambda: _run_alpha("pead"))

    _run_step("7. ML signals (from file)", lambda: _run_alpha("ml_model"))

    _run_step("8. ETF divergence scan", lambda: (
        __import__("engine.screens.etf_divergence",
                   fromlist=["detect_divergences", "save_divergence_events"])
    ))

    _run_step("9. Outcome fill", lambda: (
        __import__("engine.screens.etf_divergence", fromlist=["fill_outcome_data"])
        .fill_outcome_data()
    ))

    # ── Weekly steps ───────────────────────────────────────────────────────
    if weekday == 0:   # Monday
        _run_step("W1. PEAD engine full refresh", lambda: (
            __import__("engine.alpha.pead_alpha", fromlist=["run_pead_engine_weekly"])
            .run_pead_engine_weekly()
        ))

    # ── Weekend steps ──────────────────────────────────────────────────────
    if weekday == 5:   # Saturday
        _run_step("WE1. ML pipeline full refresh", lambda: (
            __import__("engine.alpha.ml_alpha", fromlist=["run_ml_pipeline_refresh"])
            .run_ml_pipeline_refresh()
        ))

    logger.info(f"=== Pipeline complete: {today} ===")


def _run_alpha(model_name: str):
    from engine.alpha.momentum import MomentumAlpha
    from engine.alpha.mean_reversion import MeanReversionAlpha
    from engine.alpha.vol_timing import VolTimingAlpha
    from engine.alpha.pead_alpha import PEADAlpha
    from engine.alpha.ml_alpha import MLAlpha

    model_map = {
        "momentum":      MomentumAlpha(),
        "mean_reversion": MeanReversionAlpha(),
        "vol_timing":    VolTimingAlpha(),
        "pead":          PEADAlpha(),
        "ml_model":      MLAlpha(),
    }
    model = model_map[model_name]
    signals = model.generate_signals(today, tickers)
    if not signals.empty:
        model.persist_signals(today, signals)
    return signals


def _run_step(name: str, fn):
    try:
        logger.info(f"Running: {name}")
        fn()
    except Exception as e:
        logger.error(f"FAILED: {name} — {e}")
        logger.error(traceback.format_exc())
        send_alert(f"Pipeline step failed: {name}\n{e}")


def send_alert(message: str):
    logger.critical(f"ALERT: {message}")


if __name__ == "__main__":
    run_pipeline()
```

---

## Data Loader Migration Path

The original guide said `data_loader.py` "will be extended" with no specifics. Here is the exact migration plan so you don't end up with two separate data pipelines.

**Phase A (Sprint 1):** Keep `portfolio/src/data_loader.py` exactly as is. The existing `portfolio/` app continues to use it. The new `engine/data/ingestion.py` is a separate pipeline writing to PostgreSQL.

**Phase B (Sprint 4, after BL is wired):** Add a DB-backed fetch path to `data_loader.py` so the portfolio app can optionally read from PostgreSQL instead of yfinance:

```python
# Add to portfolio/src/data_loader.py

def fetch_from_db(tickers: list, lookback_days: int = 504):
    """
    Alternative to fetch_historical() — reads from PostgreSQL.
    Falls back to fetch_historical() if DB unavailable.
    """
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        result = session.execute(text("""
            SELECT date, ticker, adj_close FROM prices
            WHERE ticker = ANY(:tickers)
            ORDER BY date ASC
        """), {"tickers": tickers})
        rows = result.fetchall()
        session.close()

        if not rows:
            raise ValueError("No data in DB — falling back to yfinance")

        df = pd.DataFrame(rows, columns=["date", "ticker", "adj_close"])
        pivot = df.pivot(index="date", columns="ticker", values="adj_close")
        pivot.index = pd.to_datetime(pivot.index)
        return pivot.tail(lookback_days)

    except Exception as e:
        logging.warning(f"DB fetch failed ({e}) — falling back to yfinance")
        return fetch_historical(tickers, lookback_days)
```

**Phase C (Sprint 6, after reconciliation):** Replace `load_ledger()` with DB reads from `positions_history`. Your `ledger.csv` becomes the initial import source, not the ongoing truth.

```python
# Migration script — run once during Sprint 6
def migrate_ledger_to_db(ledger_path: str = "portfolio/data/ledger.csv"):
    """
    One-time migration: reads ledger.csv and imports positions into positions_history.
    After this runs, the DB is the source of truth and ledger.csv is archived.
    """
    holdings, cash = load_ledger(ledger_path)
    from engine.db.db import get_session
    from sqlalchemy import text
    import datetime

    session = get_session()
    today = str(datetime.date.today())

    for ticker, qty in holdings.items():
        session.execute(text("""
            INSERT INTO positions_history (date, ticker, quantity, price, value_eur, weight)
            VALUES (:date, :ticker, :qty, NULL, NULL, NULL)
        """), {"date": today, "ticker": ticker, "qty": qty})

    session.commit()
    session.close()
    logging.info(f"Migrated {len(holdings)} positions from ledger.csv to DB.")
    logging.info(f"Archive ledger.csv — do not delete, keep as audit trail.")
```

---

## Dashboard — Missing Pages

The original guide only implemented the rebalance page and divergence labeler. Here are the remaining pages that are 60% of the dashboard's value.

### `dashboard/pages/risk.py`

```python
# dashboard/pages/risk.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session

st.header("Risk dashboard")

session = get_session()
metrics = session.execute(text("""
    SELECT metric_name, metric_value FROM risk_metrics
    WHERE date = (SELECT MAX(date) FROM risk_metrics)
""")).fetchall()
session.close()

if not metrics:
    st.info("No risk metrics yet — run the pipeline first.")
else:
    m = {r[0]: r[1] for r in metrics}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("VaR 95%",     f"{m.get('var_95', 0):.2%}")
    col2.metric("CVaR 95%",    f"{m.get('cvar_95', 0):.2%}")
    col3.metric("Max Drawdown",f"{m.get('max_drawdown', 0):.2%}")
    col4.metric("Regime",       m.get("regime", "—"))

    st.divider()
    st.subheader("Stress test")
    stress_keys = [k for k in m if k.startswith("stress_")]
    if stress_keys:
        stress_df = pd.DataFrame([
            {"Scenario": k.replace("stress_", "").replace("_", " ").title(),
             "Portfolio Impact": f"{m[k]:.2%}"}
            for k in stress_keys
        ])
        st.dataframe(stress_df, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Regime gauge")
    stress_score = m.get("stress_score", 0.5)
    regime = m.get("regime", "medium")
    colour = {"low_stress": "🟢", "medium": "🟡", "high_stress": "🔴"}.get(regime, "⚪")
    st.markdown(f"### {colour} {regime.replace('_', ' ').title()} — stress score: {stress_score:.2f}")
    st.progress(float(stress_score))
    st.caption("Composite of realised volatility (60%) + correlation compression (40%)")
```

### `dashboard/pages/models.py`

```python
# dashboard/pages/models.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session

st.header("Model health")
st.caption("Information Coefficient (IC) = correlation between signal and next-day return. "
           "IC > 0.05 for 21 consecutive days required before a model influences weights.")

session = get_session()
rows = session.execute(text("""
    SELECT model_name,
           AVG(confidence) as avg_ic,
           COUNT(*) as signal_count,
           MIN(date) as first_date,
           MAX(date) as last_date
    FROM signals
    WHERE date >= CURRENT_DATE - INTERVAL '63 days'
    GROUP BY model_name
    ORDER BY avg_ic DESC
""")).fetchall()
session.close()

if not rows:
    st.info("No signals yet.")
else:
    df = pd.DataFrame(rows, columns=["Model", "Avg IC (63d)", "Signal count", "First date", "Last date"])
    df["Status"] = df["Avg IC (63d)"].apply(
        lambda ic: "🟢 Live" if ic >= 0.05 else "🔴 Paper only"
    )
    df["Avg IC (63d)"] = df["Avg IC (63d)"].map("{:.4f}".format)
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Override log — model vs actual")
    session = get_session()
    overrides = session.execute(text("""
        SELECT date, ticker, model_suggestion, action_taken, reason, outcome_30d
        FROM override_log
        ORDER BY date DESC LIMIT 20
    """)).fetchall()
    session.close()

    if overrides:
        ov_df = pd.DataFrame(overrides, columns=[
            "Date", "Ticker", "Model suggested", "You set", "Reason", "30d outcome"
        ])
        st.dataframe(ov_df, hide_index=True, use_container_width=True)
        st.caption("30d outcome: positive = your override outperformed the model suggestion")
    else:
        st.info("No overrides logged yet.")
```

### `dashboard/pages/overview.py`

```python
# dashboard/pages/overview.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import datetime

st.header("Portfolio overview")

session = get_session()

# Latest positions
positions = session.execute(text("""
    SELECT DISTINCT ON (ticker) ticker, quantity, price, value_eur, weight
    FROM positions_history
    ORDER BY ticker, date DESC
""")).fetchall()

# Recent trades
trades = session.execute(text("""
    SELECT date, ticker, action, quantity, price_eur, value_eur, notes
    FROM trades
    ORDER BY date DESC LIMIT 10
""")).fetchall()

session.close()

if positions:
    pos_df = pd.DataFrame(positions, columns=["Ticker", "Qty", "Price (€)", "Value (€)", "Weight"])
    pos_df["Weight"] = pos_df["Weight"].map(lambda x: f"{x:.1%}" if x else "—")
    total_value = sum(r[3] for r in positions if r[3])
    st.metric("Total portfolio value", f"€{total_value:,.2f}")
    st.dataframe(pos_df, hide_index=True, use_container_width=True)
else:
    st.info("No positions in DB yet — run migration or enter positions via reconciliation.")

st.divider()
st.subheader("Recent trades")
if trades:
    t_df = pd.DataFrame(trades, columns=["Date", "Ticker", "Action", "Qty", "Price (€)", "Value (€)", "Notes"])
    st.dataframe(t_df, hide_index=True, use_container_width=True)
else:
    st.info("No trades logged yet.")
```

---

## Environment Setup — Missing from Original Guide

The original guide had no `.env` or secrets management. This matters from Sprint 1 because your Polygon API key must never be hardcoded.

### Create `.env` in project root

```bash
# hedge-fund/.env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/hedgefund
POLYGON_API_KEY=your_polygon_key_here
ALERT_EMAIL=your@email.com
ALERT_EMAIL_PASSWORD=your_app_password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

### Add to `.gitignore`

```
.env
*.csv
*.json
!portfolio/data/ml_state.json   # keep this one — it's output not secrets
__pycache__/
*.pyc
```

### Load in `engine/db/db.py`

```python
# Add to top of engine/db/db.py
from dotenv import load_dotenv
load_dotenv()   # reads .env from project root

import os
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/hedgefund")
```

```bash
pip install python-dotenv
```

---

## Updated Full System Checklist

Add these items to the end of the original Sprint 8 checklist:

### Sprint 0 (Backtest integrity)
- [ ] T+0 bug fixed — execution uses next day's prices, not same day
- [ ] Static FX rate replaced with daily rolling EURUSD=X rate
- [ ] `regime_split_backtest()` run — high_stress Sharpe is lower than low_stress (confirms regime detection adds value)
- [ ] `is_live_approved()` returns False for all models at Sprint 3 start (insufficient history)

### FX handling
- [ ] `fetch_fx_history()` fetches USDEUR and GBPEUR history
- [ ] All prices in `prices` table are EUR-equivalent (verify: NVDA price ≈ 800 * 0.92 = €736, not $800)
- [ ] `.L` tickers (BP.L, AZN.L) converted from GBP to EUR correctly

### IC calibration
- [ ] `compute_view_omegas()` uses proportional method (P @ tau*Sigma @ P.T), not hardcoded 0.0004
- [ ] BL posterior returns change meaningfully when IC doubles (test with IC=0.02 vs IC=0.10)

### Alpha model gates
- [ ] `is_live_approved()` gate prevents model from influencing weights with < 21 days of IC history
- [ ] PEAD reads from `pead_setups.csv`, not from a non-existent function call
- [ ] ML reads from `portfolio/data/ml_state.json`, not from a non-existent predictions file
- [ ] PEAD engine runs weekly (Monday), not daily
- [ ] ML pipeline runs on Saturday, not daily

### Data loader migration
- [ ] `migrate_ledger_to_db()` run once — existing positions in `positions_history`
- [ ] `ledger.csv` archived (not deleted)
- [ ] `fetch_from_db()` added to `data_loader.py` as optional path

### Dashboard completeness
- [ ] Risk page shows VaR, CVaR, drawdown, stress test table, regime gauge
- [ ] Model health page shows IC per model + live approval status
- [ ] Overview page shows current positions and recent trades
- [ ] All 5 pages load without error

### Environment
- [ ] `.env` file created with DATABASE_URL and POLYGON_API_KEY
- [ ] `.env` in `.gitignore` — verify with `git status` that it does not appear
- [ ] `load_dotenv()` called before any `os.getenv()` usage
- [ ] `python-dotenv` in requirements

---

*Addendum version 1.0 — corrects and extends IMPLEMENTATION_GUIDE.md*
*Based on full read of: backtest_portfolio.py, data_loader.py, pead_engine/screener.py, pead_engine/run_engine.py, pead_engine/config.py, pead_engine/regression_model.py, stock_ml_lab/run_ml_pipeline.py, stock_ml_lab/utils/ (all 4 files)*