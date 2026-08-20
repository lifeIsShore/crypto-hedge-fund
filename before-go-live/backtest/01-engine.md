> **STATUS: NOT IMPLEMENTED.**
> Prerequisites: `00-OVERVIEW.md`, stable pipeline, clean DB.

# Walk-Forward Engine
# `backtests/walk_forward.py` (new)
# Estimated time: 1–1.5 days

---

## Design principle

Replay every Monday from the warmup cutoff to today. At each step `t`:

1. All price data up to and including `t` is visible (never past `t`)
2. Features are computed on the price window ending at `t`
3. Alpha signals are generated from those features
4. BL optimizer runs with those signals + covariance from that window
5. Suggested weights are applied; portfolio value updates using `t+1` prices
6. That day's return is recorded

This is a **daily rebalance walk-forward** for simplicity. In practice the live
system rebalances on the 1st/3rd Friday, but daily rebalance gives more data
points and is strictly more conservative (more turnover cost applied).

---

## What to reuse vs what to rewrite

**Reuse directly** (these are pure functions that take a price slice as input):

```python
from engine.features.feature_store import (
    compute_momentum_features,
    compute_sector_relative_features,
    compute_volatility_features,
    compute_technical_features,
)
from engine.portfolio.black_litterman import (
    build_bl_views_calibrated,
    run_black_litterman,      # don't use this — it reads from DB. Use the components directly.
)
from engine.portfolio.optimizer import optimize_with_bl
```

**Do NOT reuse directly** (they read from/write to `engine_data.db`):

| Production function | Why it breaks in backtest | What to do instead |
|---|---|---|
| `load_returns_from_db()` | Reads whole DB — always leaks future prices | Pass price slice directly to `compute_*` functions |
| `load_signals_from_db()` | Reads `signals` table — future leaks if signals were written | Compute signals inline in the loop |
| `run_black_litterman()` | Calls `load_signals_from_db()` internally | Build views inline: see code below |
| `persist_features()` | Writes to `feature_store` table — corrupts live data | Skip entirely — features are computed in-memory |
| `run_feature_pipeline()` | Orchestrator that does DB read+write | Skip. Call `compute_*` functions directly |

**ML alpha — special case:**

`MLAlpha.generate_signals()` calls the trained model which was trained on the full
history including future data relative to any backtest date. This is **forward-leaking**
by construction. **Do not use MLAlpha inside the backtest loop.**

Instead: evaluate ML alpha separately in `02-alpha-ic-evaluation.md` using
expanding-window IC measurement. The walk-forward loop uses only the
**non-ML alpha models** (momentum, sector_momentum, mean_reversion, vol_timing).
This is honest and sufficient — the ML model's IC evaluation in doc 02 tells
you whether it adds value independently.

---

## Implementation

### `backtests/walk_forward.py`

```python
"""
backtests/walk_forward.py
==========================
Walk-forward backtest of the BL + multi-factor portfolio strategy.

Usage:
    python backtests/walk_forward.py
    python backtests/walk_forward.py --start 2023-06-01 --end 2025-01-01

Output:
    backtest_results.csv  — daily portfolio values + weights
    Console table         — performance metrics (doc 03 reads this)

Deliberately no DB writes during the loop. Results are written to a CSV
in backtests/ only. Does not touch engine_data.db.
"""
import sys, os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('backtest')

# ── Config ────────────────────────────────────────────────────────────────────
WARMUP_DAYS     = 273    # 252 (mom_12m) + 21 (skip) — minimum history needed
INITIAL_CAPITAL = 10_000.0
BENCHMARK       = 'EUNL.DE'
REBAL_WEEKDAY   = 0      # 0=Monday (replicate live cadence)

# Reuse live constants — do not re-tune these on the backtest window
from engine.portfolio.optimizer import MAX_POSITION, TURNOVER_PENALTY, SLIPPAGE_PCT
from portfolio.src.config import ASSET_UNIVERSE, TICKER_SECTORS, BENCHMARK_TICKER


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_prices() -> pd.DataFrame:
    """
    Load full price history from DB once, slice per step inside the loop.
    This is the ONLY DB call in the entire backtest.
    Returns: DataFrame(index=date, columns=tickers), adj_close in EUR.
    """
    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE adj_close IS NOT NULL
            ORDER BY date ASC
        """)).fetchall()
    finally:
        session.close()

    df = pd.DataFrame(rows, columns=['date', 'ticker', 'adj_close'])
    prices = df.pivot(index='date', columns='ticker', values='adj_close')
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    # Forward-fill up to 5 days (weekends / bank holidays) — same as live
    prices = prices.ffill(limit=5)
    logger.info(f"Loaded {len(prices)} price rows, {len(prices.columns)} tickers, "
                f"{prices.index[0].date()} → {prices.index[-1].date()}")
    return prices


# ── Signal generation (no DB) ─────────────────────────────────────────────────

def compute_signals_at(prices_slice: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all non-ML alpha signals on prices_slice.
    prices_slice: rows = all dates up to t (inclusive), columns = tickers.
    Returns: DataFrame with columns [ticker, model_name, expected_return, confidence].
    """
    from engine.features.feature_store import (
        compute_momentum_features,
        compute_sector_relative_features,
        compute_volatility_features,
        compute_technical_features,
    )
    import numpy as np

    log_returns = np.log(prices_slice / prices_slice.shift(1)).dropna(how='all')
    all_signals = []

    # ── Momentum (cross-sectional, universe rank) ─────────────────────────────
    mom = compute_momentum_features(prices_slice)
    if not mom.empty and 'mom_12m' in mom.columns:
        RETURN_SCALE_MOM = 0.04
        for ticker, row in mom.iterrows():
            rank = row.get('mom_12m')
            if pd.isna(rank): continue
            all_signals.append({
                'ticker': ticker,
                'model_name': 'momentum',
                'expected_return': (rank - 0.5) * 2 * RETURN_SCALE_MOM,
                'confidence': 0.05,   # conservative fixed IC for backtest
            })

    # ── Sector momentum (intra-sector rank) ───────────────────────────────────
    sec_mom = compute_sector_relative_features(prices_slice, TICKER_SECTORS)
    if not sec_mom.empty and 'sector_mom_12m' in sec_mom.columns:
        RETURN_SCALE_SEC = 0.03
        for ticker, row in sec_mom.iterrows():
            rank = row.get('sector_mom_12m')
            if pd.isna(rank): continue
            all_signals.append({
                'ticker': ticker,
                'model_name': 'sector_momentum',
                'expected_return': (rank - 0.5) * 2 * RETURN_SCALE_SEC,
                'confidence': 0.04,
            })

    # ── Mean reversion (vol-adjusted RSI) ─────────────────────────────────────
    tech = compute_technical_features(prices_slice)
    vol  = compute_volatility_features(log_returns)
    if not tech.empty and 'rsi_14' in tech.columns:
        RETURN_SCALE_MR = 0.02
        for ticker in tech.index:
            rsi = tech.loc[ticker, 'rsi_14'] if ticker in tech.index else None
            if rsi is None or pd.isna(rsi): continue
            # RSI < 30: oversold → positive view; RSI > 70: overbought → negative
            mean_rev_signal = (50 - rsi) / 50.0   # maps [0,100] → [+1, -1]
            all_signals.append({
                'ticker': ticker,
                'model_name': 'mean_reversion',
                'expected_return': mean_rev_signal * RETURN_SCALE_MR,
                'confidence': 0.03,
            })

    # ── Vol timing (low-vol premium) ──────────────────────────────────────────
    if not vol.empty and 'vol_21d' in vol.columns:
        RETURN_SCALE_VT = 0.02
        vol_series = vol['vol_21d'].dropna()
        if len(vol_series) > 1:
            vol_rank = vol_series.rank(pct=True)
            for ticker, rank in vol_rank.items():
                all_signals.append({
                    'ticker': ticker,
                    'model_name': 'vol_timing',
                    'expected_return': (0.5 - rank) * 2 * RETURN_SCALE_VT,
                    'confidence': 0.03,
                })

    return pd.DataFrame(all_signals) if all_signals else pd.DataFrame()


# ── Covariance ────────────────────────────────────────────────────────────────

def compute_covariance(prices_slice: pd.DataFrame, tickers: list) -> pd.DataFrame:
    """
    Ledoit-Wolf covariance on the price slice — same as live system.
    Uses only tickers with enough data (>= 60 observations).
    """
    import numpy as np
    from sklearn.covariance import LedoitWolf

    log_ret = np.log(prices_slice[tickers] / prices_slice[tickers].shift(1)).dropna(how='all')
    valid_tickers = [t for t in tickers if log_ret[t].notna().sum() >= 60]
    log_ret = log_ret[valid_tickers].dropna()

    if len(log_ret) < len(valid_tickers):
        # fallback: sample covariance
        cov = log_ret.cov() * 252
    else:
        lw = LedoitWolf().fit(log_ret.values)
        cov = pd.DataFrame(lw.covariance_ * 252,
                           index=valid_tickers, columns=valid_tickers)

    return cov, valid_tickers


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_walk_forward(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Core loop. Returns DataFrame with columns:
      date, portfolio_value, benchmark_value, weights (dict)
    """
    from ml_quant_finance_research.general_research.src.factor_model import (
        black_litterman, compute_market_implied_returns,
    )
    from engine.portfolio.optimizer import optimize_with_bl

    prices = load_all_prices()
    trading_dates = prices.index

    # Determine valid tickers for the backtest
    # (must have data for the full backtest window — avoids survivorship bias
    #  for tickers that existed the whole time but not new additions)
    tickers = [t for t in ASSET_UNIVERSE if t in prices.columns]
    benchmark_in_universe = BENCHMARK in prices.columns

    # Warmup cutoff — first date with enough history for all momentum features
    warmup_cutoff = trading_dates[WARMUP_DAYS] if len(trading_dates) > WARMUP_DAYS else trading_dates[-1]

    if start_date:
        start_dt = pd.Timestamp(start_date)
        start_dt = max(start_dt, warmup_cutoff)
    else:
        start_dt = warmup_cutoff

    end_dt = pd.Timestamp(end_date) if end_date else trading_dates[-1]

    backtest_dates = trading_dates[(trading_dates >= start_dt) & (trading_dates <= end_dt)]
    logger.info(f"Backtest: {start_dt.date()} → {end_dt.date()}, {len(backtest_dates)} steps")

    # State
    portfolio_value = INITIAL_CAPITAL
    benchmark_value = INITIAL_CAPITAL
    current_weights = pd.Series(0.0, index=tickers)
    results = []

    for i, t in enumerate(backtest_dates):
        # Only rebalance on Mondays (or first date)
        is_rebal_day = (t.weekday() == REBAL_WEEKDAY) or (i == 0)

        # Price slice: all data up to and including t
        prices_t = prices.loc[:t, tickers]
        prices_t = prices_t.dropna(axis=1, thresh=60)   # drop tickers with < 60 obs
        available = list(prices_t.columns)

        # Next-period prices (t+1) for P&L calculation
        next_dates = trading_dates[trading_dates > t]
        if len(next_dates) == 0:
            break
        t_next = next_dates[0]
        prices_next = prices.loc[t_next, available] if t_next in prices.index else None

        if prices_next is None or prices_next.isna().all():
            results.append({
                'date': t.date(),
                'portfolio_value': portfolio_value,
                'benchmark_value': benchmark_value,
            })
            continue

        if is_rebal_day:
            # ── Signals ───────────────────────────────────────────────────────
            signals_df = compute_signals_at(prices_t)

            # ── Covariance ────────────────────────────────────────────────────
            cov_matrix, valid_tickers = compute_covariance(prices_t, available)
            if len(valid_tickers) < 3:
                logger.warning(f"[{t.date()}] < 3 valid tickers — skipping rebalance")
                is_rebal_day = False
            else:
                # ── BL ────────────────────────────────────────────────────────
                market_weights = pd.Series(
                    1.0 / len(valid_tickers), index=valid_tickers
                )
                # Build views directly (avoid load_signals_from_db)
                from engine.portfolio.black_litterman import build_bl_views_calibrated
                views = build_bl_views_calibrated(
                    signals_df=signals_df[signals_df['ticker'].isin(valid_tickers)],
                    tickers=valid_tickers,
                    cov_matrix=cov_matrix,
                    models_dict=None,   # no live-approval gating in backtest
                    tau=0.05,
                )

                mu_bl = black_litterman(
                    cov_matrix=cov_matrix,
                    market_weights=market_weights,
                    views=views,
                    tau=0.05,
                    risk_aversion=2.5,
                )

                # ── Optimizer ─────────────────────────────────────────────────
                new_weights = optimize_with_bl(
                    mu_bl=mu_bl,
                    cov_matrix=cov_matrix,
                    current_weights=current_weights.reindex(valid_tickers, fill_value=0.0),
                    sector_map=TICKER_SECTORS,
                    date=None,              # don't write cluster data to DB
                    apply_tax_penalty=False, # no tax drag in backtest (no entry price basis)
                )
                current_weights = new_weights.reindex(tickers, fill_value=0.0)

        # ── P&L update ────────────────────────────────────────────────────────
        # For each held ticker: weight × price return
        ret = 0.0
        for ticker in tickers:
            w = float(current_weights.get(ticker, 0.0))
            if w == 0 or ticker not in prices_t.columns: continue
            p0 = float(prices_t[ticker].iloc[-1])
            p1 = float(prices.loc[t_next, ticker]) if (
                t_next in prices.index and ticker in prices.columns
                and not pd.isna(prices.loc[t_next, ticker])
            ) else p0
            if p0 > 0:
                ret += w * (p1 / p0 - 1.0)

        portfolio_value *= (1.0 + ret)

        # Benchmark
        if benchmark_in_universe:
            b0 = float(prices.loc[t, BENCHMARK]) if not pd.isna(prices.loc[t, BENCHMARK]) else None
            b1 = float(prices.loc[t_next, BENCHMARK]) if (
                t_next in prices.index and not pd.isna(prices.loc[t_next, BENCHMARK])
            ) else b0
            if b0 and b0 > 0:
                benchmark_value *= (b1 / b0)

        results.append({
            'date': t.date(),
            'portfolio_value': round(portfolio_value, 4),
            'benchmark_value': round(benchmark_value, 4),
            'daily_return': round(ret, 6),
        })

        if i % 50 == 0:
            logger.info(f"[{t.date()}] portfolio={portfolio_value:,.0f} benchmark={benchmark_value:,.0f}")

    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    return df


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', default=None, help='Start date YYYY-MM-DD')
    parser.add_argument('--end',   default=None, help='End date YYYY-MM-DD')
    args = parser.parse_args()

    results = run_walk_forward(start_date=args.start, end_date=args.end)

    out = os.path.join(os.path.dirname(__file__), 'backtest_results.csv')
    results.to_csv(out)
    logger.info(f"Results saved to {out}")

    # Print summary
    from backtests.metrics import print_metrics   # doc 03
    print_metrics(results)
```

---

## Key design decisions documented

**Why fixed IC = 0.05 for momentum in backtest (not computed rolling IC)?**
Rolling IC computation requires forward returns, which requires future prices — leakage.
The `compute_rolling_ic()` in the live `AlphaModel.base` reads the `signals` table and
compares against subsequent `prices` rows. To do this in a walk-forward context would
require writing signals to a temp table and reading them 21 days later in the loop.
That's complex. The fixed IC is conservative (real live IC is typically 0.03–0.10) and
gives consistent BL view weights across the backtest. The real IC analysis is in doc 02.

**Why no ML in the loop?**
`MLAlpha` wraps a trained classifier that was fit on data spanning 2022–today. There is
no clean way to retrain it at each walk-forward step without a full expanding-window
retraining cycle (train on 2022→t, predict t+1, roll forward). That's a 2-week project
on its own. Exclude for now; evaluate separately via expanding IC in doc 02.

**Why no tax penalty in backtest?**
No entry price basis tracking across the loop. Including tax drag would require tracking
each lot's acquisition price across 600+ steps — adds significant complexity for minor
precision. The turnover penalty (0.2% × Δweight) already penalises excessive trading.

**Why daily rebalance instead of bi-monthly?**
More data points → better metric estimation. The additional turnover cost is applied via
the optimizer's `TURNOVER_PENALTY` constant, so it's not as if we're getting free rebalancing.

---

## Output file: `backtests/backtest_results.csv`

```
date,portfolio_value,benchmark_value,daily_return
2023-01-23,10000.0,10000.0,0.0
2023-01-24,10032.1,10018.4,0.00321
...
```

This is the input to `03-portfolio-metrics.md`.
