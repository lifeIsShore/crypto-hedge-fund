# research/src/factor_model.py
#
# Fama-French 3-factor regression and Black-Litterman implementation.
# Called by 03_factor_model.ipynb and 04_black_litterman.ipynb.

import numpy as np
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def fetch_fama_french_factors(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Downloads the Fama-French 3-factor daily data from Kenneth French's website
    via pandas-datareader. Returns a DataFrame with columns:
        Mkt-RF, SMB, HML, RF  (all in decimal form, i.e. /100)

    NOTE (2026-08-10): pandas_datareader is imported HERE, lazily, not at module
    level. This function is research-only (used by 03_factor_model.ipynb) and is
    NOT part of the daily production path — engine/portfolio/black_litterman.py
    only imports `black_litterman` and `compute_market_implied_returns` from this
    file, never this function. A module-level `import pandas_datareader.data`
    was previously crashing the entire daily portfolio-construction pipeline step
    with ModuleNotFoundError whenever pandas_datareader wasn't installed in the
    venv, even though the production path never used it. See PROJECT-STATE.md.
    """
    import pandas_datareader.data as web
    logger.info("Fetching Fama-French 3-factor data from Kenneth French's website...")
    try:
        ff = web.DataReader('F-F_Research_Data_Factors_daily', 'famafrench',
                            start=start_date, end=end_date)[0]
        ff = ff / 100.0  # Convert from percent to decimal
        ff.index = pd.to_datetime(ff.index)
        logger.info(f"FF factors: {len(ff)} observations ({ff.index[0].date()} → {ff.index[-1].date()})")
        return ff
    except Exception as e:
        logger.error(f"Failed to fetch FF factors: {e}")
        raise


def run_factor_regression(
    asset_returns: pd.Series,
    ff_factors: pd.DataFrame,
) -> dict:
    """
    Runs OLS regression of asset excess returns on FF 3 factors.

    Model: R_i - RF = alpha + beta_mkt*(Mkt-RF) + beta_smb*SMB + beta_hml*HML + e

    Returns a dict with:
        alpha, beta_mkt, beta_smb, beta_hml,
        alpha_tstat, alpha_pvalue, r_squared,
        annualised_alpha_pct

    NOTE (2026-08-10): statsmodels is imported HERE, lazily, not at module
    level, for the same reason as pandas_datareader above — this function is
    research-only (03_factor_model.ipynb) and outside the daily production
    path. See the note on fetch_fama_french_factors().
    """
    import statsmodels.api as sm

    # Align on common dates
    aligned = pd.concat([asset_returns, ff_factors], axis=1).dropna()
    aligned.columns = ['R_asset', 'Mkt_RF', 'SMB', 'HML', 'RF']

    if len(aligned) < 60:
        logger.warning(f"Only {len(aligned)} observations — regression unreliable.")
        return None

    # Excess return
    y = aligned['R_asset'] - aligned['RF']
    X = sm.add_constant(aligned[['Mkt_RF', 'SMB', 'HML']])

    model = sm.OLS(y, X).fit()

    alpha       = float(model.params['const'])
    alpha_ann   = float(alpha * 252 * 100)  # annualised, in %
    alpha_tstat = float(model.tvalues['const'])
    alpha_pval  = float(model.pvalues['const'])

    return {
        'alpha_daily':        round(alpha, 6),
        'annualised_alpha_pct': round(alpha_ann, 3),
        'alpha_tstat':        round(alpha_tstat, 3),
        'alpha_pvalue':       round(alpha_pval, 4),
        'beta_mkt':           round(float(model.params['Mkt_RF']), 4),
        'beta_smb':           round(float(model.params['SMB']), 4),
        'beta_hml':           round(float(model.params['HML']), 4),
        'r_squared':          round(float(model.rsquared), 4),
        'n_obs':              len(aligned),
    }


def run_factor_regressions_all(
    log_returns: pd.DataFrame,
    ff_factors: pd.DataFrame,
    tickers: list,
    alpha_tstat_threshold: float = 2.0,
) -> pd.DataFrame:
    """
    Runs FF regressions for all tickers in the list.
    Returns a DataFrame with one row per ticker, columns from run_factor_regression.
    Flags tickers with statistically significant alpha (|t| > threshold).
    """
    rows = []
    for ticker in tickers:
        if ticker not in log_returns.columns:
            continue
        result = run_factor_regression(log_returns[ticker], ff_factors)
        if result:
            result['ticker']         = ticker
            result['alpha_sig']      = abs(result['alpha_tstat']) >= alpha_tstat_threshold
            result['return_source']  = 'alpha' if result['alpha_sig'] and result['annualised_alpha_pct'] > 0 \
                                       else 'beta' if result['beta_mkt'] > 0.8 else 'mixed'
            rows.append(result)

    df = pd.DataFrame(rows)
    if not df.empty:
        cols = ['ticker', 'annualised_alpha_pct', 'alpha_tstat', 'alpha_pvalue',
                'beta_mkt', 'beta_smb', 'beta_hml', 'r_squared', 'alpha_sig', 'return_source', 'n_obs']
        df = df[cols].sort_values('alpha_tstat', ascending=False).reset_index(drop=True)

    logger.info(f"Factor regressions: {len(df)} tickers | "
                f"{df['alpha_sig'].sum() if not df.empty else 0} with significant alpha")
    return df


# ─────────────────────────────────────────────
# BLACK-LITTERMAN
# ─────────────────────────────────────────────

def compute_market_implied_returns(
    cov_matrix: pd.DataFrame,
    market_weights: pd.Series,
    risk_aversion: float = 2.5,
) -> pd.Series:
    """
    Computes the market equilibrium (implied) returns using reverse optimisation.
    Pi = delta * Sigma * w_mkt
    """
    pi = risk_aversion * cov_matrix.dot(market_weights)
    return pi


def black_litterman(
    cov_matrix: pd.DataFrame,
    market_weights: pd.Series,
    views: list,          # list of dicts: {assets, weights, Q, omega}
    tau: float = 0.05,
    risk_aversion: float = 2.5,
) -> pd.Series:
    """
    Black-Litterman model — returns posterior expected returns.

    views: list of dicts, each with:
        assets  : list of tickers involved in this view
        weights : list of +/- weights (must sum to 0 for relative, or 1 for absolute)
        Q       : scalar — the expected return of this view (annualised decimal)
        omega   : scalar — confidence (variance) of this view; higher = less confident

    Returns a pd.Series of posterior expected returns (annualised).
    """
    n      = len(market_weights)
    tickers = market_weights.index.tolist()

    # Equilibrium returns
    pi = compute_market_implied_returns(cov_matrix, market_weights, risk_aversion)

    if not views:
        logger.info("No views provided — returning equilibrium returns.")
        return pi

    # Build P matrix (k x n) and Q vector (k,)
    k   = len(views)
    P   = np.zeros((k, n))
    Q   = np.zeros(k)
    Omega = np.zeros((k, k))

    for i, v in enumerate(views):
        Q[i] = v['Q']
        Omega[i, i] = v['omega']
        for asset, w in zip(v['assets'], v['weights']):
            if asset in tickers:
                j = tickers.index(asset)
                P[i, j] = w

    Sigma = cov_matrix.values
    pi_arr = pi.values

    # BL posterior formula
    # M = (tau*Sigma)^-1 + P'*Omega^-1*P
    # mu_BL = M^-1 * ((tau*Sigma)^-1 * pi + P'*Omega^-1*Q)
    tau_sigma_inv = np.linalg.inv(tau * Sigma)
    omega_inv     = np.linalg.inv(Omega)

    M      = tau_sigma_inv + P.T @ omega_inv @ P
    M_inv  = np.linalg.inv(M)
    mu_bl  = M_inv @ (tau_sigma_inv @ pi_arr + P.T @ omega_inv @ Q)

    result = pd.Series(mu_bl, index=tickers)
    logger.info(f"BL posterior returns computed for {n} assets with {k} views.")
    return result


def build_regime_views(
    tickers: list,
    benchmark_ticker: str,
    regime: str,
    stress_score: float,
    bl_regime_map: dict = None,
) -> list:
    """
    Converts current regime into Black-Litterman views.

    Logic:
      - high_stress  → view: benchmark will underperform by stress_score * scale
      - low_stress   → view: benchmark will outperform by (1-stress_score) * scale
      - medium       → no strong view (small adjustment)

    Returns a list of BL view dicts.
    """
    if bl_regime_map is None:
        bl_regime_map = {
            'high_stress': -0.04,   # expect -4% ann. from benchmark in stress
            'medium':       0.01,
            'low_stress':   0.03,
        }

    if benchmark_ticker not in tickers:
        logger.warning(f"Benchmark {benchmark_ticker} not in tickers — no regime view injected.")
        return []

    base_view = bl_regime_map.get(regime, 0.0)
    # Scale by stress score for proportionality
    Q_view = base_view * (stress_score if regime == 'high_stress' else (1 - stress_score))

    # Confidence: high stress → high confidence in the view (low omega)
    omega = 0.0001 if regime == 'high_stress' else 0.001

    view = {
        'assets':  [benchmark_ticker],
        'weights': [1.0],
        'Q':       round(Q_view, 5),
        'omega':   omega,
    }
    logger.info(f"Regime view: {regime} → benchmark Q={Q_view:.4f}, omega={omega}")
    return [view]
