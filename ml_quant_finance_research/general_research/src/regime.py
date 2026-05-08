# research/src/regime.py
#
# Regime detection functions.
# Called by 02_regime_detection.ipynb.
# Returns plain DataFrames and dicts — no side effects, no I/O.

import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. REALISED VOLATILITY REGIME
# ─────────────────────────────────────────────

def compute_realised_vol(log_returns: pd.Series, window: int = 21) -> pd.Series:
    """
    Annualised rolling realised volatility of a return series.
    Uses a 21-day (1 month) rolling window by default.
    """
    return (log_returns.rolling(window).std() * np.sqrt(252)).dropna()


def classify_vol_regime(
    realised_vol: pd.Series,
    low_threshold:  float = 0.12,
    high_threshold: float = 0.22,
) -> pd.Series:
    """
    Maps each date's realised volatility to a regime label.

    low_stress  : ann. vol < low_threshold  (calm market)
    medium      : low_threshold <= vol <= high_threshold
    high_stress : ann. vol > high_threshold (turbulent market)
    """
    conditions = [
        realised_vol < low_threshold,
        realised_vol > high_threshold,
    ]
    choices = ['low_stress', 'high_stress']
    return pd.Series(
        np.select(conditions, choices, default='medium'),
        index=realised_vol.index,
        name='vol_regime',
    )


# ─────────────────────────────────────────────
# 2. CORRELATION COMPRESSION
# ─────────────────────────────────────────────

def compute_correlation_compression(
    log_returns: pd.DataFrame,
    window: int = 30,
) -> pd.Series:
    """
    Measures the average pairwise correlation across all tickers on a
    rolling basis. When assets start moving together (correlation rises),
    it signals stress — diversification is breaking down.

    Returns a Series indexed by date.
    """
    result = {}
    tickers = log_returns.columns.tolist()
    n = len(tickers)

    if n < 2:
        logger.warning("Need at least 2 tickers for correlation compression.")
        return pd.Series(dtype=float)

    for end_idx in range(window, len(log_returns) + 1):
        window_slice = log_returns.iloc[end_idx - window: end_idx]
        date_key     = log_returns.index[end_idx - 1]
        corr_matrix  = window_slice.corr().values

        # Extract upper triangle (exclude diagonal)
        upper_idx = np.triu_indices(n, k=1)
        pairwise  = corr_matrix[upper_idx]
        pairwise  = pairwise[~np.isnan(pairwise)]

        result[date_key] = float(np.mean(np.abs(pairwise))) if len(pairwise) > 0 else np.nan

    series = pd.Series(result, name='corr_compression')
    logger.info(f"Correlation compression computed: {len(series)} observations (window={window}d)")
    return series


# ─────────────────────────────────────────────
# 3. COMPOSITE REGIME SCORE
# ─────────────────────────────────────────────

def compute_composite_regime(
    portfolio_log_returns: pd.Series,
    log_returns_all: pd.DataFrame,
    vol_window:       int   = 21,
    corr_window:      int   = 30,
    vol_low:          float = 0.12,
    vol_high:         float = 0.22,
    corr_high:        float = 0.65,
) -> pd.DataFrame:
    """
    Combines volatility regime and correlation compression into a
    single composite stress score (0–1) and regime label per date.

    Stress score formula:
        vol_component  = clip((vol - vol_low) / (vol_high - vol_low), 0, 1)
        corr_component = clip(corr_compression / corr_high, 0, 1)
        stress_score   = 0.6 * vol_component + 0.4 * corr_component

    Regime:
        stress < 0.35  → low_stress
        stress < 0.65  → medium
        stress >= 0.65 → high_stress

    Returns a DataFrame with columns:
        date, realised_vol, vol_regime, corr_compression,
        vol_component, corr_component, stress_score, regime
    """
    # Realised vol
    r_vol       = compute_realised_vol(portfolio_log_returns, window=vol_window)
    vol_regime  = classify_vol_regime(r_vol, vol_low, vol_high)

    # Correlation compression (on all assets in the data)
    corr_comp   = compute_correlation_compression(log_returns_all, window=corr_window)

    # Align on common dates
    aligned = pd.DataFrame({
        'realised_vol':      r_vol,
        'vol_regime':        vol_regime,
        'corr_compression':  corr_comp,
    }).dropna()

    # Stress components
    vol_range = vol_high - vol_low
    aligned['vol_component']  = ((aligned['realised_vol'] - vol_low) / vol_range).clip(0, 1)
    aligned['corr_component'] = (aligned['corr_compression'] / corr_high).clip(0, 1)
    aligned['stress_score']   = (
        0.6 * aligned['vol_component'] +
        0.4 * aligned['corr_component']
    ).round(4)

    # Regime label
    def label(s):
        if s < 0.35:  return 'low_stress'
        if s < 0.65:  return 'medium'
        return 'high_stress'

    aligned['regime'] = aligned['stress_score'].apply(label)

    logger.info(
        f"Composite regime: {len(aligned)} observations | "
        f"Current: {aligned['regime'].iloc[-1]} "
        f"(stress={aligned['stress_score'].iloc[-1]:.3f})"
    )
    return aligned.reset_index().rename(columns={'index': 'date'})


# ─────────────────────────────────────────────
# 4. REGIME PROBABILITIES
# ─────────────────────────────────────────────

def compute_regime_probabilities(
    regime_df: pd.DataFrame,
    lookback_days: int = 60,
) -> dict:
    """
    Estimates the probability of each regime over a rolling lookback window
    by counting how many of the last N days were in each state.

    Returns:
        {
            'low_stress':  0.65,
            'medium':      0.25,
            'high_stress': 0.10,
        }
    """
    recent = regime_df.tail(lookback_days)
    counts = recent['regime'].value_counts()
    total  = len(recent)

    probs = {}
    for r in ['low_stress', 'medium', 'high_stress']:
        probs[r] = round(counts.get(r, 0) / total, 4) if total > 0 else 0.0

    return probs


# ─────────────────────────────────────────────
# 5. REGIME TRANSITION STATS
# ─────────────────────────────────────────────

def compute_transition_stats(regime_df: pd.DataFrame) -> dict:
    """
    Computes how long the portfolio has been in the current regime
    and the average duration of each regime historically.

    Returns a dict with:
        current_regime, days_in_current_regime,
        avg_duration_per_regime: { regime: avg_days }
    """
    if regime_df.empty:
        return {}

    regimes       = regime_df['regime'].tolist()
    current       = regimes[-1]
    days_in_curr  = 1

    for r in reversed(regimes[:-1]):
        if r == current:
            days_in_curr += 1
        else:
            break

    # Average duration per regime
    durations = {r: [] for r in ['low_stress', 'medium', 'high_stress']}
    run_regime, run_len = regimes[0], 1
    for r in regimes[1:]:
        if r == run_regime:
            run_len += 1
        else:
            durations[run_regime].append(run_len)
            run_regime, run_len = r, 1
    durations[run_regime].append(run_len)

    avg_durations = {
        r: round(np.mean(v), 1) if v else 0.0
        for r, v in durations.items()
    }

    return {
        'current_regime':          current,
        'days_in_current_regime':  days_in_curr,
        'avg_duration_per_regime': avg_durations,
    }
