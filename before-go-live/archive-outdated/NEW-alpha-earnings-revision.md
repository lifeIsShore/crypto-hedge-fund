> **STATUS (2026-08-09, verified by Claude): NOT IMPLEMENTED.** This file was found sitting in `archive-implemented/` but no corresponding code exists — `engine/alpha/` has no `earnings_revision.py`, and there is no `fundamental_data` table or `fundamental_ingestion.py`. It was archived in error at some point (possibly by a different tool session) without the work actually being done. Moved back here as genuinely open. Verify against the live repo again before starting, since some time has passed.

# New Alpha Model: Earnings Revision Momentum
# `engine/alpha/earnings_revision.py`
# Estimated time: 1 day. Source: yfinance .info dict (free, no new API key)

---

## What this model does

When Wall Street analysts revise their earnings estimates upward, stocks
tend to outperform for 3–6 months. This is called the Earnings Revision
factor — one of the most robust and well-documented anomalies in academic
finance (documented by Hawkins, Chamberlin, and Daniel (1984) and replicated
consistently since).

The logic is simple: analysts are slow to update their models. When one
analyst revises up, others follow. The stock re-rates over weeks, not days.

Your PEAD model captures post-announcement drift. This model captures
pre-announcement estimate revision drift — they are complementary signals
on different time horizons.

---

## Data source

`yfinance` Ticker `.info` dict. Already in your stack. Free. No new key needed.

Relevant fields:
```python
info = yf.Ticker('NVDA').info
info['earningsGrowth']         # YoY EPS growth (latest quarter vs year ago)
info['revenueGrowth']          # YoY revenue growth
info['trailingEps']            # trailing 12-month EPS
info['forwardEps']             # consensus forward EPS estimate
info['earningsQuarterlyGrowth'] # QoQ growth rate
```

The key signal is: `forward_eps / trailing_eps - 1` = implied earnings growth
from consensus. When this has increased since the last reading (analyst upgrade),
it predicts outperformance.

---

## Implementation

### Step 1 — New table: `fundamental_data`

Add to `schema.sql`:
```sql
CREATE TABLE IF NOT EXISTS fundamental_data (
    date          TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    field         TEXT NOT NULL,
    value         REAL,
    fetched_at    TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker, field)
);
CREATE INDEX IF NOT EXISTS idx_fundamental_date ON fundamental_data (date, ticker);
```

### Step 2 — Weekly fundamental ingestion

Create `engine/data/fundamental_ingestion.py`:

```python
"""
fundamental_ingestion.py — Weekly fetch of per-ticker fundamental data.
Runs Sundays (light, no market data). ~3 minutes for 130 tickers.
Uses yfinance .info dict. Graceful fallback — missing fields are skipped.
"""
import yfinance as yf
import pandas as pd
import logging
import time
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Fields to fetch from yfinance .info
FUNDAMENTAL_FIELDS = {
    'trailing_eps':     'trailingEps',
    'forward_eps':      'forwardEps',
    'earnings_growth':  'earningsGrowth',
    'revenue_growth':   'revenueGrowth',
    'pe_ratio':         'trailingPE',
    'forward_pe':       'forwardPE',
    'pb_ratio':         'priceToBook',
    'ps_ratio':         'priceToSalesTrailing12Months',
    'roe':              'returnOnEquity',
    'debt_to_equity':   'debtToEquity',
    'free_cashflow':    'freeCashflow',
    'market_cap':       'marketCap',
    'short_ratio':      'shortRatio',
    'short_float_pct':  'shortPercentOfFloat',
}


def fetch_fundamentals_for_ticker(ticker: str) -> dict:
    """Fetch .info dict for one ticker. Returns {} on failure."""
    try:
        info = yf.Ticker(ticker).info
        result = {}
        for our_name, yf_key in FUNDAMENTAL_FIELDS.items():
            val = info.get(yf_key)
            if val is not None and isinstance(val, (int, float)) and not pd.isna(val):
                result[our_name] = float(val)
        return result
    except Exception as e:
        logger.warning(f"[fundamentals] {ticker}: fetch failed: {e}")
        return {}


def run_fundamental_ingestion(tickers: list, date: str = None) -> int:
    """
    Fetches fundamentals for all tickers and writes to fundamental_data table.
    Designed to run weekly (Sundays) — not daily.
    Returns count of (ticker, field) pairs written.
    """
    import datetime
    if date is None:
        date = str(datetime.date.today())

    logger.info(f"[fundamentals] Starting weekly fetch for {len(tickers)} tickers")
    session = get_session()
    count = 0

    for i, ticker in enumerate(tickers):
        fields = fetch_fundamentals_for_ticker(ticker)
        if not fields:
            continue

        for field, value in fields.items():
            try:
                session.execute(text("""
                    INSERT INTO fundamental_data (date, ticker, field, value)
                    VALUES (:date, :ticker, :field, :value)
                    ON CONFLICT (date, ticker, field) DO UPDATE SET
                        value      = :value,
                        fetched_at = datetime('now')
                """), {'date': date, 'ticker': ticker, 'field': field, 'value': value})
                count += 1
            except Exception as e:
                logger.warning(f"[fundamentals] DB write failed for {ticker}/{field}: {e}")

        if (i + 1) % 10 == 0:
            session.commit()
            logger.info(f"[fundamentals] {i+1}/{len(tickers)} tickers processed")
            time.sleep(0.3)   # polite yfinance rate limiting

    session.commit()
    session.close()
    logger.info(f"[fundamentals] Complete: {count} (ticker, field) pairs written for {date}")
    return count
```

### Step 3 — The alpha model

Create `engine/alpha/earnings_revision.py`:

```python
"""
Alpha Model 6 — Earnings Revision Momentum.

Signal: change in (forward_eps / trailing_eps) since last reading.
Positive revision (analysts raised estimates) → buy signal.
Negative revision (analysts cut estimates) → sell signal.

This model only covers tickers where yfinance provides EPS estimates.
Typically ~70% of TRADEABLE_UNIVERSE. Missing tickers generate no signal
(BL treats them as no-view, which is correct — not a missing-data problem).

Return scale: ±3.5% annualised excess. Horizon: 3–6 months.
"""
import pandas as pd
import logging
from sqlalchemy import text
from engine.alpha.base import AlphaModel
from engine.db.db import get_session

logger = logging.getLogger(__name__)

RETURN_SCALE   = 0.035
LOOKBACK_WEEKS = 4    # compare current estimate to reading from 4 weeks ago


class EarningsRevisionAlpha(AlphaModel):
    name = 'earnings_revision'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        session = get_session()
        try:
            # Get latest forward_eps and trailing_eps for each ticker
            rows_current = session.execute(text("""
                SELECT ticker, field, value
                FROM fundamental_data
                WHERE date = (
                    SELECT MAX(date) FROM fundamental_data
                    WHERE date <= :date
                )
                AND ticker IN ({})
                AND field IN ('forward_eps', 'trailing_eps', 'earnings_growth')
            """.format(','.join([f"'{t}'" for t in tickers]))), {'date': date}).fetchall()

            # Get reading from ~4 weeks ago
            rows_prior = session.execute(text("""
                SELECT ticker, field, value
                FROM fundamental_data
                WHERE date = (
                    SELECT MAX(date) FROM fundamental_data
                    WHERE date <= date(:date, '-28 days')
                )
                AND ticker IN ({})
                AND field IN ('forward_eps', 'trailing_eps')
            """.format(','.join([f"'{t}'" for t in tickers]))), {'date': date}).fetchall()

        finally:
            session.close()

        if not rows_current:
            logger.warning("[earnings_revision] No fundamental data in DB — run fundamental ingestion first")
            return pd.DataFrame()

        # Pivot current
        curr_df = pd.DataFrame(rows_current, columns=['ticker', 'field', 'value'])
        curr_pivot = curr_df.pivot(index='ticker', columns='field', values='value')

        # Implied forward growth rate (current)
        signals = {}
        for ticker in curr_pivot.index:
            fwd = curr_pivot.loc[ticker].get('forward_eps')
            trail = curr_pivot.loc[ticker].get('trailing_eps')
            if fwd and trail and trail != 0 and fwd > 0:
                signals[ticker] = {'current_growth': (fwd / trail) - 1}

        if not signals:
            return pd.DataFrame()

        # Prior reading for revision delta
        if rows_prior:
            prior_df = pd.DataFrame(rows_prior, columns=['ticker', 'field', 'value'])
            prior_pivot = prior_df.pivot(index='ticker', columns='field', values='value')
            for ticker in prior_pivot.index:
                if ticker not in signals:
                    continue
                fwd_p = prior_pivot.loc[ticker].get('forward_eps')
                trail_p = prior_pivot.loc[ticker].get('trailing_eps')
                if fwd_p and trail_p and trail_p != 0 and fwd_p > 0:
                    prior_growth = (fwd_p / trail_p) - 1
                    signals[ticker]['prior_growth'] = prior_growth
                    signals[ticker]['revision_delta'] = (
                        signals[ticker]['current_growth'] - prior_growth
                    )

        ic = self.compute_rolling_ic()
        rows_out = []

        for ticker, data in signals.items():
            revision = data.get('revision_delta', data.get('current_growth', 0))
            # Clip extreme revisions (earnings surprises can be huge)
            revision = max(-0.5, min(0.5, revision))

            raw_score = revision
            expected_return = revision * RETURN_SCALE * 2

            rows_out.append({
                'ticker':          ticker,
                'expected_return': round(expected_return, 4),
                'confidence':      max(0.01, ic),
                'raw_score':       round(raw_score, 4),
            })

        result = pd.DataFrame(rows_out)
        if not result.empty:
            # Cross-sectional rank transform
            result['raw_score'] = result['raw_score'].rank(pct=True)
            result['expected_return'] = (result['raw_score'] - 0.5) * 2 * RETURN_SCALE
            logger.info(f"[earnings_revision] {len(result)} signals for {date}")
        return result
```

### Step 4 — Wire into scheduler

In `engine/scheduler.py`:

1. Add to Sunday pipeline (light job):
```python
def step_fundamental_ingestion():
    from engine.data.fundamental_ingestion import run_fundamental_ingestion
    from portfolio.src.config import TRADEABLE_UNIVERSE
    run_fundamental_ingestion(TRADEABLE_UNIVERSE)
```

2. Add `EarningsRevisionAlpha` to the alpha model list in `step_alpha_signals()`:
```python
from engine.alpha.earnings_revision import EarningsRevisionAlpha
models = [
    MomentumAlpha(),
    MeanReversionAlpha(),
    VolTimingAlpha(),
    PEADAlpha(),
    MLAlpha(),
    LSTMAlpha(),
    EarningsRevisionAlpha(),   # NEW
]
```

---

## Expected characteristics

- Coverage: ~70–90 tickers (US stocks and European ADRs with analyst coverage)
- IC expectation: 0.05–0.09 (documented anomaly, reliable)
- Horizon: 3–6 months (slower signal than momentum)
- Correlation with momentum: ~0.25 (partially overlapping — both chase quality)
- Correlation with PEAD: ~0.15 (complementary — different timing)
- Most useful in: early recovery regimes when value + quality begins to work
- Least useful in: momentum-driven bull markets where fundamentals don't matter
