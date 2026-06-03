# engine/portfolio/lab_optimizer.py
"""
Portfolio Lab — On-demand optimizer and risk analytics.

Called exclusively by the Flask /api/lab/optimize endpoint.
Pure computation: no DB writes, no external calls, no Flask imports.

Objectives
----------
max_sharpe   : Maximise Sharpe ratio (Markowitz mean-variance)
min_vol      : Minimum volatility portfolio
risk_parity  : Equal Risk Contribution (Maillard et al.)
equal_weight : Naive 1/N baseline  (no solver)
max_return   : Max expected return subject to vol cap
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import logging

log = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
RF_RATE       = 0.035   # risk-free rate (ECB ~3.5%)
TRADING_DAYS  = 252
MC_PATHS      = 5_000
MC_HORIZON    = 21      # days
FRONTIER_N    = 3_000


# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═════════════════════════════════════════════════════════════════════════════

def load_returns(tickers: list, lookback_days: int) -> tuple[pd.DataFrame, list]:
    """
    Pull adj_close from engine_data.db for the requested tickers.
    Returns (log_returns_df, excluded_tickers).
    Tickers with < lookback/3 data points are excluded with a warning.
    """
    from engine.db.db import get_session
    from sqlalchemy import text

    min_rows = max(30, lookback_days // 3)
    ticker_sql = ",".join(f"'{t}'" for t in tickers)

    session = get_session()
    try:
        rows = session.execute(text(f"""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE ticker IN ({ticker_sql})
              AND adj_close IS NOT NULL AND adj_close > 0
            ORDER BY ticker, date DESC
            LIMIT :lim
        """), {"lim": len(tickers) * lookback_days * 2}).fetchall()
    finally:
        session.close()

    if not rows:
        return pd.DataFrame(), tickers

    df_raw = pd.DataFrame(rows, columns=["date", "ticker", "adj_close"])
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    pivot = (
        df_raw.pivot(index="date", columns="ticker", values="adj_close")
        .sort_index()
        .tail(lookback_days + 1)
    )

    # Drop tickers with too little data
    enough = pivot.columns[pivot.count() >= min_rows].tolist()
    excluded = [t for t in tickers if t not in enough]
    if excluded:
        log.warning(f"[lab] Excluded (insufficient data): {excluded}")

    pivot = pivot[enough].ffill().dropna(how="all")
    log_ret = np.log(pivot / pivot.shift(1)).dropna()
    return log_ret, excluded


# ═════════════════════════════════════════════════════════════════════════════
# COVARIANCE & EXPECTED RETURNS
# ═════════════════════════════════════════════════════════════════════════════

def compute_stats(log_ret: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """
    Annualised expected returns (simple mean) and covariance matrix.
    Uses shrinkage: 80% sample cov + 20% diagonal (Ledoit-Wolf lite).
    """
    mu = log_ret.mean() * TRADING_DAYS
    cov_sample = log_ret.cov() * TRADING_DAYS

    # Ledoit-Wolf diagonal shrinkage
    shrink = 0.15
    diag = np.diag(np.diag(cov_sample.values))
    cov = pd.DataFrame(
        (1 - shrink) * cov_sample.values + shrink * diag,
        index=cov_sample.index,
        columns=cov_sample.columns,
    )
    return mu, cov


# ═════════════════════════════════════════════════════════════════════════════
# OBJECTIVES
# ═════════════════════════════════════════════════════════════════════════════

def _sharpe(w, mu, Sigma):
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ Sigma @ w))
    return -(ret - RF_RATE) / (vol + 1e-9)


def _vol(w, Sigma):
    return float(np.sqrt(w @ Sigma @ w))


def _risk_parity_obj(w, Sigma):
    """Sum of squared differences in risk contributions."""
    port_vol = np.sqrt(w @ Sigma @ w)
    rc = w * (Sigma @ w) / (port_vol + 1e-9)
    target = port_vol / len(w)
    return float(np.sum((rc - target) ** 2))


def _neg_return(w, mu):
    return -float(w @ mu)


def _run_optimizer(
    objective_key: str,
    mu: np.ndarray,
    Sigma: np.ndarray,
    n: int,
    min_w: float,
    max_w: float,
) -> np.ndarray:
    """Run SLSQP optimizer; return weight array."""
    w0 = np.ones(n) / n
    bounds = [(min_w, max_w)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    if objective_key == "max_sharpe":
        fun = lambda w: _sharpe(w, mu, Sigma)
    elif objective_key == "min_vol":
        fun = lambda w: _vol(w, Sigma)
    elif objective_key == "risk_parity":
        fun = lambda w: _risk_parity_obj(w, Sigma)
    elif objective_key == "max_return":
        # Max return subject to vol <= 25% annualised
        vol_cap = 0.25
        constraints.append({
            "type": "ineq",
            "fun": lambda w: vol_cap - float(np.sqrt(w @ Sigma @ w))
        })
        fun = lambda w: _neg_return(w, mu)
    else:
        return w0  # equal_weight — skip solver

    result = minimize(
        fun, w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 2000, "ftol": 1e-10},
    )
    if not result.success:
        log.warning(f"[lab] Optimizer ({objective_key}) did not converge: {result.message}")
    w = np.clip(result.x, 0, 1)
    return w / w.sum()


# ═════════════════════════════════════════════════════════════════════════════
# METRICS
# ═════════════════════════════════════════════════════════════════════════════

def _portfolio_metrics(w: np.ndarray, mu: np.ndarray, Sigma: np.ndarray, individual_vols: np.ndarray) -> dict:
    ret_ann = float(w @ mu)
    vol_ann = float(np.sqrt(w @ Sigma @ w))
    sharpe  = (ret_ann - RF_RATE) / (vol_ann + 1e-9)
    # Diversification ratio: weighted avg of individual vols / portfolio vol
    div_ratio = float(np.dot(w, individual_vols) / (vol_ann + 1e-9))
    # Cornish-Fisher adjustment for non-normal VaR (simple version)
    z95, z99 = 1.645, 2.326
    daily_vol = vol_ann / np.sqrt(TRADING_DAYS)
    horizon_vol = daily_vol * np.sqrt(MC_HORIZON)
    horizon_ret = ret_ann * MC_HORIZON / TRADING_DAYS
    var95  = horizon_ret - z95 * horizon_vol
    var99  = horizon_ret - z99 * horizon_vol
    cvar95 = horizon_ret - horizon_vol * (np.exp(-0.5 * z95**2) / (np.sqrt(2*np.pi) * 0.05))
    return {
        "ret_ann":            round(ret_ann * 100, 2),
        "vol_ann":            round(vol_ann * 100, 2),
        "sharpe":             round(sharpe, 3),
        "var95_pct":          round(var95 * 100, 2),
        "var99_pct":          round(var99 * 100, 2),
        "cvar95_pct":         round(cvar95 * 100, 2),
        "max_drawdown_est":   round(-2.5 * vol_ann * np.sqrt(1) * 100, 2),  # rough estimate
        "diversification_ratio": round(div_ratio, 3),
    }


# ═════════════════════════════════════════════════════════════════════════════
# EFFICIENT FRONTIER
# ═════════════════════════════════════════════════════════════════════════════

def build_efficient_frontier(mu: np.ndarray, Sigma: np.ndarray, tickers: list, min_w: float, max_w: float) -> list:
    """
    Sample FRONTIER_N random feasible portfolios.
    Returns list of [vol_pct, ret_pct, sharpe].
    """
    n = len(tickers)
    results = []
    rng = np.random.default_rng(seed=42)

    for _ in range(FRONTIER_N):
        # Dirichlet gives uniform distribution on simplex
        raw = rng.dirichlet(np.ones(n))
        # Apply weight bounds by clipping and renormalising
        w = np.clip(raw, min_w, max_w)
        if w.sum() < 1e-9:
            continue
        w /= w.sum()
        ret = float(w @ mu)
        vol = float(np.sqrt(w @ Sigma @ w))
        sharpe = (ret - RF_RATE) / (vol + 1e-9)
        results.append([round(vol * 100, 3), round(ret * 100, 3), round(sharpe, 3)])

    return results


# ═════════════════════════════════════════════════════════════════════════════
# MONTE CARLO
# ═════════════════════════════════════════════════════════════════════════════

def run_monte_carlo(
    weights: dict,
    log_ret: pd.DataFrame,
    portfolio_size_eur: float,
) -> dict:
    """
    Parametric MC with correlated assets using Cholesky decomposition.
    Returns sampled paths for fan chart + histogram + VaR.
    """
    tickers = list(weights.keys())
    w = np.array([weights[t] for t in tickers])
    sub_ret = log_ret[tickers].dropna()

    mu_daily = sub_ret.mean().values
    Sigma_daily = sub_ret.cov().values

    rng = np.random.default_rng(seed=0)
    try:
        L = np.linalg.cholesky(Sigma_daily + np.eye(len(tickers)) * 1e-8)
    except np.linalg.LinAlgError:
        L = np.diag(np.sqrt(np.diag(Sigma_daily)))

    # Shape: (MC_PATHS, MC_HORIZON, n_assets)
    z = rng.standard_normal((MC_PATHS, MC_HORIZON, len(tickers)))
    corr_z = z @ L.T
    daily_rets = mu_daily + corr_z  # (MC_PATHS, MC_HORIZON, n_assets)

    # Portfolio cumulative return per path: (MC_PATHS,)
    port_log_ret = (daily_rets * w).sum(axis=2)           # (MC_PATHS, MC_HORIZON)
    cum_ret = np.exp(port_log_ret.cumsum(axis=1)) - 1     # (MC_PATHS, MC_HORIZON)

    final_ret = cum_ret[:, -1]  # (MC_PATHS,)
    var95  = float(np.percentile(final_ret, 5) * 100)
    var99  = float(np.percentile(final_ret, 1) * 100)
    cvar95 = float(np.mean(final_ret[final_ret <= np.percentile(final_ret, 5)]) * 100)
    p_profit = float(np.mean(final_ret > 0) * 100)
    p_up5    = float(np.mean(final_ret > 0.05) * 100)
    p_down10 = float(np.mean(final_ret < -0.10) * 100)
    exp_ret  = float(np.mean(final_ret) * 100)

    # Sample 30 paths for fan chart (portfolio value in EUR)
    n_fan = 30
    idx = rng.choice(MC_PATHS, size=n_fan, replace=False)
    fan_paths = (portfolio_size_eur * (1 + cum_ret[idx, :])).tolist()

    # Histogram of final return
    hist_counts, hist_edges = np.histogram(final_ret * 100, bins=60)
    hist_centers = ((hist_edges[:-1] + hist_edges[1:]) / 2).round(2).tolist()

    return {
        "var95_pct":   round(var95, 2),
        "var99_pct":   round(var99, 2),
        "cvar95_pct":  round(cvar95, 2),
        "p_profit":    round(p_profit, 1),
        "p_up5":       round(p_up5, 1),
        "p_down10":    round(p_down10, 1),
        "exp_ret_pct": round(exp_ret, 2),
        "fan_paths":   [list(np.round(p, 2)) for p in fan_paths],
        "histogram":   {"labels": hist_centers, "counts": hist_counts.tolist()},
    }


# ═════════════════════════════════════════════════════════════════════════════
# CORRELATION
# ═════════════════════════════════════════════════════════════════════════════

def compute_correlation(log_ret: pd.DataFrame) -> dict:
    """Returns correlation matrix as nested list + ticker list."""
    corr = log_ret.corr().round(3)
    return {
        "tickers": corr.columns.tolist(),
        "matrix":  corr.values.tolist(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def run_lab_optimization(
    tickers: list,
    objective: str = "max_sharpe",
    lookback_days: int = 504,
    portfolio_size_eur: float = 10_000.0,
    min_weight: float = 0.0,
    max_weight: float = 0.40,
) -> dict:
    """
    Full lab pipeline. Called by Flask /api/lab/optimize.
    Returns a single JSON-serialisable dict with everything the frontend needs.
    """
    if len(tickers) < 2:
        return {"error": "Need at least 2 tickers"}

    # ── 1. Load returns ───────────────────────────────────────────────────────
    log_ret, excluded = load_returns(tickers, lookback_days)
    available = [t for t in tickers if t not in excluded and t in log_ret.columns]

    if len(available) < 2:
        return {"error": f"Insufficient price data. Excluded: {excluded}"}

    log_ret = log_ret[available]

    # ── 2. Stats ──────────────────────────────────────────────────────────────
    mu, cov = compute_stats(log_ret)
    mu_arr    = mu.values
    Sigma_arr = cov.values
    n         = len(available)
    individual_vols = np.sqrt(np.diag(Sigma_arr))

    # ── 3. Optimal weights ────────────────────────────────────────────────────
    w_opt = _run_optimizer(objective, mu_arr, Sigma_arr, n, min_weight, max_weight)
    weights_dict = {t: round(float(w), 4) for t, w in zip(available, w_opt)}

    # ── 4. Baseline: equal weight ─────────────────────────────────────────────
    w_ew = np.ones(n) / n
    weights_ew = {t: round(float(w), 4) for t, w in zip(available, w_ew)}

    # ── 5. Metrics ────────────────────────────────────────────────────────────
    metrics_opt = _portfolio_metrics(w_opt, mu_arr, Sigma_arr, individual_vols)
    metrics_ew  = _portfolio_metrics(w_ew,  mu_arr, Sigma_arr, individual_vols)

    # Per-ticker summary
    returns_summary = {
        t: {
            "ret_ann_pct": round(float(mu[t]) * 100, 2),
            "vol_ann_pct": round(float(np.sqrt(cov.loc[t, t])) * 100, 2),
        }
        for t in available
    }

    # ── 6. Efficient frontier ─────────────────────────────────────────────────
    frontier = build_efficient_frontier(mu_arr, Sigma_arr, available, min_weight, max_weight)

    # ── 7. Monte Carlo ────────────────────────────────────────────────────────
    mc_results = run_monte_carlo(weights_dict, log_ret, portfolio_size_eur)

    # ── 8. Correlation ────────────────────────────────────────────────────────
    correlation = compute_correlation(log_ret)

    return {
        "ok":              True,
        "tickers":         available,
        "excluded":        excluded,
        "objective":       objective,
        "lookback_days":   lookback_days,
        "portfolio_size":  portfolio_size_eur,
        "weights":         weights_dict,
        "weights_ew":      weights_ew,
        "metrics":         metrics_opt,
        "metrics_ew":      metrics_ew,
        "returns_summary": returns_summary,
        "frontier":        frontier,
        "monte_carlo":     mc_results,
        "correlation":     correlation,
    }
