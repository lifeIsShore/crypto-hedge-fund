"""feature_builder.py — All feature families + automatic feature selection.

Feature families:
  1. Price (returns, momentum distances, gap)
  2. Volume (OBV, relative volume, divergence signals)
  3. Technical (RSI, MACD, Bollinger, ATR, Stochastic)
  4. Fundamental (PE, PB, EV/EBITDA, margins, FCF)
  5. Macro (Fed funds, CPI, yield curve, DXY)
  6. Options (ATM IV, put/call ratio, skew, IV-RV spread)  ← NEW
  7. Short interest (short % float, days-to-cover, change)  ← NEW

Feature selection (runs once after the first RF fold):
  - Variance threshold: drop near-constant features
  - Correlation dedup: drop one of any pair with r > 0.95
  - Importance gate: drop features with RF importance < 0.5/n_features
"""
import numpy as np
import pandas as pd
import logging

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FAMILIES 1–5 (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def add_price_features(df):
    c = df["Adj Close"]
    for n in [1, 5, 10, 21, 63]:
        df[f"ret_{n}d"] = c.pct_change(n)
    df["log_ret_1d"] = np.log(c / c.shift(1))
    for w in [21, 63]:
        df[f"vol_{w}d"] = df["log_ret_1d"].rolling(w).std() * np.sqrt(252)
    for ma in [50, 200]:
        ma_s = c.rolling(ma).mean()
        df[f"price_vs_ma{ma}"] = (c - ma_s) / ma_s
    df["dist_52w_high"] = (c - c.rolling(252).max()) / c.rolling(252).max()
    df["dist_52w_low"]  = (c - c.rolling(252).min()) / c.rolling(252).min()
    df["gap_pct"] = (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)
    return df


def add_volume_features(df):
    v = df["Volume"].replace(0, np.nan)
    df["rel_volume"]   = v / v.rolling(21).mean()
    df["volume_trend"] = v.rolling(5).mean() / v.rolling(21).mean()
    obv = (v * np.sign(df["Close"].diff())).fillna(0).cumsum()
    df["obv_zscore"] = (obv - obv.rolling(63).mean()) / (obv.rolling(63).std() + 1e-9)
    ret = df["Close"].pct_change()
    df["vol_price_div_up"]   = ((ret > 0) & (v < v.rolling(5).mean())).astype(int)
    df["vol_price_div_down"] = ((ret < 0) & (v > v.rolling(5).mean())).astype(int)
    return df


def add_technical_features(df):
    c, h, l = df["Close"], df["High"], df["Low"]
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))   # standard Wilder RSI: 0–100
    ema12  = c.ewm(span=12, adjust=False).mean()
    ema26  = c.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = macd - signal
    df["macd_signal"] = signal
    ma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_position"] = (c - (ma20 - 2 * std20)) / (4 * std20 + 1e-9)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr_norm"] = tr.rolling(14).mean() / c
    df["stoch_k"] = (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min() + 1e-9)
    return df


def add_fundamental_features(df, fundamentals):
    mapping = {
        "trailingPE":         "fund_pe",
        "priceToBook":        "fund_pb",
        "enterpriseToEbitda": "fund_ev_ebitda",
        "revenueGrowth":      "fund_rev_growth",
        "grossMargins":       "fund_gross_margin",
        "operatingMargins":   "fund_op_margin",
        "debtToEquity":       "fund_de",
        "freeCashflow":       "fund_fcf",
    }
    for k, col in mapping.items():
        val = fundamentals.get(k)
        df[col] = float(val) if (val is not None and not isinstance(val, str)) else np.nan
    return df


def add_macro_features(df, macro):
    aligned = macro.reindex(df.index, method="ffill", limit=5)
    for col in aligned.columns:
        df[f"macro_{col}"] = aligned[col].values
    return df


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FAMILY 6+7 — Options & Short Interest (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def add_options_features(df, options_dict: dict):
    """
    Adds options and short interest features as constant columns (point-in-time).
    options_dict: output of options_scraper.fetch_options_features()

    Note: these are static scalars (fetched today), not time series.
    They represent the current market's view of this stock.
    """
    COLS = {
        "iv_atm":          "opt_iv_atm",
        "iv_rv_spread":    "opt_iv_rv_spread",    # vol risk premium
        "iv_skew":         "opt_iv_skew",         # put/call skew (fear gauge)
        "iv_change_5d":    "opt_iv_change_5d",    # IV momentum
        "pc_ratio":        "opt_pc_ratio",        # put/call volume ratio
        "short_pct_float": "opt_short_pct",       # % float sold short
        "short_ratio":     "opt_short_ratio",     # days to cover
        "short_change":    "opt_short_change",    # recent change in short interest
    }
    for src_key, col_name in COLS.items():
        val = options_dict.get(src_key, np.nan)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            df[col_name] = np.nan
        else:
            df[col_name] = float(val)
    return df


def add_target(df, horizons=None):
    if horizons is None:
        horizons = [5, 21, 63]
    c = df["Adj Close"]
    for n in horizons:
        fut = c.shift(-n) / c - 1
        df[f"target_dir_{n}d"]  = (fut > 0).astype(int)
        df[f"future_ret_{n}d"]  = fut
        bins = [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf]
        df[f"target_mag_{n}d"]  = pd.cut(fut, bins=bins, labels=[0, 1, 2, 3, 4]).astype("Int64")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE SELECTION (anti-overfitting)
# ─────────────────────────────────────────────────────────────────────────────

def select_features(X: pd.DataFrame, importance_dict: dict = None,
                    variance_threshold: float = 0.005,
                    corr_threshold: float = 0.95,
                    importance_gate: float = 0.40) -> list:
    """
    Three-stage feature selection to prevent overfitting.

    Args:
        X:                  Feature DataFrame (rows=samples, cols=features)
        importance_dict:    {feature: importance} from RandomForest (optional)
        variance_threshold: Drop features where var < this (default 0.5%)
        corr_threshold:     Drop one of any pair with |r| > this (default 0.95)
        importance_gate:    Drop features with importance < gate/n_features

    Returns:
        List of selected feature column names.
    """
    original_n = len(X.columns)
    keep = list(X.columns)

    # Stage 1: Variance threshold
    vars_ = X[keep].var()
    keep = [c for c in keep if vars_.get(c, 0) >= variance_threshold]
    log.info(f"Feature selection — Stage 1 (variance): {original_n} → {len(keep)} features")

    # Stage 2: Correlation deduplication
    if len(keep) > 1:
        corr = X[keep].corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        # For each highly correlated pair, drop the one with lower variance
        drop_corr = set()
        for col in upper.columns:
            partners = upper.index[upper[col] > corr_threshold].tolist()
            for partner in partners:
                # Keep the one with higher variance
                if vars_.get(col, 0) < vars_.get(partner, 0):
                    drop_corr.add(col)
                else:
                    drop_corr.add(partner)
        keep = [c for c in keep if c not in drop_corr]
        log.info(f"Feature selection — Stage 2 (correlation): → {len(keep)} features "
                 f"(dropped {len(drop_corr)} correlated)")

    # Stage 3: Importance gate (requires RF importance)
    if importance_dict and len(importance_dict) > 0:
        threshold = importance_gate / len(importance_dict)
        keep_imp = [c for c in keep
                    if importance_dict.get(c, 0) >= threshold]
        if len(keep_imp) >= 10:   # safety: never drop below 10 features
            dropped = len(keep) - len(keep_imp)
            keep = keep_imp
            log.info(f"Feature selection — Stage 3 (importance): → {len(keep)} features "
                     f"(dropped {dropped} low-importance)")
        else:
            log.info(f"Feature selection — Stage 3 skipped (would drop too many; "
                     f"keeping {len(keep)})")

    log.info(f"Feature selection complete: {original_n} → {len(keep)} features selected")
    return keep


def get_feature_selection_report(X: pd.DataFrame, importance_dict: dict = None) -> pd.DataFrame:
    """
    Returns a DataFrame showing why each feature was kept or dropped.
    Useful for the dashboard feature importance section.
    """
    rows = []
    vars_ = X.var()

    for col in X.columns:
        var = vars_.get(col, 0)
        imp = importance_dict.get(col, np.nan) if importance_dict else np.nan

        # Correlation: find highest correlated partner
        others = [c for c in X.columns if c != col]
        if others:
            max_corr = X[[col] + others].corr()[col].drop(col).abs().max()
        else:
            max_corr = 0.0

        status = "KEEP"
        reason = "—"
        if var < 0.005:
            status = "DROP"; reason = f"low variance ({var:.4f})"
        elif max_corr > 0.95:
            status = "REVIEW"; reason = f"high correlation ({max_corr:.2f})"
        elif not np.isnan(imp) and imp < 0.40 / len(X.columns):
            status = "DROP"; reason = f"low importance ({imp:.4f})"

        rows.append({
            "feature":     col,
            "variance":    round(var, 5),
            "max_corr":    round(max_corr, 3),
            "importance":  round(imp, 5) if not np.isnan(imp) else "—",
            "status":      status,
            "reason":      reason,
        })

    return pd.DataFrame(rows).sort_values("importance", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_features(price_df, fundamentals=None, macro_df=None,
                   options_dict=None, horizons=None):
    """
    Builds all feature families for one ticker.

    Args:
        price_df:     OHLCV DataFrame (yfinance format)
        fundamentals: dict from fetch_fundamentals()
        macro_df:     macro DataFrame from fetch_macro_data()
        options_dict: dict from options_scraper.fetch_options_features()  ← NEW
        horizons:     list of prediction horizons in days

    Returns:
        DataFrame with all features + target columns.
    """
    if horizons is None:
        horizons = [5, 21, 63]
    df = price_df.copy()
    df = add_price_features(df)
    df = add_volume_features(df)
    df = add_technical_features(df)
    if fundamentals:
        df = add_fundamental_features(df, fundamentals)
    if macro_df is not None:
        df = add_macro_features(df, macro_df)
    if options_dict:
        df = add_options_features(df, options_dict)
    df = add_target(df, horizons=horizons)

    # Bug fix (2026-08-20): this row-completeness check used to count ALL feature
    # columns together, including 'fund_*'/'opt_*'/'macro_*' — ticker-level
    # constants broadcast identically to every row. A ticker missing two optional
    # families at once (e.g. no fundamentals AND no options coverage) could
    # exceed the 20% threshold on EVERY row purely from that broadcast pattern,
    # wiping its entire history before run_ml_pipeline.py's per-column handling
    # ever got a chance to run. Now this check only looks at CORE (price/volume/
    # technical) columns, where a NaN genuinely reflects a bad observation (e.g.
    # too early in the series for a rolling window). Optional-family coverage
    # gaps are handled downstream in run_ml_pipeline.py::drop_uncovered_optional_columns
    # by dropping the column for that ticker, not the row.
    core_prefixes = (
        "ret_", "log_ret_", "vol_", "price_vs_ma", "dist_52w_", "gap_pct",
        "rel_volume", "volume_trend", "obv_zscore", "vol_price_div_",
        "rsi_", "macd_", "bb_position", "atr_norm", "stoch_k",
    )
    core_cols = [c for c in df.columns
                 if not c.startswith(("target_", "future_")) and c.startswith(core_prefixes)]
    if core_cols:
        df = df[df[core_cols].isnull().mean(axis=1) <= 0.20].copy()
    return df
