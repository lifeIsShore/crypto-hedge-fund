# research/src/correlation.py
#
# Core correlation engine functions.
# Called by 01_correlation_engine.ipynb.
# Returns plain DataFrames and dicts — no side effects, no I/O.

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. ROLLING CORRELATIONS
# ─────────────────────────────────────────────

def rolling_correlation_matrix(log_returns: pd.DataFrame, window: int) -> dict:
    """
    Computes pairwise Pearson correlations on a rolling window.

    Returns a dict keyed by date (ISO string), each value being a
    {ticker: {ticker: corr}} dict — JSON-serialisable.
    Only the final snapshot (latest date) is typically needed for the
    dashboard; the full history is used for stability scoring.
    """
    result = {}
    tickers = log_returns.columns.tolist()

    for end_idx in range(window, len(log_returns) + 1):
        window_slice = log_returns.iloc[end_idx - window : end_idx]
        date_key = str(log_returns.index[end_idx - 1].date())
        corr_df = window_slice.corr(method='pearson')
        result[date_key] = corr_df.round(4).to_dict()

    logger.info(f"Rolling correlation computed: window={window}d, {len(result)} snapshots")
    return result


def latest_correlation_matrix(log_returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Returns just the most recent correlation matrix as a DataFrame.
    Much faster than rolling_correlation_matrix when you only need today.
    """
    return log_returns.tail(window).corr(method='pearson').round(4)


# ─────────────────────────────────────────────
# 2. STABILITY SCORING
# ─────────────────────────────────────────────

def compute_stability_scores(log_returns: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    """
    For every pair (i, j), computes the rolling window-day correlation at
    each date, then measures the standard deviation of that time series.

    A low std means the correlation is stable over time → trustworthy.
    A high std means the correlation flips around → unreliable for hedging.

    Returns a DataFrame with columns:
        ticker_a, ticker_b, mean_corr, std_corr, stability_score
        (stability_score = 1 - std_corr, clipped to [0, 1])
    """
    tickers = log_returns.columns.tolist()
    n = len(tickers)
    rows = []

    for i in range(n):
        for j in range(i + 1, n):
            a, b = tickers[i], tickers[j]
            pair_returns = log_returns[[a, b]].dropna()

            if len(pair_returns) < window + 10:
                continue

            # Rolling correlation time series
            rolling_corr = pair_returns[a].rolling(window).corr(pair_returns[b]).dropna()

            if len(rolling_corr) < 10:
                continue

            mean_corr = float(rolling_corr.mean())
            std_corr  = float(rolling_corr.std())
            stability = float(np.clip(1.0 - std_corr, 0, 1))

            rows.append({
                'ticker_a':        a,
                'ticker_b':        b,
                'mean_corr':       round(mean_corr, 4),
                'std_corr':        round(std_corr, 4),
                'stability_score': round(stability, 4),
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('stability_score', ascending=False).reset_index(drop=True)

    logger.info(f"Stability scores computed for {len(df)} pairs (window={window}d)")
    return df


# ─────────────────────────────────────────────
# 3. BREAKDOWN DETECTION
# ─────────────────────────────────────────────

def detect_correlation_breakdowns(
    log_returns: pd.DataFrame,
    short_window: int = 30,
    long_window: int = 90,
    threshold: float = 0.20,
) -> list:
    """
    Flags pairs where the short-term correlation has diverged significantly
    from the long-term correlation — a sign the relationship is breaking down.

    A positive spread means: short-term correlation is HIGHER than long-term
    (pair moving together more than usual — possible crisis compression).
    A negative spread means: short-term correlation is LOWER than long-term
    (pair decoupling — hedge may be weakening).

    Returns a list of dicts, sorted by abs(spread) descending.
    """
    tickers = log_returns.columns.tolist()
    alerts = []

    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            pair = log_returns[[a, b]].dropna()

            if len(pair) < long_window:
                continue

            corr_short = float(pair.tail(short_window).corr().iloc[0, 1])
            corr_long  = float(pair.tail(long_window).corr().iloc[0, 1])
            spread     = round(corr_short - corr_long, 4)

            if abs(spread) >= threshold:
                severity = 'high' if abs(spread) >= threshold * 1.5 else 'medium'
                alerts.append({
                    'ticker_a':    a,
                    'ticker_b':    b,
                    'corr_short':  round(corr_short, 4),
                    'corr_long':   round(corr_long, 4),
                    'spread':      spread,
                    'direction':   'compressing' if spread > 0 else 'decoupling',
                    'severity':    severity,
                })

    alerts.sort(key=lambda x: abs(x['spread']), reverse=True)
    logger.info(f"Breakdown detection: {len(alerts)} alerts flagged (threshold={threshold})")
    return alerts


# ─────────────────────────────────────────────
# 4. TRADEABILITY SCORING
# ─────────────────────────────────────────────

def compute_tradeability_scores(
    log_returns: pd.DataFrame,
    stability_df: pd.DataFrame,
    min_abs_corr: float = 0.40,
) -> pd.DataFrame:
    """
    Combines correlation strength, stability, and volatility compatibility
    into a single tradeability score (0–10) for each pair.

    Score components:
        - Correlation magnitude (0–4 pts): abs(mean_corr) scaled to 4
        - Stability             (0–3 pts): stability_score scaled to 3
        - Vol compatibility     (0–3 pts): 1 - abs(vol_a - vol_b) / max(vol_a, vol_b)

    Also tags each pair as:
        - 'hedge'    → strong negative correlation (mean_corr < -0.5)
        - 'stat-arb' → strong positive correlation with mean reversion signal
        - 'monitor'  → moderate correlation, watch for regime
    """
    if stability_df.empty:
        return pd.DataFrame()

    # Compute annualised volatility per ticker
    ann_vol = (log_returns.std() * np.sqrt(252)).to_dict()

    rows = []
    for _, row in stability_df.iterrows():
        a, b = row['ticker_a'], row['ticker_b']
        mean_corr = row['mean_corr']

        if abs(mean_corr) < min_abs_corr:
            continue

        vol_a = ann_vol.get(a, np.nan)
        vol_b = ann_vol.get(b, np.nan)

        if np.isnan(vol_a) or np.isnan(vol_b) or max(vol_a, vol_b) == 0:
            vol_compat = 0.0
        else:
            vol_compat = float(1.0 - abs(vol_a - vol_b) / max(vol_a, vol_b))

        # Score components
        corr_pts    = abs(mean_corr) * 4.0
        stable_pts  = row['stability_score'] * 3.0
        vol_pts     = vol_compat * 3.0
        total_score = round(corr_pts + stable_pts + vol_pts, 2)

        # Tag
        if mean_corr < -0.50:
            tag = 'hedge'
        elif mean_corr > 0.50:
            tag = 'stat-arb'
        else:
            tag = 'monitor'

        rows.append({
            'ticker_a':         a,
            'ticker_b':         b,
            'mean_corr':        round(mean_corr, 4),
            'stability_score':  round(row['stability_score'], 4),
            'vol_a_ann':        round(vol_a, 4),
            'vol_b_ann':        round(vol_b, 4),
            'vol_compat':       round(vol_compat, 4),
            'tradeability':     total_score,
            'tag':              tag,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('tradeability', ascending=False).reset_index(drop=True)

    logger.info(f"Tradeability scores: {len(df)} pairs scored, {len(df[df.tag=='hedge'])} hedge, "
                f"{len(df[df.tag=='stat-arb'])} stat-arb")
    return df


# ─────────────────────────────────────────────
# 5. LEAD-LAG DETECTION
# ─────────────────────────────────────────────

def compute_lead_lag(
    log_returns: pd.DataFrame,
    tickers: list,
    max_lag: int = 5,
) -> list:
    """
    For each pair in tickers, computes cross-correlations at lags 1..max_lag.
    Returns pairs where a lag > 0 gives meaningfully higher correlation
    than lag 0 — suggesting one asset leads the other.

    Returns a list of dicts sorted by lead strength descending.
    """
    results = []
    n = len(tickers)

    for i in range(n):
        for j in range(i + 1, n):
            a, b = tickers[i], tickers[j]
            series_a = log_returns[a].dropna()
            series_b = log_returns[b].dropna()
            aligned  = pd.concat([series_a, series_b], axis=1).dropna()

            if len(aligned) < max_lag * 10:
                continue

            ra = aligned.iloc[:, 0]
            rb = aligned.iloc[:, 1]

            # Contemporaneous correlation
            corr_0 = float(ra.corr(rb))

            best_lag   = 0
            best_corr  = corr_0
            best_leader = None

            for lag in range(1, max_lag + 1):
                # a leads b
                corr_a_leads = float(ra.shift(lag).corr(rb))
                # b leads a
                corr_b_leads = float(rb.shift(lag).corr(ra))

                if abs(corr_a_leads) > abs(best_corr):
                    best_corr   = corr_a_leads
                    best_lag    = lag
                    best_leader = a

                if abs(corr_b_leads) > abs(best_corr):
                    best_corr   = corr_b_leads
                    best_lag    = lag
                    best_leader = b

            # Only report if a lagged corr is meaningfully stronger
            lead_strength = abs(best_corr) - abs(corr_0)
            if best_lag > 0 and lead_strength > 0.05:
                follower = b if best_leader == a else a
                results.append({
                    'leader':         best_leader,
                    'follower':       follower,
                    'lag_days':       best_lag,
                    'corr_at_lag':    round(best_corr, 4),
                    'corr_at_0':      round(corr_0, 4),
                    'lead_strength':  round(lead_strength, 4),
                })

    results.sort(key=lambda x: x['lead_strength'], reverse=True)
    logger.info(f"Lead-lag: {len(results)} significant pairs found (max_lag={max_lag})")
    return results
