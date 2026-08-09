# engine/portfolio/optimizer.py
"""
Extended optimizer: BL returns + turnover penalty + cost model.
Extends portfolio/src/math_optimizer.py — does not replace it.
The original is still used for the simple backtester.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
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

# J1 — Correlation cluster concentration limit (see before-go-live/J1-correlation-cluster-constraint.md)
MAX_CLUSTER_SHARE = 0.25            # 25% max per correlation cluster
CLUSTER_DISTANCE_THRESHOLD = 0.35   # dendrogram cut point (lower = more, smaller clusters)
MIN_CLUSTER_SIZE_TO_CONSTRAIN = 2   # singleton clusters need no constraint


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


def build_correlation_clusters(tickers: list, cov_matrix: pd.DataFrame) -> dict:
    """
    Groups tickers into correlation clusters using hierarchical clustering
    on the correlation-distance matrix (distance = 1 - |correlation|).
    Returns {ticker: cluster_id}. See J1 doc for full rationale.
    """
    if len(tickers) < 3:
        return {t: 0 for t in tickers}

    sub = cov_matrix.loc[tickers, tickers].values
    std = np.sqrt(np.diag(sub))
    # Guard against zero-variance tickers (e.g. a brand-new listing with 1 data point)
    std_safe = np.where(std == 0, 1e-12, std)
    corr = sub / np.outer(std_safe, std_safe)
    corr = np.clip(corr, -1.0, 1.0)

    distance = 1 - np.abs(corr)
    np.fill_diagonal(distance, 0)
    distance = (distance + distance.T) / 2  # enforce exact symmetry (float rounding safety)
    condensed = squareform(distance, checks=False)

    Z = linkage(condensed, method='average')
    cluster_ids = fcluster(Z, t=CLUSTER_DISTANCE_THRESHOLD, criterion='distance')

    return dict(zip(tickers, cluster_ids))


def build_cluster_constraints(tickers: list, cluster_map: dict, max_cluster: float = MAX_CLUSTER_SHARE) -> list:
    """Generates one inequality constraint per correlation cluster with >= 2 members."""
    clusters = {}
    for i, t in enumerate(tickers):
        cid = cluster_map.get(t)
        if cid is not None:
            clusters.setdefault(cid, []).append(i)

    constraints = []
    for cid, indices in clusters.items():
        if len(indices) < MIN_CLUSTER_SIZE_TO_CONSTRAIN:
            continue
        constraints.append({
            "type": "ineq",
            "fun": lambda w, idx=indices: max_cluster - np.sum(w[idx])
        })
    return constraints


def persist_correlation_clusters(date: str, cluster_map: dict):
    """Persists cluster membership so the dashboard can explain WHY a position was capped."""
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS correlation_clusters (
                date        TEXT NOT NULL,
                ticker      TEXT NOT NULL,
                cluster_id  INTEGER NOT NULL,
                computed_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (date, ticker)
            )
        """))
        for ticker, cid in cluster_map.items():
            session.execute(text("""
                INSERT INTO correlation_clusters (date, ticker, cluster_id)
                VALUES (:date, :ticker, :cid)
                ON CONFLICT (date, ticker) DO UPDATE SET
                    cluster_id = :cid, computed_at = datetime('now')
            """), {"date": date, "ticker": ticker, "cid": int(cid)})
        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"persist_correlation_clusters failed (non-fatal): {e}")
    finally:
        session.close()


def optimize_with_bl(
    mu_bl: pd.Series,
    cov_matrix: pd.DataFrame,
    current_weights: pd.Series,
    current_prices: pd.Series = None,
    sector_map: dict = None,
    risk_aversion: float = 2.5,
    date: str = None,
    apply_cluster_constraint: bool = True,
    apply_tax_penalty: bool = True,
) -> pd.Series:
    """
    Constrained optimizer using BL posterior returns.

    Objective:
        maximize  mu_BL · w  −  (δ/2) wᵀΣw  −  turnover_penalty · |Δw|  −  costs · |Δw|  −  tax_drag

    date: if provided (and apply_cluster_constraint=True), cluster membership
          is persisted to the correlation_clusters table for dashboard display.
    current_prices: if provided (and apply_tax_penalty=True), a per-ticker
          unrealized-gain tax drag penalty (J2) is applied to sell decisions,
          using the currently active jurisdiction from tax_settings (see
          engine/portfolio/tax_rates.py). Sells only, never buys/holds.
    """
    tickers = mu_bl.index.tolist()
    n = len(tickers)

    # Align current weights
    w0 = np.array([current_weights.get(t, 0.0) for t in tickers])
    mu = mu_bl.values
    Sigma = cov_matrix.loc[tickers, tickers].values

    # J2 — tax-aware selling: unrealized gain % per ticker, only computed if
    # we have prices to compute a gain from. tax_rate comes from whatever
    # jurisdiction is active in Settings — see tax_rates.get_active_tax_rate().
    unrealized_gain_pct = np.zeros(n)
    tax_rate = 0.0
    if apply_tax_penalty and current_prices is not None:
        try:
            from engine.portfolio.tax_rates import get_active_tax_rate
            from engine.risk.circuit_breaker import get_average_entry_prices
            tax_rate = get_active_tax_rate()
            if tax_rate > 0:
                entry_prices = get_average_entry_prices()
                unrealized_gain_pct = np.array([
                    max(0.0, (current_prices.get(t, 0) - entry_prices.get(t, current_prices.get(t, 0)))
                        / entry_prices.get(t, current_prices.get(t, 1)))
                    if entry_prices.get(t) else 0.0
                    for t in tickers
                ])
        except Exception as e:
            logger.warning(f"[J2] Tax penalty setup failed, proceeding without it (non-fatal): {e}")
            tax_rate = 0.0
            unrealized_gain_pct = np.zeros(n)

    def objective(w):
        ret       = np.dot(mu, w)
        risk      = 0.5 * risk_aversion * w @ Sigma @ w
        delta_w   = w - w0
        abs_delta = np.abs(delta_w)
        turnover  = TURNOVER_PENALTY * np.sum(abs_delta)
        costs     = SLIPPAGE_PCT * np.sum(abs_delta)
        # Tax drag: only SELLS (delta_w < 0) of positions with unrealized gains
        sell_amounts = np.clip(-delta_w, 0, None)
        tax_drag  = np.sum(sell_amounts * unrealized_gain_pct * tax_rate)
        return -(ret - risk - turnover - costs - tax_drag)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if sector_map:
        constraints += build_sector_constraints(tickers, sector_map)

    # J1 — correlation cluster constraint
    if apply_cluster_constraint:
        try:
            cluster_map = build_correlation_clusters(tickers, cov_matrix)
            constraints += build_cluster_constraints(tickers, cluster_map)
            if date:
                persist_correlation_clusters(date, cluster_map)
        except Exception as e:
            logger.warning(f"[J1] Correlation cluster constraint failed, skipping (non-fatal): {e}")

    bounds = [(0, MAX_POSITION)] * n

    result = minimize(
        objective, x0=w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9}
    )

    if not result.success:
        logger.warning(f"BL optimizer did not converge: {result.message}")

    weights = pd.Series(np.round(result.x, 4), index=tickers)

    MIN_DELTA_WEIGHT = 0.005  # 0.5% minimum meaningful weight change
    for ticker in tickers:
        current = current_weights.get(ticker, 0.0)
        suggested = weights[ticker]
        if abs(suggested - current) < MIN_DELTA_WEIGHT:
            weights[ticker] = current  # snap back to current — not worth trading

    return weights


def persist_model_outputs(date: str, suggested: pd.Series, current: pd.Series, mu_bl: pd.Series, signal_breakdown: dict = None):
    import json
    session = get_session()
    try:
        for ticker in suggested.index:
            sugg = float(suggested.get(ticker, 0))
            curr = float(current.get(ticker, 0))
            delt = sugg - curr
            bl_r = float(mu_bl.get(ticker, 0))
            breakdown_json = json.dumps(signal_breakdown.get(ticker, {}) if signal_breakdown else {})
            session.execute(text("""
                INSERT INTO model_outputs
                    (date, ticker, suggested_weight, current_weight, delta_weight, bl_return, signal_breakdown, computed_at)
                VALUES (:date, :ticker, :suggested, :current, :delta, :bl_return, :breakdown, datetime('now'))
                ON CONFLICT (date, ticker) DO UPDATE SET
                    suggested_weight = :suggested,
                    delta_weight     = :delta,
                    bl_return        = :bl_return,
                    signal_breakdown = :breakdown,
                    computed_at      = datetime('now')
            """), {
                "date": date, "ticker": ticker,
                "suggested": sugg, "current": curr,
                "delta": delt, "bl_return": bl_r,
                "breakdown": breakdown_json,
            })
        session.commit()
        logger.info(f"Model outputs persisted: {date}, {len(suggested)} tickers")
    except Exception as e:
        session.rollback()
        logger.error(f"persist_model_outputs failed: {e}")
        raise
    finally:
        session.close()
