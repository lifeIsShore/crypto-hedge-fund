"""feature_builder.py — All feature families + automatic feature selection.

Feature families for Crypto:
  1. Price (returns, momentum distances, gap)
  2. Volume (OBV, relative volume, divergence signals)
  3. Technical (RSI, MACD, Bollinger, ATR, Stochastic)
  4. Cross-sectional (Rank against crypto universe)
  5. Acceleration (Momentum of momentum)

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
# CORE FEATURE FAMILIES
# ─────────────────────────────────────────────────────────────────────────────

def add_price_features(df):
    if "adj_close" in df.columns:
        c = df["adj_close"]
    elif "Adj Close" in df.columns:
        c = df["Adj Close"]
    else:
        c = df["close"]
        
    for n in [1, 5, 10, 21, 63]:
        df[f"ret_{n}d"] = c.pct_change(n)
    df["log_ret_1d"] = np.log(c / c.shift(1))
    
    # 365 days for crypto annualisation
    for w in [21, 63]:
        df[f"vol_{w}d"] = df["log_ret_1d"].rolling(w).std() * np.sqrt(365)
    df["var_21d"] = df["log_ret_1d"].rolling(21).quantile(0.05)
    
    for ma in [50, 200]:
        ma_s = c.rolling(ma).mean()
        df[f"price_vs_ma{ma}"] = (c - ma_s) / ma_s
        
    # 365 for crypto 52-week equivalent
    df["dist_52w_high"] = (c - c.rolling(365).max()) / c.rolling(365).max()
    df["dist_52w_low"]  = (c - c.rolling(365).min()) / c.rolling(365).min()
    
    open_col = "open" if "open" in df.columns else "Open"
    close_col = "close" if "close" in df.columns else "Close"
    df["gap_pct"] = (df[open_col] - df[close_col].shift(1)) / df[close_col].shift(1)
    return df


def add_volume_features(df):
    vol_col = "volume" if "volume" in df.columns else "Volume"
    close_col = "close" if "close" in df.columns else "Close"
    
    v = df[vol_col].replace(0, np.nan)
    df["rel_volume"]   = v / v.rolling(21).mean()
    df["volume_trend"] = v.rolling(5).mean() / v.rolling(21).mean()
    obv = (v * np.sign(df[close_col].diff())).fillna(0).cumsum()
    df["obv_zscore"] = (obv - obv.rolling(63).mean()) / (obv.rolling(63).std() + 1e-9)
    ret = df[close_col].pct_change()
    df["vol_price_div_up"]   = ((ret > 0) & (v < v.rolling(5).mean())).astype(int)
    df["vol_price_div_down"] = ((ret < 0) & (v > v.rolling(5).mean())).astype(int)
    return df


def add_technical_features(df):
    close_col = "close" if "close" in df.columns else "Close"
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"
    
    c, h, l = df[close_col], df[high_col], df[low_col]
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    ema12  = c.ewm(span=12, adjust=False).mean()
    ema26  = c.ewm(span=26, adjust=False).mean()
    macd_raw   = ema12 - ema26
    signal_raw = macd_raw.ewm(span=9, adjust=False).mean()
    
    df["macd_pct"]        = macd_raw / (ema26 + 1e-9)
    df["macd_hist_pct"]   = (macd_raw - signal_raw) / (ema26 + 1e-9)
    df["macd_signal_pct"] = signal_raw / (ema26 + 1e-9)
    
    ma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_position"] = (c - (ma20 - 2 * std20)) / (4 * std20 + 1e-9)
    
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr_norm"] = tr.rolling(14).mean() / c
    df["stoch_k"] = (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min() + 1e-9)
    return df


def add_macro_features(df, macro):
    aligned = macro.reindex(df.index, method="ffill", limit=5)
    for col in aligned.columns:
        df[f"macro_{col}"] = aligned[col].values
    return df

# ─────────────────────────────────────────────────────────────────────────────
# DB REGIME (Can be left in case we have crypto DB regimes)
# ─────────────────────────────────────────────────────────────────────────────

DB_REGIME_FEATURE_NAMES = [
    'stress_score', 'macro_vix', 'macro_risk_on', 'macro_risk_off',
    'macro_yield_spread', 'macro_hy_spread', 'macro_easing',
    'macro_tightening', 'macro_expansion', 'macro_slowdown',
    'macro_contraction', 'macro_ew_transition', 'macro_ew_count',
    'macro_streak_days',
]

def add_db_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    import sqlite3
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.normpath(os.path.join(here, '..', '..', '..', '..', 'engine_data.db'))

    if not os.path.exists(db_path):
        return df

    placeholders = ','.join([f'"{f}"' for f in DB_REGIME_FEATURE_NAMES])

    try:
        conn = sqlite3.connect(db_path)
        query = f"""
            SELECT date, feature_name, feature_value
            FROM feature_store
            WHERE ticker = '_PORTFOLIO'
              AND feature_name IN ({placeholders})
            ORDER BY date ASC
        """
        raw = pd.read_sql(query, conn, parse_dates=['date'])
        conn.close()
    except Exception as e:
        log.warning(f"[DB regime] DB read failed: {e} — skipping")
        return df

    if raw.empty:
        return df

    regime_wide = raw.pivot(index='date', columns='feature_name', values='feature_value')
    regime_wide.columns = [f'db_{c}' for c in regime_wide.columns]
    regime_wide = regime_wide.sort_index().ffill(limit=5)
    regime_wide = regime_wide.shift(1)
    aligned = regime_wide.reindex(df.index, method='ffill', limit=5)
    df = df.join(aligned, how='left')
    return df


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-SECTIONAL & ACCELERATION
# ─────────────────────────────────────────────────────────────────────────────

def get_universe_snapshot(prices_dict: dict, date: pd.Timestamp,
                          max_stale_days: int = 5) -> list:
    valid = []
    for ticker, df in prices_dict.items():
        if date not in df.index:
            continue
        subset = df.loc[:date].tail(max_stale_days)
        price_col = 'adj_close' if 'adj_close' in df.columns else 'Adj Close'
        if price_col not in df.columns: price_col = 'close'
        if price_col in df.columns and subset[price_col].notna().any():
            valid.append(ticker)
    return valid

CROSSSECTIONAL_WINDOWS = [5, 21, 63]

def add_crosssectional_features(df: pd.DataFrame, ticker: str,
                                cs_cache: dict) -> pd.DataFrame:
    if cs_cache is None:
        return df
    for k, matrix in cs_cache.items():
        if ticker in matrix.columns:
            df[k] = matrix[ticker].reindex(df.index).values
        else:
            df[k] = np.nan
    return df


def add_acceleration_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df['adj_close'] if 'adj_close' in df.columns else df['Adj Close'] if 'Adj Close' in df.columns else df['close']
    
    ret_5d  = c.pct_change(5)
    ret_21d = c.pct_change(21)
    ret_63d = c.pct_change(63)
    
    df['ret_accel_1m'] = ret_5d / ret_21d.replace(0, np.nan)
    df['ret_accel_3m'] = ret_21d / ret_63d.replace(0, np.nan)
    df['ret_accel_1m'] = df['ret_accel_1m'].clip(-5, 5)
    df['ret_accel_3m'] = df['ret_accel_3m'].clip(-5, 5)
    
    lr = np.log(c / c.shift(1))
    vol_21 = lr.rolling(21).std() * np.sqrt(365)
    vol_63 = lr.rolling(63).std() * np.sqrt(365)
    df['vol_regime'] = vol_21 / vol_63.replace(0, np.nan)
    
    ma20  = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df['bb_width'] = (4 * std20) / ma20.replace(0, np.nan)
    
    if 'rsi_14' in df.columns:
        df['rsi_momentum'] = df['rsi_14'] - df['rsi_14'].shift(5)
    
    return df


def add_target(df, horizons=None, benchmark_df=None, enable_alpha_target=False):
    if horizons is None:
        horizons = [5, 21, 63]
    c = df['adj_close'] if 'adj_close' in df.columns else df['Adj Close'] if 'Adj Close' in df.columns else df['close']
    
    if enable_alpha_target and benchmark_df is not None:
        bench_c = benchmark_df['adj_close'] if 'adj_close' in benchmark_df.columns else benchmark_df['Adj Close'] if 'Adj Close' in benchmark_df.columns else benchmark_df['close']
        bench_c = bench_c.reindex(df.index, method='ffill')
        
    for n in horizons:
        fut = c.shift(-n) / c - 1
        df[f"future_ret_{n}d"]  = fut
        
        if enable_alpha_target and benchmark_df is not None:
            bench_fut = bench_c.shift(-n) / bench_c - 1
            excess_fut = fut - bench_fut
            df[f"target_dir_{n}d"]  = (excess_fut > 0).astype(int)
            bins = [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf]
            df[f"target_mag_{n}d"]  = pd.cut(excess_fut, bins=bins, labels=[0, 1, 2, 3, 4]).astype("Int64")
        else:
            df[f"target_dir_{n}d"]  = (fut > 0).astype(int)
            bins = [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf]
            df[f"target_mag_{n}d"]  = pd.cut(fut, bins=bins, labels=[0, 1, 2, 3, 4]).astype("Int64")
            
    return df


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE SELECTION
# ─────────────────────────────────────────────────────────────────────────────

def select_features(X: pd.DataFrame, importance_dict: dict = None,
                    variance_threshold: float = 0.005,
                    corr_threshold: float = 0.95,
                    importance_gate: float = 0.40) -> list:
    original_n = len(X.columns)
    keep = list(X.columns)
    vars_ = X[keep].var()
    keep = [c for c in keep if vars_.get(c, 0) >= variance_threshold]

    if len(keep) > 1:
        corr = X[keep].corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        drop_corr = set()
        for col in upper.columns:
            partners = upper.index[upper[col] > corr_threshold].tolist()
            for partner in partners:
                if vars_.get(col, 0) < vars_.get(partner, 0):
                    drop_corr.add(col)
                else:
                    drop_corr.add(partner)
        keep = [c for c in keep if c not in drop_corr]

    if importance_dict and len(importance_dict) > 0:
        threshold = importance_gate / len(importance_dict)
        keep_imp = [c for c in keep
                    if importance_dict.get(c, 0) >= threshold]
        if len(keep_imp) >= 10:
            keep = keep_imp

    return keep

def get_feature_selection_report(X: pd.DataFrame, importance_dict: dict = None) -> pd.DataFrame:
    rows = []
    vars_ = X.var()

    for col in X.columns:
        var = vars_.get(col, 0)
        imp = importance_dict.get(col, np.nan) if importance_dict else np.nan
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
                   options_dict=None, horizons=None,
                   ticker=None,
                   cs_cache=None,
                   enable_db_regime=False,
                   enable_pead=False,
                   enable_earnings=False,
                   enable_crosssectional=False,
                   enable_acceleration=False,
                   benchmark_df=None,
                   enable_alpha_target=False,
                   sv_features_df=None):
    
    if horizons is None:
        horizons = [5, 21, 63]
    df = price_df.copy()
    df = add_price_features(df)
    df = add_volume_features(df)
    df = add_technical_features(df)
    
    if macro_df is not None:
        df = add_macro_features(df, macro_df)
    if enable_db_regime:
        df = add_db_regime_features(df)
    if enable_crosssectional:
        if not ticker:
            log.warning("[Cross-sectional] enable_crosssectional=True but no ticker passed — skipping")
        else:
            df = add_crosssectional_features(df, ticker, cs_cache)
    if enable_acceleration:
        df = add_acceleration_features(df)
        
    df = add_target(df, horizons=horizons, benchmark_df=benchmark_df, enable_alpha_target=enable_alpha_target)

    core_prefixes = (
        "ret_", "log_ret_", "vol_", "var_", "price_vs_ma", "dist_52w_", "gap_pct",
        "rel_volume", "volume_trend", "obv_zscore", "vol_price_div_",
        "rsi_", "macd_", "bb_position", "atr_norm", "stoch_k",
    )
    core_cols = [c for c in df.columns
                 if not c.startswith(("target_", "future_")) and c.startswith(core_prefixes)]
    if core_cols:
        df = df[df[core_cols].isnull().mean(axis=1) <= 0.20].copy()
    return df
