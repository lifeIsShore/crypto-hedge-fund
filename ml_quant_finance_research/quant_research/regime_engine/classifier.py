# quant-research/regime_engine/classifier.py
"""
Macro Regime Classifier — Rules-Based (Phase 1)
Classifies each trading day across three independent axes:
  Axis 1 — Risk Appetite  : Risk-On / Neutral / Risk-Off
  Axis 2 — Rate Environment: Easing / Neutral / Tightening
  Axis 3 — Growth Cycle   : Expansion / Slowdown / Contraction / Recovery

Also computes early-warning flags and a composite label.
All thresholds imported from config.py and applied per region.
"""

import logging
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

from config import (
    THRESHOLDS,
    EW_VIX_RISING_FROM, EW_VIX_RISING_TO, EW_VIX_WINDOW,
    EW_YIELD_FLATTEN_BPS, EW_YIELD_FLATTEN_WINDOW,
    EW_HY_WIDEN_BPS, EW_HY_WIDEN_WINDOW,
    EW_RATE_REPRICE_THRESHOLD, EW_RATE_REPRICE_WINDOW,
    EW_TRIGGER_COUNT,
)


# ── Axis 1: Risk Appetite ────────────────────────────────────────────────────

def classify_risk_axis(df: pd.DataFrame, region: str = "US") -> pd.Series:
    """
    Uses VIX level + trend + HY credit spread to classify risk appetite.
    """
    t = THRESHOLDS.get(region, THRESHOLDS["US"])
    vix    = df["vix"]
    hy     = df.get("hy_spread")
    result = pd.Series("Neutral", index=df.index, name="regime_risk")

    vix_trend = vix.rolling(t["RISK_VIX_TREND_WINDOW"]).mean().diff()

    for i in range(len(df)):
        v  = vix.iloc[i]
        hy_val = float(hy.iloc[i]) if hy is not None and not pd.isna(hy.iloc[i]) else 5.0
        trend  = vix_trend.iloc[i] if not pd.isna(vix_trend.iloc[i]) else 0.0

        if v > t["RISK_OFF_VIX_MIN"] or hy_val > t["HY_WIDE_THRESHOLD"]:
            result.iloc[i] = "Risk-Off"
        elif v < t["RISK_ON_VIX_MAX"] and hy_val < t["HY_TIGHT_THRESHOLD"] and trend <= 0:
            result.iloc[i] = "Risk-On"
        else:
            result.iloc[i] = "Neutral"

    return result


# ── Axis 2: Rate Environment ─────────────────────────────────────────────────

def classify_rate_axis(df: pd.DataFrame, region: str = "US") -> pd.Series:
    """
    Uses the rate of change in policy rate to classify rate environment.
    """
    t = THRESHOLDS.get(region, THRESHOLDS["US"])
    rates = df.get("fed_funds")
    result = pd.Series("Neutral", index=df.index, name="regime_rates")

    if rates is None:
        log.warning(f"Rates series missing for {region} — rate axis defaulting to Neutral")
        return result

    rate_change = rates.diff(t["RATE_LOOKBACK_DAYS"])

    for i in range(len(df)):
        chg = rate_change.iloc[i]
        if pd.isna(chg):
            result.iloc[i] = "Neutral"
        elif chg <= t["RATE_EASING_THRESHOLD"]:
            result.iloc[i] = "Easing"
        elif chg >= t["RATE_TIGHTENING_THRESHOLD"]:
            result.iloc[i] = "Tightening"
        else:
            result.iloc[i] = "Neutral"

    return result


# ── Axis 3: Growth Cycle ─────────────────────────────────────────────────────

def classify_growth_axis(df: pd.DataFrame, region: str = "US") -> pd.Series:
    """
    Uses the yield spread level and trend to classify the growth cycle.
    """
    t = THRESHOLDS.get(region, THRESHOLDS["US"])
    yld    = df.get("yield_spread")
    result = pd.Series("Slowdown", index=df.index, name="regime_growth")

    if yld is None:
        log.warning(f"Yield spread series missing for {region} — growth axis defaulting to Slowdown")
        return result

    yld_trend = yld.rolling(t["YIELD_CURVE_TREND_WINDOW"]).mean().diff()

    prev_state = None
    for i in range(len(df)):
        spread = yld.iloc[i]
        trend  = yld_trend.iloc[i] if not pd.isna(yld_trend.iloc[i]) else 0.0

        if pd.isna(spread):
            result.iloc[i] = "Slowdown"
            continue

        if spread < t["YIELD_CURVE_INVERSION_MAX"]:
            result.iloc[i] = "Contraction"
        elif spread > t["YIELD_CURVE_EXPANSION_MIN"] and trend >= 0:
            result.iloc[i] = "Expansion"
        elif prev_state == "Contraction" and spread >= 0:
            result.iloc[i] = "Recovery"
        else:
            result.iloc[i] = "Slowdown"

        prev_state = result.iloc[i]

    return result


# ── Early Warning Flags ───────────────────────────────────────────────────────

def compute_early_warnings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Checks early warning conditions per row. (Static thresholds for now).
    """
    vix = df.get("vix", pd.Series(dtype=float))
    yld = df.get("yield_spread", pd.Series(dtype=float))
    hy  = df.get("hy_spread", pd.Series(dtype=float))
    fed = df.get("fed_funds", pd.Series(dtype=float))

    ew = pd.DataFrame(index=df.index)

    if not vix.empty:
        vix_min_lookback = vix.rolling(EW_VIX_WINDOW).min()
        ew["ew_vix_rising"] = (vix_min_lookback < EW_VIX_RISING_FROM) & (vix > EW_VIX_RISING_TO)
    else:
        ew["ew_vix_rising"] = False

    if not yld.empty:
        yld_change = yld.diff(EW_YIELD_FLATTEN_WINDOW) * 100
        ew["ew_curve_flattening"] = yld_change <= EW_YIELD_FLATTEN_BPS
    else:
        ew["ew_curve_flattening"] = False

    if not hy.empty:
        hy_change = hy.diff(EW_HY_WIDEN_WINDOW) * 100
        ew["ew_hy_widening"] = hy_change >= EW_HY_WIDEN_BPS
    else:
        ew["ew_hy_widening"] = False

    if not fed.empty:
        fed_change = fed.diff(EW_RATE_REPRICE_WINDOW).abs() * 100
        ew["ew_rate_reprice"] = fed_change >= EW_RATE_REPRICE_THRESHOLD * 100
    else:
        ew["ew_rate_reprice"] = False

    ew_cols = ["ew_vix_rising", "ew_curve_flattening", "ew_hy_widening", "ew_rate_reprice"]
    ew["ew_active_count"]    = ew[ew_cols].sum(axis=1)
    ew["transition_warning"] = ew["ew_active_count"] >= EW_TRIGGER_COUNT

    return ew


# ── Full Classification Pipeline ──────────────────────────────────────────────

def classify_all(df: pd.DataFrame, region: str = "US") -> pd.DataFrame:
    """Main entry point. Region-aware."""
    log.info(f"Classifying {len(df)} trading days for region: {region}...")

    risk_axis   = classify_risk_axis(df, region=region)
    rate_axis   = classify_rate_axis(df, region=region)
    growth_axis = classify_growth_axis(df, region=region)

    def make_composite(risk, rate, growth):
        risk_short = risk.replace("-", "").replace(" ", "")
        return f"{risk_short}_{rate}_{growth}"

    composite = pd.Series(
        [make_composite(r, ra, g)
         for r, ra, g in zip(risk_axis, rate_axis, growth_axis)],
        index=df.index,
        name="regime_composite"
    )

    ew_df = compute_early_warnings(df)
    result = pd.concat([df, risk_axis, rate_axis, growth_axis, composite, ew_df], axis=1)

    latest = result.iloc[-1]
    log.info(
        f"Latest {region} regime [{result.index[-1].date()}]: "
        f"{latest['regime_composite']} | EW={latest['transition_warning']}"
    )

    return result
