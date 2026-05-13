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

# Constraints — MAX_POSITION intentionally tighter than config.MAX_WEIGHT (0.25);
# BL optimizer already accounts for uncertainty so 10% cap reduces concentration risk.
# Change by updating MAX_POSITION here only; document in portfolio/docs/03-TUNING-LOG.md.
MAX_POSITION     = 0.10   # 10% max per asset in the BL-optimised portfolio
MAX_SECTOR_SHARE = 0.30   # 30% max in any one sector (mirrors pre_trade.py MAX_SECTOR)
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
    try:
        for ticker in suggested.index:
            sugg = float(suggested.get(ticker, 0))
            curr = float(current.get(ticker, 0))
            delt = sugg - curr
            bl_r = float(mu_bl.get(ticker, 0))
            session.execute(text("""
                INSERT INTO model_outputs
                    (date, ticker, suggested_weight, current_weight, delta_weight, bl_return, computed_at)
                VALUES (:date, :ticker, :suggested, :current, :delta, :bl_return, datetime('now'))
                ON CONFLICT (date, ticker) DO UPDATE SET
                    suggested_weight = :suggested,
                    delta_weight     = :delta,
                    bl_return        = :bl_return,
                    computed_at      = datetime('now')
            """), {
                "date": date, "ticker": ticker,
                "suggested": sugg, "current": curr,
                "delta": delt, "bl_return": bl_r,
            })
        session.commit()
        logger.info(f"Model outputs persisted: {date}, {len(suggested)} tickers")
    except Exception as e:
        session.rollback()
        logger.error(f"persist_model_outputs failed: {e}")
        raise
    finally:
        session.close()
