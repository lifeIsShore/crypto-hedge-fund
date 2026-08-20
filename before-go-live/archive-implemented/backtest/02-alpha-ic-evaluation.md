> **STATUS: IMPLEMENTED ✅** — 2026-08-20 (session 11). `backtests/alpha_eval.py` built and import-verified.
> Can be built in parallel with `01-engine.md` — no dependency on the walk-forward loop.
> Only needs: prices table populated with 2+ years of data.

# Alpha IC Evaluation
# `backtests/alpha_eval.py` (new)
# Estimated time: 0.5–1 day

---

## What this answers

For each alpha model, how predictive was its signal of the actual next-period return?
This is the **Information Coefficient (IC)** — Spearman rank correlation between:
- Signal at time `t` (the expected return / raw score)
- Actual return over the next `N` days, measured at time `t+N`

IC is the right unit for evaluating alpha models. Portfolio P&L is not — it
conflates signal quality with portfolio construction decisions (weights, constraints,
BL mixing). IC isolates the signal itself.

**Targets to compute:**
- `IC_21d` — 21-day forward return (the primary horizon used in the live system)
- `IC_63d` — 63-day forward return (secondary)
- `IC_5d`  — 5-day forward return (does it predict short-term at all?)

**Models to evaluate:**
1. `momentum` — signal: `mom_12m` rank from `feature_store`
2. `sector_momentum` — signal: `sector_mom_12m` rank
3. `mean_reversion` — signal: `(50 - rsi_14) / 50`
4. `vol_timing` — signal: inverse `vol_21d` rank
5. `ml_alpha` — signal: `up_proba_21d` from ML state (read from `signals` table)

---

## Implementation

### `backtests/alpha_eval.py`

```python
"""
backtests/alpha_eval.py
========================
Expanding-window IC evaluation for all alpha models.

Method: for each model and each date t in the evaluation window,
compute the signal → actual forward return Spearman correlation.
Reports per-model IC mean, IC std, ICIR = mean/std, hit rate.

Usage:
    python backtests/alpha_eval.py
    python backtests/alpha_eval.py --horizon 21  (default)
    python backtests/alpha_eval.py --model momentum
"""
import sys, os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import logging
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from datetime import timedelta

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('alpha_eval')

from portfolio.src.config import ASSET_UNIVERSE, TICKER_SECTORS


def load_prices_and_signals() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load prices (for computing realized returns) and pre-computed signals
    from the feature_store + signals tables in engine_data.db.

    Signals table already exists and is populated daily by the scheduler.
    Feature_store already exists and is populated daily.
    This is a pure read — no DB writes.
    """
    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        # Prices
        price_rows = session.execute(text("""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE adj_close IS NOT NULL
            ORDER BY date ASC
        """)).fetchall()

        # Alpha signals (written by each model's persist_signals())
        signal_rows = session.execute(text("""
            SELECT date, ticker, model_name, expected_return, confidence
            FROM signals
            ORDER BY date ASC
        """)).fetchall()

        # ML signals (up_proba_21d from price_targets, which MLAlpha writes)
        ml_rows = session.execute(text("""
            SELECT date, ticker, up_proba
            FROM price_targets
            WHERE up_proba IS NOT NULL
            ORDER BY date ASC
        """)).fetchall()

    finally:
        session.close()

    prices = pd.DataFrame(price_rows, columns=['date', 'ticker', 'adj_close'])
    prices['date'] = pd.to_datetime(prices['date'])
    prices = prices.pivot(index='date', columns='ticker', values='adj_close').sort_index()

    signals = pd.DataFrame(signal_rows, columns=['date', 'ticker', 'model_name', 'expected_return', 'confidence'])
    signals['date'] = pd.to_datetime(signals['date'])

    ml = pd.DataFrame(ml_rows, columns=['date', 'ticker', 'up_proba'])
    ml['date'] = pd.to_datetime(ml['date'])
    ml['model_name'] = 'ml_alpha'
    ml['expected_return'] = ml['up_proba'] - 0.5   # centre around 0
    ml['confidence'] = 0.05
    ml = ml[['date', 'ticker', 'model_name', 'expected_return', 'confidence']]

    all_signals = pd.concat([signals, ml], ignore_index=True)

    logger.info(f"Loaded {len(prices)} price dates, {all_signals['model_name'].nunique()} models, "
                f"{all_signals['date'].nunique()} signal dates")
    return prices, all_signals


def compute_forward_returns(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """
    For each (date, ticker), compute the log return from date to date+horizon.
    Returns DataFrame: index=date, columns=tickers, values=log_return.
    """
    # Shift by horizon to get future price — then compute return at current date.
    future_prices = prices.shift(-horizon)
    log_ret = np.log(future_prices / prices)
    logger.info(f"Forward returns computed: horizon={horizon}d, "
                f"{log_ret.notna().sum().sum()} valid observations")
    return log_ret


def compute_ic_timeseries(
    signals: pd.DataFrame,
    forward_returns: pd.DataFrame,
    model_name: str,
    min_tickers: int = 10,
) -> pd.Series:
    """
    For each date where signals exist for `model_name`, compute the
    cross-sectional Spearman IC between signal and forward return.

    Returns pd.Series: index=date, values=IC (NaN if < min_tickers).
    """
    model_signals = signals[signals['model_name'] == model_name].copy()
    dates = sorted(model_signals['date'].unique())
    ic_series = {}

    for dt in dates:
        day_signals = model_signals[model_signals['date'] == dt].set_index('ticker')

        # Get realized forward returns for the same tickers on this date
        if dt not in forward_returns.index:
            continue
        fwd = forward_returns.loc[dt]

        # Align
        common = day_signals.index.intersection(fwd.dropna().index)
        if len(common) < min_tickers:
            continue

        s = day_signals.loc[common, 'expected_return'].values
        r = fwd.loc[common].values

        ic, pval = spearmanr(s, r)
        ic_series[dt] = ic

    return pd.Series(ic_series, name=f'IC_{model_name}')


def evaluate_model(
    model_name: str,
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    horizons: list = [5, 21, 63],
) -> dict:
    """
    Compute IC stats for one model across multiple horizons.
    Returns dict of {horizon: {mean_ic, std_ic, icir, hit_rate, n_obs}}.
    """
    results = {}
    for h in horizons:
        fwd = compute_forward_returns(prices, h)
        ic_ts = compute_ic_timeseries(signals, fwd, model_name)

        if ic_ts.empty:
            results[h] = {'mean_ic': None, 'std_ic': None, 'icir': None,
                          'hit_rate': None, 'n_obs': 0}
            continue

        mean_ic = ic_ts.mean()
        std_ic  = ic_ts.std()
        icir    = mean_ic / std_ic if std_ic > 1e-8 else 0.0
        hit_rate = (ic_ts > 0).mean()

        results[h] = {
            'mean_ic':  round(float(mean_ic),  4),
            'std_ic':   round(float(std_ic),   4),
            'icir':     round(float(icir),     3),
            'hit_rate': round(float(hit_rate), 3),
            'n_obs':    len(ic_ts),
        }
        logger.info(f"[{model_name}] horizon={h}d | IC={mean_ic:.4f} ± {std_ic:.4f} "
                    f"| ICIR={icir:.3f} | hit={hit_rate:.1%} | n={len(ic_ts)}")

    return results


def run_alpha_evaluation(horizon: int = 21, model_filter: str = None):
    """Entry point."""
    prices, signals = load_prices_and_signals()

    models = signals['model_name'].unique().tolist()
    if model_filter:
        models = [m for m in models if m == model_filter]

    all_results = {}
    for model in models:
        logger.info(f"\n{'='*50}\nEvaluating: {model}\n{'='*50}")
        all_results[model] = evaluate_model(
            model_name=model,
            signals=signals,
            prices=prices,
            horizons=[5, 21, 63],
        )

    # Print summary table
    print("\n" + "="*70)
    print(f"{'MODEL':<20} {'H':>4} {'MEAN_IC':>8} {'STD_IC':>8} {'ICIR':>7} {'HIT':>7} {'N':>5}")
    print("-"*70)
    for model, hresults in all_results.items():
        for h, stats in sorted(hresults.items()):
            if stats['n_obs'] == 0:
                print(f"{model:<20} {h:>4} {'NO DATA':>40}")
                continue
            print(
                f"{model:<20} {h:>4} "
                f"{stats['mean_ic']:>8.4f} {stats['std_ic']:>8.4f} "
                f"{stats['icir']:>7.3f} {stats['hit_rate']:>7.1%} {stats['n_obs']:>5}"
            )
    print("="*70)

    # Save
    rows = []
    for model, hresults in all_results.items():
        for h, stats in hresults.items():
            rows.append({'model': model, 'horizon': h, **stats})
    out_df = pd.DataFrame(rows)
    out = os.path.join(os.path.dirname(__file__), 'alpha_ic_results.csv')
    out_df.to_csv(out, index=False)
    logger.info(f"IC results saved to {out}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--horizon', type=int, default=21)
    parser.add_argument('--model', default=None)
    args = parser.parse_args()
    run_alpha_evaluation(horizon=args.horizon, model_filter=args.model)
```

---

## How to read the results

| Metric | What it means | Threshold |
|---|---|---|
| `MEAN_IC` | Average cross-sectional rank correlation. 0 = random | > 0.03 is useful; > 0.06 is good |
| `STD_IC` | Stability of IC over time. High std = model is hot/cold | Lower is better |
| `ICIR` | = MEAN_IC / STD_IC. Risk-adjusted signal quality | > 0.5 is acceptable; > 1.0 is good |
| `HIT_RATE` | % of months where IC > 0 | > 55% means it's consistently positive |
| `N_OBS` | Number of dates with enough tickers to compute IC | Need > 50 for reliable stats |

**Interpretation guide:**
- `momentum` at 21d: expected IC ~0.03–0.06 (well-documented in literature)
- `mean_reversion` at 5d: typically higher IC but degrades fast at 21d+
- `ml_alpha`: IC at 21d should be the highest if the model is genuinely predictive
- A model with IC < 0.02 and ICIR < 0.3 is noise — should be weighted out by BL anyway
  (because its omega is high due to low IC)

---

## Output files

- `backtests/alpha_ic_results.csv` — IC table for all models × horizons
- Console table — printed at runtime
