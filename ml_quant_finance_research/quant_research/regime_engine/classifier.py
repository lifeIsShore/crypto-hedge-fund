# quant-research/regime_engine/classifier.py
"""
Macro Regime Classifier — Rules-Based (Phase 1)

Classifies each trading day across three independent axes:
  Axis 1 — Risk Appetite  : Risk-On / Neutral / Risk-Off
  Axis 2 — Rate Environment: Easing / Neutral / Tightening
  Axis 3 — Growth Cycle   : Expansion / Slowdown / Contraction / Recovery

Also computes early-warning flags and a composite label.

All thresholds imported from config.py — never hardcoded here.
"""

import logging
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

from config import (
    RISK_ON_VIX_MAX, RISK_OFF_VIX_MIN, RISK_VIX_TREND_WINDOW,
    HY_TIGHT_THRESHOLD, HY_WIDE_THRESHOLD,
    RATE_EASING_THRESHOLD, RATE_TIGHTENING_THRESHOLD, RATE_LOOKBACK_DAYS,
    YIELD_CURVE_EXPANSION_MIN, YIELD_CURVE_INVERSION_MAX, YIELD_CURVE_TREND_WINDOW,
    EW_VIX_RISING_FROM, EW_VIX_RISING_TO, EW_VIX_WINDOW,
    EW_YIELD_FLATTEN_BPS, EW_YIELD_FLATTEN_WINDOW,
    EW_HY_WIDEN_BPS, EW_HY_WIDEN_WINDOW,
    EW_RATE_REPRICE_THRESHOLD, EW_RATE_REPRICE_WINDOW,
    EW_TRIGGER_COUNT,
)


# ── Axis 1: Risk Appetite ────────────────────────────────────────────────────

def classify_risk_axis(df: pd.DataFrame) -> pd.Series:
    """
    Uses VIX level + trend + HY credit spread to classify risk appetite.

    Logic:
      Risk-Off  : VIX > 28  OR  HY spread > 6.0
      Risk-On   : VIX < 20  AND  HY spread < 4.0  AND  VIX trending down
      Neutral   : everything else
    """
    vix    = df["vix"]
    hy     = df.get("hy_spread")
    result = pd.Series("Neutral", index=df.index, name="regime_risk")

    # VIX trend: positive = rising (deteriorating), negative = falling (improving)
    vix_trend = vix.rolling(RISK_VIX_TREND_WINDOW).mean().diff()

    for i in range(len(df)):
        v  = vix.iloc[i]
        hy_val = float(hy.iloc[i]) if hy is not None and not pd.isna(hy.iloc[i]) else 5.0
        trend  = vix_trend.iloc[i] if not pd.isna(vix_trend.iloc[i]) else 0.0

        if v > RISK_OFF_VIX_MIN or hy_val > HY_WIDE_THRESHOLD:
            result.iloc[i] = "Risk-Off"
        elif v < RISK_ON_VIX_MAX and hy_val < HY_TIGHT_THRESHOLD and trend <= 0:
            result.iloc[i] = "Risk-On"
        else:
            result.iloc[i] = "Neutral"

    return result


# ── Axis 2: Rate Environment ─────────────────────────────────────────────────

def classify_rate_axis(df: pd.DataFrame) -> pd.Series:
    """
    Uses the 3-month change in Fed Funds Rate to classify rate environment.
    """
    fed = df.get("fed_funds")
    result = pd.Series("Neutral", index=df.index, name="regime_rates")

    if fed is None:
        log.warning("fed_funds series missing — rate axis defaulting to Neutral")
        return result

    # 63-day (≈3 month) change in fed funds
    fed_change = fed.diff(RATE_LOOKBACK_DAYS)

    for i in range(len(df)):
        chg = fed_change.iloc[i]
        if pd.isna(chg):
            result.iloc[i] = "Neutral"
        elif chg <= RATE_EASING_THRESHOLD:
            result.iloc[i] = "Easing"
        elif chg >= RATE_TIGHTENING_THRESHOLD:
            result.iloc[i] = "Tightening"
        else:
            result.iloc[i] = "Neutral"

    return result


# ── Axis 3: Growth Cycle ─────────────────────────────────────────────────────

def classify_growth_axis(df: pd.DataFrame) -> pd.Series:
    """
    Uses the 10Y-2Y yield spread level and trend to classify the growth cycle.

    Expansion   : spread > 0.3 AND trending up (curve steepening)
    Slowdown    : spread 0.0 to 0.3 OR trending down from expansion
    Contraction : spread < -0.1 (inverted)
    Recovery    : spread was negative, now turning positive
    """
    yld    = df.get("yield_spread")
    result = pd.Series("Slowdown", index=df.index, name="regime_growth")

    if yld is None:
        log.warning("yield_spread series missing — growth axis defaulting to Slowdown")
        return result

    yld_trend = yld.rolling(YIELD_CURVE_TREND_WINDOW).mean().diff()

    # Track the previous state for Recovery detection
    prev_state = None
    for i in range(len(df)):
        spread = yld.iloc[i]
        trend  = yld_trend.iloc[i] if not pd.isna(yld_trend.iloc[i]) else 0.0

        if pd.isna(spread):
            result.iloc[i] = "Slowdown"
            continue

        if spread < YIELD_CURVE_INVERSION_MAX:
            result.iloc[i] = "Contraction"
        elif spread > YIELD_CURVE_EXPANSION_MIN and trend >= 0:
            result.iloc[i] = "Expansion"
        elif prev_state == "Contraction" and spread >= 0:
            result.iloc[i] = "Recovery"   # coming out of inversion
        else:
            result.iloc[i] = "Slowdown"

        prev_state = result.iloc[i]

    return result


# ── Early Warning Flags ───────────────────────────────────────────────────────

def compute_early_warnings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Checks 4 independent early warning conditions per row.
    Returns a DataFrame with boolean columns per EW type and a
    'transition_warning' boolean (True when EW_TRIGGER_COUNT+ conditions active).
    """
    vix = df.get("vix", pd.Series(dtype=float))
    yld = df.get("yield_spread", pd.Series(dtype=float))
    hy  = df.get("hy_spread", pd.Series(dtype=float))
    fed = df.get("fed_funds", pd.Series(dtype=float))

    ew = pd.DataFrame(index=df.index)

    # EW1: VIX rising from calm to stress zone within EW_VIX_WINDOW days
    if not vix.empty:
        vix_min_lookback = vix.rolling(EW_VIX_WINDOW).min()
        ew["ew_vix_rising"] = (vix_min_lookback < EW_VIX_RISING_FROM) & (vix > EW_VIX_RISING_TO)
    else:
        ew["ew_vix_rising"] = False

    # EW2: Yield curve flattening > 20bps in EW_YIELD_FLATTEN_WINDOW days
    if not yld.empty:
        yld_change = yld.diff(EW_YIELD_FLATTEN_WINDOW) * 100  # convert to bps
        ew["ew_curve_flattening"] = yld_change <= EW_YIELD_FLATTEN_BPS
    else:
        ew["ew_curve_flattening"] = False

    # EW3: HY spreads widening > 50bps in EW_HY_WIDEN_WINDOW days
    if not hy.empty:
        hy_change = hy.diff(EW_HY_WIDEN_WINDOW) * 100  # bps
        ew["ew_hy_widening"] = hy_change >= EW_HY_WIDEN_BPS
    else:
        ew["ew_hy_widening"] = False

    # EW4: Fed funds rate repriced > 50bps in EW_RATE_REPRICE_WINDOW days
    if not fed.empty:
        fed_change = fed.diff(EW_RATE_REPRICE_WINDOW).abs() * 100  # bps
        ew["ew_rate_reprice"] = fed_change >= EW_RATE_REPRICE_THRESHOLD * 100
    else:
        ew["ew_rate_reprice"] = False

    # Composite: True if EW_TRIGGER_COUNT or more EW flags are active
    ew_cols = ["ew_vix_rising", "ew_curve_flattening", "ew_hy_widening", "ew_rate_reprice"]
    ew["ew_active_count"]    = ew[ew_cols].sum(axis=1)
    ew["transition_warning"] = ew["ew_active_count"] >= EW_TRIGGER_COUNT

    return ew


# ── Full Classification Pipeline ──────────────────────────────────────────────

def classify_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main entry point. Takes raw macro DataFrame, returns full regime DataFrame.

    Output columns:
      vix, yield_spread, hy_spread, ig_spread, fed_funds, ism_mfg
      regime_risk, regime_rates, regime_growth
      regime_composite  (e.g. "RiskOn_Easing_Expansion")
      ew_vix_rising, ew_curve_flattening, ew_hy_widening, ew_rate_reprice
      ew_active_count, transition_warning
    """
    log.info(f"Classifying {len(df)} trading days...")

    risk_axis   = classify_risk_axis(df)
    rate_axis   = classify_rate_axis(df)
    growth_axis = classify_growth_axis(df)

    # Composite label: spaces stripped, underscore-separated for easy querying
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

    # Summary log for most recent day
    latest = result.iloc[-1]
    log.info(
        f"Latest regime [{result.index[-1].date()}]: "
        f"Risk={latest['regime_risk']} | "
        f"Rates={latest['regime_rates']} | "
        f"Growth={latest['regime_growth']} | "
        f"EW={latest['transition_warning']} ({int(latest['ew_active_count'])}/4 triggers)"
    )

    return result
