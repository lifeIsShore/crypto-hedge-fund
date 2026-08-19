# engine/risk/post_trade.py
"""
Post-trade risk monitoring: VaR, CVaR, drawdown, regime detection.
Promotes your existing regime.py and research metrics.
"""
import numpy as np
import pandas as pd
from scipy import stats
from engine.features.feature_store import load_returns_from_db
from engine.db.db import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def historical_var_cvar(returns: pd.Series, confidence: float = 0.95) -> dict:
    """Historical simulation VaR and CVaR — no normality assumption."""
    sorted_ret = returns.sort_values()
    cutoff_idx = int((1 - confidence) * len(sorted_ret))
    var  = float(sorted_ret.iloc[cutoff_idx])
    cvar = float(sorted_ret.iloc[:cutoff_idx].mean())
    return {"var_95": round(var, 4), "cvar_95": round(cvar, 4)}


def drawdown_metrics(equity_curve: pd.Series) -> dict:
    rolling_max  = equity_curve.cummax()
    drawdown     = (equity_curve - rolling_max) / rolling_max
    max_dd       = float(drawdown.min())
    current_dd   = float(drawdown.iloc[-1])
    return {"max_drawdown": round(max_dd, 4), "current_drawdown": round(current_dd, 4)}


def portfolio_returns_from_weights(
    weights: dict, log_returns: pd.DataFrame, lookback: int = 252
) -> pd.Series:
    tickers = [t for t in weights if t in log_returns.columns]
    w = np.array([weights[t] for t in tickers])
    w = w / w.sum()
    return log_returns[tickers].tail(lookback).dot(w)


def compute_regime_stress(tickers: list) -> dict:
    """
    Wraps your existing composite regime engine from regime.py.
    Returns current stress score and regime label.
    """
    log_returns = load_returns_from_db(tickers)
    if log_returns.empty:
        return {"stress_score": 0.5, "regime": "medium"}

    from ml_quant_finance_research.general_research.src.regime import compute_composite_regime
    portfolio_ret = log_returns.mean(axis=1)
    regime_df = compute_composite_regime(portfolio_ret, log_returns)
    latest = regime_df.iloc[-1]
    return {
        "stress_score":  float(latest["stress_score"]),
        "regime":        latest["regime"],
        "vol_component": float(latest["vol_component"]),
    }


def run_post_trade_risk(weights: dict, tickers: list) -> dict:
    """Full post-trade risk snapshot. Called after every rebalance."""
    log_returns = load_returns_from_db(tickers)
    port_returns = portfolio_returns_from_weights(weights, log_returns)
    equity_curve = (1 + port_returns).cumprod()

    var_cvar = historical_var_cvar(port_returns)
    dd       = drawdown_metrics(equity_curve)
    regime   = compute_regime_stress(tickers)

    metrics = {**var_cvar, **dd, **regime}

    # Stress tests — market drawdown × portfolio beta-weighted equity exposure.
    # Shocks sourced from /api/stress_tests which computes real betas vs EUNL.DE.
    # Here we use simple equity_weight × shock as a conservative lower-bound;
    # the dashboard's /api/stress_tests endpoint applies per-ticker betas.
    stress_shocks = {
        "gfc_2008":        -0.57,
        "covid_2020":      -0.34,
        "dot_com_2000":    -0.49,
        "rate_shock_2022": -0.255,
        "flash_crash_2010": -0.099,
    }
    equity_weight = sum(w for t, w in weights.items() if t != "CASH")
    for scenario, shock in stress_shocks.items():
        metrics[f"stress_{scenario}"] = round(equity_weight * shock, 4)

    # Persist to DB
    # Bug fix (2026-08-20): the `isinstance(val, (int, float))` filter silently
    # dropped the 'regime' key, since compute_regime_stress() returns a STRING
    # label (e.g. "medium"), not a number. That meant `regime` was NEVER written
    # to risk_metrics, so the digest's `_build_risk_summary()` always fell back
    # to "unknown" even though the regime was computed correctly (visible only
    # in the log line below, never in the DB or dashboard digest).
    # risk_metrics.metric_value is REAL-typed, so we can't store the string
    # there directly — instead we map it to a small numeric code and also log
    # it to pipeline_logs so the human-readable label survives for the digest.
    REGIME_CODES = {"low": 0.0, "medium": 1.0, "high": 2.0}
    session = get_session()
    for metric_name, val in metrics.items():
        if isinstance(val, (int, float)):
            session.execute(text("""
                INSERT INTO risk_metrics (date, metric_name, metric_value)
                VALUES (CURRENT_DATE, :name, :val)
                ON CONFLICT (date, metric_name) DO UPDATE SET metric_value = EXCLUDED.metric_value
            """), {"name": metric_name, "val": float(val)})
        elif metric_name == "regime" and isinstance(val, str):
            session.execute(text("""
                INSERT INTO risk_metrics (date, metric_name, metric_value)
                VALUES (CURRENT_DATE, 'regime_code', :val)
                ON CONFLICT (date, metric_name) DO UPDATE SET metric_value = EXCLUDED.metric_value
            """), {"val": REGIME_CODES.get(val, -1.0)})
            session.execute(text("""
                INSERT INTO pipeline_logs (level, step_name, message, detail, run_date)
                VALUES ('INFO', 'post_trade_risk', :msg, :val, date('now'))
            """), {"msg": f"Regime label: {val}", "val": val})
    session.commit()
    session.close()
    logger.info(f"Post-trade risk: VaR={var_cvar['var_95']:.2%}, CVaR={var_cvar['cvar_95']:.2%}, Regime={regime['regime']}")
    return metrics
