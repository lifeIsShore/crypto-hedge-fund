"""
backtests/walk_forward.py
==========================
Walk-forward backtest of the BL + multi-factor portfolio strategy.

Usage:
    python backtests/walk_forward.py
    python backtests/walk_forward.py --start 2023-06-01 --end 2025-01-01
    python backtests/walk_forward.py --note "disabled ml_alpha"
    python backtests/walk_forward.py --run-id 20260820_120000  (override run ID)

Output (each run is immutable — nothing is ever overwritten):
    backtests/runs/<run_id>/backtest_results.csv
    backtests/runs/<run_id>/backtest_metrics.csv
    backtests/runs/<run_id>/alpha_ic_results.csv  (if alpha_eval is run)
    backtests/runs/<run_id>/strategy_config.json
    backtests/runs/<run_id>/run_meta.json
    backtests/runs/runs_index.csv                  (one row appended per run)

    backtests/backtest_results.csv  — copy of latest run (backward compat)
    Console table                   — performance metrics (via metrics.py)

Deliberately no DB writes during the loop. Results are written to CSVs
in backtests/ only. Does not touch engine_data.db.
"""
import sys
import os
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
from backtests.registry import (
    generate_run_id, get_run_dir, append_index, BACKTESTS_DIR
)


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

    log_returns = np.log(prices_slice / prices_slice.shift(1)).dropna(how='all')
    all_signals = []

    # ── Momentum (cross-sectional, universe rank) ─────────────────────────────
    try:
        mom = compute_momentum_features(prices_slice)
        if not mom.empty and 'mom_12m' in mom.columns:
            RETURN_SCALE_MOM = 0.04
            for ticker, row in mom.iterrows():
                rank = row.get('mom_12m')
                if pd.isna(rank):
                    continue
                all_signals.append({
                    'ticker': ticker,
                    'model_name': 'momentum',
                    'expected_return': (rank - 0.5) * 2 * RETURN_SCALE_MOM,
                    'confidence': 0.05,   # conservative fixed IC for backtest
                })
    except Exception as e:
        logger.debug(f"momentum signal failed: {e}")

    # ── Sector momentum (intra-sector rank) ───────────────────────────────────
    try:
        sec_mom = compute_sector_relative_features(prices_slice, TICKER_SECTORS)
        if not sec_mom.empty and 'sector_mom_12m' in sec_mom.columns:
            RETURN_SCALE_SEC = 0.03
            for ticker, row in sec_mom.iterrows():
                rank = row.get('sector_mom_12m')
                if pd.isna(rank):
                    continue
                all_signals.append({
                    'ticker': ticker,
                    'model_name': 'sector_momentum',
                    'expected_return': (rank - 0.5) * 2 * RETURN_SCALE_SEC,
                    'confidence': 0.04,
                })
    except Exception as e:
        logger.debug(f"sector_momentum signal failed: {e}")

    # ── Mean reversion (vol-adjusted RSI) ─────────────────────────────────────
    try:
        tech = compute_technical_features(prices_slice)
        vol  = compute_volatility_features(log_returns)
        if not tech.empty and 'rsi_14' in tech.columns:
            RETURN_SCALE_MR = 0.02
            for ticker in tech.index:
                rsi = tech.loc[ticker, 'rsi_14'] if ticker in tech.index else None
                if rsi is None or pd.isna(rsi):
                    continue
                # RSI < 30: oversold → positive view; RSI > 70: overbought → negative
                mean_rev_signal = (50 - rsi) / 50.0   # maps [0,100] → [+1, -1]
                all_signals.append({
                    'ticker': ticker,
                    'model_name': 'mean_reversion',
                    'expected_return': mean_rev_signal * RETURN_SCALE_MR,
                    'confidence': 0.03,
                })
    except Exception as e:
        logger.debug(f"mean_reversion signal failed: {e}")

    # ── Vol timing (low-vol premium) ──────────────────────────────────────────
    try:
        vol = compute_volatility_features(log_returns)
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
    except Exception as e:
        logger.debug(f"vol_timing signal failed: {e}")

    return pd.DataFrame(all_signals) if all_signals else pd.DataFrame()


# ── Covariance ────────────────────────────────────────────────────────────────

def compute_covariance(prices_slice: pd.DataFrame, tickers: list):
    """
    Ledoit-Wolf covariance on the price slice — same as live system.
    Uses only tickers with enough data (>= 60 observations).
    Returns (cov_matrix DataFrame, valid_tickers list).
    """
    from sklearn.covariance import LedoitWolf

    # Only keep tickers that are in prices_slice
    tickers = [t for t in tickers if t in prices_slice.columns]
    log_ret = np.log(prices_slice[tickers] / prices_slice[tickers].shift(1)).dropna(how='all')
    valid_tickers = [t for t in tickers if log_ret[t].notna().sum() >= 60]

    if len(valid_tickers) < 3:
        return pd.DataFrame(), []

    log_ret = log_ret[valid_tickers].dropna()

    try:
        lw = LedoitWolf().fit(log_ret.values)
        cov = pd.DataFrame(lw.covariance_ * 252,
                           index=valid_tickers, columns=valid_tickers)
    except Exception:
        # fallback: sample covariance
        cov = log_ret.cov() * 252

    return cov, valid_tickers


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_walk_forward(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Core loop. Returns DataFrame with columns:
      date, portfolio_value, benchmark_value, daily_return
    """
    from ml_quant_finance_research.general_research.src.factor_model import (
        black_litterman, compute_market_implied_returns,
    )
    from engine.portfolio.black_litterman import build_bl_views_calibrated
    from engine.portfolio.optimizer import optimize_with_bl

    prices = load_all_prices()
    trading_dates = prices.index

    # Determine valid tickers for the backtest
    tickers = [t for t in ASSET_UNIVERSE if t in prices.columns]
    benchmark_in_universe = BENCHMARK in prices.columns

    # Warmup cutoff — first date with enough history for all momentum features
    if len(trading_dates) > WARMUP_DAYS:
        warmup_cutoff = trading_dates[WARMUP_DAYS]
    else:
        warmup_cutoff = trading_dates[-1]

    if start_date:
        start_dt = pd.Timestamp(start_date)
        start_dt = max(start_dt, warmup_cutoff)
    else:
        start_dt = warmup_cutoff

    end_dt = pd.Timestamp(end_date) if end_date else trading_dates[-1]

    backtest_dates = trading_dates[
        (trading_dates >= start_dt) & (trading_dates <= end_dt)
    ]
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
                'daily_return': 0.0,
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

                try:
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

                    # ── Optimizer ─────────────────────────────────────────────
                    new_weights = optimize_with_bl(
                        mu_bl=mu_bl,
                        cov_matrix=cov_matrix,
                        current_weights=current_weights.reindex(valid_tickers, fill_value=0.0),
                        sector_map=TICKER_SECTORS,
                        date=None,              # don't write cluster data to DB
                        apply_tax_penalty=False, # no tax drag in backtest
                    )
                    current_weights = new_weights.reindex(tickers, fill_value=0.0)

                except Exception as e:
                    logger.warning(f"[{t.date()}] BL/optimizer error: {e} — keeping prior weights")

        # ── P&L update ────────────────────────────────────────────────────────
        # For each held ticker: weight × price return
        ret = 0.0
        for ticker in tickers:
            w = float(current_weights.get(ticker, 0.0))
            if w == 0 or ticker not in prices_t.columns:
                continue
            p0 = float(prices_t[ticker].iloc[-1])
            p1 = (float(prices.loc[t_next, ticker])
                  if t_next in prices.index
                  and ticker in prices.columns
                  and not pd.isna(prices.loc[t_next, ticker])
                  else p0)
            if p0 > 0:
                ret += w * (p1 / p0 - 1.0)

        portfolio_value *= (1.0 + ret)

        # Benchmark
        if benchmark_in_universe:
            b0 = (float(prices.loc[t, BENCHMARK])
                  if BENCHMARK in prices.columns and not pd.isna(prices.loc[t, BENCHMARK])
                  else None)
            b1 = (float(prices.loc[t_next, BENCHMARK])
                  if t_next in prices.index
                  and BENCHMARK in prices.columns
                  and not pd.isna(prices.loc[t_next, BENCHMARK])
                  else b0)
            if b0 and b0 > 0:
                benchmark_value *= (b1 / b0)

        results.append({
            'date': t.date(),
            'portfolio_value': round(portfolio_value, 4),
            'benchmark_value': round(benchmark_value, 4),
            'daily_return': round(ret, 6),
        })

        if i % 50 == 0:
            logger.info(f"[{t.date()}] portfolio={portfolio_value:,.0f} "
                        f"benchmark={benchmark_value:,.0f}")

    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    return df


# ── Git commit helper ─────────────────────────────────────────────────────────

def _get_git_commit() -> str:
    """Return short git commit hash, or '' if not in a git repo."""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(__file__)
        )
        return result.stdout.strip() if result.returncode == 0 else ''
    except Exception:
        return ''


def _build_strategy_config(
    run_id: str,
    start_date: str,
    end_date: str,
    git_commit: str,
) -> dict:
    """Snapshot of every parameter used in this backtest run."""
    from datetime import timezone
    return {
        'run_id':           run_id,
        'run_timestamp':    datetime.now(timezone.utc).isoformat(),
        'backtest_start':   start_date or 'auto',
        'backtest_end':     end_date   or 'auto',
        'git_commit':       git_commit,
        'initial_capital':  INITIAL_CAPITAL,
        'benchmark':        BENCHMARK,
        'warmup_days':      WARMUP_DAYS,
        'rebal_weekday':    REBAL_WEEKDAY,
        'alphas_active': [
            {'name': 'momentum',        'confidence': 0.05, 'return_scale': 0.04},
            {'name': 'sector_momentum', 'confidence': 0.04, 'return_scale': 0.03},
            {'name': 'mean_reversion',  'confidence': 0.03, 'return_scale': 0.02},
            {'name': 'vol_timing',      'confidence': 0.03, 'return_scale': 0.02},
        ],
        'optimizer_params': {
            'max_position':    MAX_POSITION,
            'turnover_penalty': TURNOVER_PENALTY,
            'slippage_pct':    SLIPPAGE_PCT,
            'tau':             0.05,
            'risk_aversion':   2.5,
        },
        'risk_free_rate': 0.04,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Walk-forward backtest')
    parser.add_argument('--start',  default=None, help='Start date YYYY-MM-DD')
    parser.add_argument('--end',    default=None, help='End date YYYY-MM-DD')
    parser.add_argument('--note',   default='',   help='Free-text note for this run')
    parser.add_argument('--run-id', default=None, dest='run_id',
                        help='Override run ID (default: YYYYMMDD_HHMMSS)')
    args = parser.parse_args()

    # ── Generate run ID & directories ─────────────────────────────────────────
    run_id     = args.run_id or generate_run_id()
    run_dir    = get_run_dir(run_id)
    git_commit = _get_git_commit()

    logger.info(f"Run ID: {run_id}  |  Output dir: {run_dir}")

    # ── Write strategy_config.json immediately (before any computation) ────────
    config = _build_strategy_config(
        run_id=run_id,
        start_date=args.start,
        end_date=args.end,
        git_commit=git_commit,
    )
    config_path = run_dir / 'strategy_config.json'
    config_path.write_text(
        __import__('json').dumps(config, indent=2), encoding='utf-8'
    )
    logger.info(f"strategy_config.json written to {run_dir}")

    # ── Run the backtest ──────────────────────────────────────────────────────
    import time as _time
    t0 = _time.perf_counter()

    results = run_walk_forward(start_date=args.start, end_date=args.end)

    elapsed_sec = round(_time.perf_counter() - t0, 1)

    # ── Save results into run folder ──────────────────────────────────────────
    results_path = run_dir / 'backtest_results.csv'
    results.to_csv(results_path)
    logger.info(f"Results saved to {results_path} ({len(results)} rows)")

    # ── Compute & save metrics ─────────────────────────────────────────────────
    try:
        from backtests.metrics import print_metrics, compute_metrics
        import pandas as _pd
        print_metrics(results)
        m = compute_metrics(results)
        metrics_path = run_dir / 'backtest_metrics.csv'
        _pd.Series(m).to_csv(metrics_path, header=['value'])
        logger.info(f"Metrics saved to {metrics_path}")
    except Exception as e:
        logger.warning(f"metrics step failed: {e}")
        m = {}

    # ── Write run_meta.json ────────────────────────────────────────────────────
    from datetime import timezone as _tz
    meta = {
        'run_id':       run_id,
        'completed_at': datetime.now(_tz.utc).isoformat(),
        'elapsed_sec':  elapsed_sec,
        'n_result_rows': len(results),
        'git_commit':   git_commit,
        'note':         args.note,
    }
    meta_path = run_dir / 'run_meta.json'
    meta_path.write_text(
        __import__('json').dumps(meta, indent=2), encoding='utf-8'
    )

    # ── Append to runs_index.csv ───────────────────────────────────────────────
    append_index(run_id=run_id, metrics=m, config=config, note=args.note)

    # ── Backward-compat: copy to root-level flat files ─────────────────────────
    import shutil as _shutil
    for fname in ('backtest_results.csv', 'backtest_metrics.csv'):
        src = run_dir / fname
        dst = BACKTESTS_DIR / fname
        if src.exists():
            _shutil.copy2(src, dst)

    logger.info(
        f"\n{'='*60}\n"
        f"  Run {run_id} complete in {elapsed_sec}s\n"
        f"  Artifacts: {run_dir}\n"
        f"{'='*60}"
    )
