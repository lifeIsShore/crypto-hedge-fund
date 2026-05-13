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
import os
_BL_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if _BL_ROOT not in sys.path:
    sys.path.insert(0, _BL_ROOT)

# Import your existing research implementation directly
from ml_quant_finance_research.general_research.src.factor_model import (
    black_litterman, compute_market_implied_returns
)
import logging

logger = logging.getLogger(__name__)

try:
    from portfolio.src.config import BENCHMARK_TICKER as _BENCHMARK_TICKER
except Exception:
    _BENCHMARK_TICKER = 'EUNL.DE'   # fallback if config unavailable


def load_signals_from_db(date: str, tickers: list) -> pd.DataFrame:
    """Loads all model signals for a given date."""
    session = get_session()
    placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
    params = {f't{i}': t for i, t in enumerate(tickers)}
    params['date'] = date
    result = session.execute(text(f"""
        SELECT ticker, model_name, expected_return, confidence
        FROM signals
        WHERE date = :date AND ticker IN ({placeholders})
    """), params)
    rows = result.fetchall()
    session.close()
    return pd.DataFrame(rows, columns=["ticker", "model_name", "expected_return", "confidence"])



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


def _single_view_omega(
    P_row: np.ndarray,      # 1 × n
    Sigma: np.ndarray,      # n × n
    tau: float,
    ic: float,
) -> float:
    """
    Scalar omega for a single view, consistent with compute_view_omegas.
    Used by build_bl_views_calibrated to avoid re-slicing Sigma per view.
    """
    base = float((P_row @ (tau * Sigma) @ P_row.T)[0, 0])
    return base / (max(ic, 0.01) ** 2)


def build_bl_views_calibrated(
    signals_df: pd.DataFrame,
    tickers: list,
    cov_matrix: pd.DataFrame,
    models_dict: dict = None,
    tau: float = 0.05,
) -> list:
    """
    Builds per-ticker BL views with IC-scaled omega.
    Uses _single_view_omega (consistent with compute_view_omegas) for each view.
    """
    views = []
    models_dict = models_dict or {}
    Sigma = cov_matrix.loc[tickers, tickers].values   # slice once, not per row
    n = len(tickers)

    for _, row in signals_df.iterrows():
        if row["ticker"] not in tickers:
            continue
        ticker_idx = tickers.index(row["ticker"])

        P_row = np.zeros((1, n))
        P_row[0, ticker_idx] = 1.0

        ic = max(0.01, float(row["confidence"]))

        model = models_dict.get(row["model_name"])

        # Gate: if model not live-approved, set omega extremely high (effectively ignored)
        if model and hasattr(model, 'is_live_approved') and not model.is_live_approved():
            omega = 999.0
        else:
            omega = _single_view_omega(P_row, Sigma, tau, ic)

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
    models_dict: dict = None,
    benchmark: str = None,
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
    if benchmark is None:
        benchmark = _BENCHMARK_TICKER
    signals_df = load_signals_from_db(date, tickers)
    alpha_views = build_bl_views_calibrated(signals_df, tickers, cov_matrix, models_dict, tau)

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
