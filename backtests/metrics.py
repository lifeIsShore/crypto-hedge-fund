"""
backtests/metrics.py
=====================
Performance metrics for the walk-forward backtest.
Reads backtests/backtest_results.csv produced by walk_forward.py.
Can also be called as a library: from backtests.metrics import compute_metrics, print_metrics

Usage:
    python backtests/metrics.py
    python backtests/metrics.py --file path/to/backtest_results.csv
"""
import sys
import os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import numpy as np
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('metrics')

RISK_FREE_RATE = 0.04    # EUR 4% — conservative approximation for 2023–2025
TRADING_DAYS   = 252


def load_results(filepath: str) -> pd.DataFrame:
    """Load backtest_results.csv into a DataFrame."""
    df = pd.read_csv(filepath, index_col='date', parse_dates=True)
    df = df.sort_index()
    assert 'portfolio_value' in df.columns, "Missing portfolio_value column"
    assert 'benchmark_value' in df.columns, "Missing benchmark_value column"
    return df


def compute_metrics(df: pd.DataFrame) -> dict:
    """
    Computes all metrics from the equity DataFrame.
    df: index=date, columns=[portfolio_value, benchmark_value, daily_return]
    Returns: dict of metric_name → value
    """
    pv = df['portfolio_value'].dropna()
    bv = df['benchmark_value'].dropna()

    # Daily returns
    port_ret  = pv.pct_change().dropna()
    bench_ret = bv.pct_change().dropna()

    # Align
    common_idx = port_ret.index.intersection(bench_ret.index)
    port_ret   = port_ret.loc[common_idx]
    bench_ret  = bench_ret.loc[common_idx]
    excess_ret = port_ret - bench_ret

    n_days  = len(port_ret)
    n_years = n_days / TRADING_DAYS

    rf_daily = RISK_FREE_RATE / TRADING_DAYS

    # ── Return metrics ────────────────────────────────────────────────────────
    total_return_port  = pv.iloc[-1] / pv.iloc[0] - 1.0
    total_return_bench = bv.iloc[-1] / bv.iloc[0] - 1.0
    cagr_port  = (1 + total_return_port)  ** (1 / n_years) - 1 if n_years > 0 else 0.0
    cagr_bench = (1 + total_return_bench) ** (1 / n_years) - 1 if n_years > 0 else 0.0

    # ── Volatility ────────────────────────────────────────────────────────────
    vol_port  = port_ret.std()  * np.sqrt(TRADING_DAYS)
    vol_bench = bench_ret.std() * np.sqrt(TRADING_DAYS)

    # ── Sharpe (annualised, using EUR risk-free rate) ─────────────────────────
    sharpe_port  = ((port_ret.mean()  - rf_daily) / port_ret.std()  * np.sqrt(TRADING_DAYS)
                    if port_ret.std() > 0 else 0.0)
    sharpe_bench = ((bench_ret.mean() - rf_daily) / bench_ret.std() * np.sqrt(TRADING_DAYS)
                    if bench_ret.std() > 0 else 0.0)

    # ── Sortino (downside deviation only) ─────────────────────────────────────
    downside_port  = port_ret[port_ret  < rf_daily].std() * np.sqrt(TRADING_DAYS)
    downside_bench = bench_ret[bench_ret < rf_daily].std() * np.sqrt(TRADING_DAYS)
    sortino_port   = (cagr_port  - RISK_FREE_RATE) / downside_port  if downside_port  > 0 else 0.0
    sortino_bench  = (cagr_bench - RISK_FREE_RATE) / downside_bench if downside_bench > 0 else 0.0

    # ── Maximum Drawdown ──────────────────────────────────────────────────────
    def max_drawdown(prices: pd.Series) -> float:
        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max
        return float(drawdown.min())

    mdd_port  = max_drawdown(pv)
    mdd_bench = max_drawdown(bv)

    # ── Calmar (CAGR / |Max Drawdown|) ───────────────────────────────────────
    calmar_port  = cagr_port  / abs(mdd_port)  if mdd_port  != 0 else 0.0
    calmar_bench = cagr_bench / abs(mdd_bench) if mdd_bench != 0 else 0.0

    # ── Information Ratio (excess return vs benchmark / tracking error) ───────
    tracking_error = excess_ret.std() * np.sqrt(TRADING_DAYS)
    info_ratio = ((excess_ret.mean() * TRADING_DAYS) / tracking_error
                  if tracking_error > 0 else 0.0)

    # ── Beta / Alpha ──────────────────────────────────────────────────────────
    cov_matrix = np.cov(port_ret.values, bench_ret.values)
    beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] > 0 else 1.0
    alpha_annualised = ((cagr_port - RISK_FREE_RATE)
                        - beta * (cagr_bench - RISK_FREE_RATE))

    # ── Hit rate (% days portfolio outperforms benchmark) ─────────────────────
    hit_rate = float((excess_ret > 0).mean())

    return {
        # Returns
        'total_return_port':  round(total_return_port,  4),
        'total_return_bench': round(total_return_bench, 4),
        'cagr_port':          round(cagr_port,          4),
        'cagr_bench':         round(cagr_bench,         4),
        # Risk
        'vol_port':           round(vol_port,           4),
        'vol_bench':          round(vol_bench,          4),
        'mdd_port':           round(mdd_port,           4),
        'mdd_bench':          round(mdd_bench,          4),
        # Risk-adjusted
        'sharpe_port':        round(sharpe_port,        3),
        'sharpe_bench':       round(sharpe_bench,       3),
        'sortino_port':       round(sortino_port,       3),
        'sortino_bench':      round(sortino_bench,      3),
        'calmar_port':        round(calmar_port,        3),
        'calmar_bench':       round(calmar_bench,       3),
        # Alpha / relative
        'info_ratio':         round(info_ratio,         3),
        'beta':               round(float(beta),        3),
        'alpha_annualised':   round(alpha_annualised,   4),
        'hit_rate':           round(hit_rate,           3),
        # Meta
        'n_days':             n_days,
        'n_years':            round(n_years, 2),
        'start_date':         str(pv.index[0].date()),
        'end_date':           str(pv.index[-1].date()),
        'risk_free_rate':     RISK_FREE_RATE,
    }


def compute_annual_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Year-by-year breakdown: calendar year return for portfolio vs benchmark.
    """
    pv = df['portfolio_value']
    bv = df['benchmark_value']

    years = pv.index.year.unique()
    rows = []
    for yr in sorted(years):
        yr_mask = pv.index.year == yr
        pv_yr = pv[yr_mask]
        bv_yr = bv[yr_mask]
        if len(pv_yr) < 2:
            continue
        port_yr  = pv_yr.iloc[-1] / pv_yr.iloc[0] - 1.0
        bench_yr = bv_yr.iloc[-1] / bv_yr.iloc[0] - 1.0
        rows.append({
            'year':      yr,
            'portfolio': round(port_yr,  4),
            'benchmark': round(bench_yr, 4),
            'excess':    round(port_yr - bench_yr, 4),
        })
    return pd.DataFrame(rows).set_index('year')


def drawdown_series(prices: pd.Series) -> pd.Series:
    """Returns the drawdown from peak at each date."""
    rolling_max = prices.cummax()
    return (prices - rolling_max) / rolling_max


def print_metrics(df: pd.DataFrame):
    """Print a formatted console table of all metrics."""
    m = compute_metrics(df)
    annual = compute_annual_returns(df)

    print("\n" + "="*60)
    print(f"  BACKTEST RESULTS  {m['start_date']} -> {m['end_date']}")
    print(f"  {m['n_years']} years | RF={m['risk_free_rate']*100:.1f}%")
    print("="*60)

    fmt_pct = lambda v: f"{v*100:+.1f}%"
    fmt2    = lambda v: f"{v:.3f}"

    print(f"\n  {'METRIC':<22} {'PORTFOLIO':>10} {'BENCHMARK':>10}")
    print("  " + "-"*44)
    print(f"  {'Total Return':<22} {fmt_pct(m['total_return_port']):>10} {fmt_pct(m['total_return_bench']):>10}")
    print(f"  {'CAGR':<22} {fmt_pct(m['cagr_port']):>10} {fmt_pct(m['cagr_bench']):>10}")
    print(f"  {'Volatility (ann.)':<22} {fmt_pct(m['vol_port']):>10} {fmt_pct(m['vol_bench']):>10}")
    print(f"  {'Max Drawdown':<22} {fmt_pct(m['mdd_port']):>10} {fmt_pct(m['mdd_bench']):>10}")
    print(f"  {'Sharpe':<22} {fmt2(m['sharpe_port']):>10} {fmt2(m['sharpe_bench']):>10}")
    print(f"  {'Sortino':<22} {fmt2(m['sortino_port']):>10} {fmt2(m['sortino_bench']):>10}")
    print(f"  {'Calmar':<22} {fmt2(m['calmar_port']):>10} {fmt2(m['calmar_bench']):>10}")

    print(f"\n  {'RELATIVE METRICS':<30}")
    print("  " + "-"*44)
    print(f"  {'Information Ratio':<22} {fmt2(m['info_ratio']):>10}")
    print(f"  {'Beta':<22} {fmt2(m['beta']):>10}")
    print(f"  {'Alpha (ann.)':<22} {fmt_pct(m['alpha_annualised']):>10}")
    print(f"  {'Hit Rate (daily)':<22} {m['hit_rate']*100:.1f}%")

    print(f"\n  ANNUAL RETURNS")
    print("  " + "-"*44)
    print(f"  {'YEAR':<6} {'PORT':>8} {'BENCH':>8} {'EXCESS':>8}")
    for yr, row in annual.iterrows():
        marker = " +" if row['excess'] > 0 else " -"
        print(f"  {yr:<6} {fmt_pct(row['portfolio']):>8} {fmt_pct(row['benchmark']):>8} "
              f"{fmt_pct(row['excess']):>8}{marker}")
    print("="*60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backtest performance metrics')
    parser.add_argument('--file', default=os.path.join(os.path.dirname(__file__),
                                                        'backtest_results.csv'))
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: {args.file} not found. Run walk_forward.py first.")
        sys.exit(1)

    df = load_results(args.file)
    print_metrics(df)

    # Save metrics to CSV
    m = compute_metrics(df)
    out = os.path.join(os.path.dirname(__file__), 'backtest_metrics.csv')
    pd.Series(m).to_csv(out, header=['value'])
    logger.info(f"Metrics saved to {out}")
