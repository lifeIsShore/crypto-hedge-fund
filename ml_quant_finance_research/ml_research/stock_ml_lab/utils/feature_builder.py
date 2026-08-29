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
    df["var_21d"] = df["log_ret_1d"].rolling(21).quantile(0.05)
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
    macd_raw   = ema12 - ema26
    signal_raw = macd_raw.ewm(span=9, adjust=False).mean()
    
    # STATIONARY MACD: Convert absolute dollars to percentages
    df["macd_pct"]        = macd_raw / (ema26 + 1e-9)
    df["macd_hist_pct"]   = (macd_raw - signal_raw) / (ema26 + 1e-9)
    df["macd_signal_pct"] = signal_raw / (ema26 + 1e-9)
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


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1A — DB-bridged signals (better-alpha/01-feature-additions.md §A)
# All three functions below are additive: they return df unchanged (or with
# NaN-filled columns) on any failure path, never raise, and never drop rows
# themselves. Row-level survival for these OPTIONAL families is handled by
# run_ml_pipeline.py::drop_uncovered_optional_columns, same as fund_/opt_.
# ─────────────────────────────────────────────────────────────────────────────

DB_REGIME_FEATURE_NAMES = [
    'stress_score', 'macro_vix', 'macro_risk_on', 'macro_risk_off',
    'macro_yield_spread', 'macro_hy_spread', 'macro_easing',
    'macro_tightening', 'macro_expansion', 'macro_slowdown',
    'macro_contraction', 'macro_ew_transition', 'macro_ew_count',
    'macro_streak_days',
]


def add_db_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds production engine regime features (engine_data.db, feature_store,
    ticker='_PORTFOLIO') to the ML feature DataFrame.

    LOOKAHEAD PROTECTION: features are aligned with a 1-day lag (feature
    date t-1 used for training row at date t) — matches production timing.

    HOLDOUT PROTECTION: this function does NOT filter df.index to
    pre-holdout dates. The caller (run_ml_pipeline.py) is responsible for
    filtering to date < HOLDOUT_START before this function is invoked,
    per better-alpha/holdout_config.txt. This function only reindexes onto
    whatever dates it's given.

    Column prefix: 'db_' — see OPTIONAL_FEATURE_PREFIXES in
    run_ml_pipeline.py for why: a ticker with no DB access should lose
    these columns, not its entire row history.
    """
    import sqlite3
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.normpath(os.path.join(here, '..', '..', '..', '..', 'engine_data.db'))

    if not os.path.exists(db_path):
        log.warning(f"[DB regime] engine_data.db not found at {db_path} — skipping")
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
        log.warning("[DB regime] No portfolio features found in feature_store")
        return df

    regime_wide = raw.pivot(index='date', columns='feature_name', values='feature_value')
    regime_wide.columns = [f'db_{c}' for c in regime_wide.columns]
    regime_wide = regime_wide.sort_index().ffill(limit=5)

    # ── CRITICAL: 1-day lag to prevent lookahead ────────────────────────────
    regime_wide = regime_wide.shift(1)

    aligned = regime_wide.reindex(df.index, method='ffill', limit=5)

    n_before = len(df.columns)
    df = df.join(aligned, how='left')
    n_added = len(df.columns) - n_before
    log.info(f"[DB regime] Added {n_added} regime features from production DB")
    return df


def add_pead_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Adds PEAD-based features from shared/state/pead_setups.csv — the actual
    production source (engine/alpha/pead_alpha.py reads this same file; the
    `pead_setups` DB table in schema.sql is dead, nothing writes to it).

      db_pead_surprise_pct  — EPS surprise % from the most recent setup
      db_pead_days_since    — calendar days since that setup's entry_date
      db_pead_in_window     — 1 if 0 < days_since < 63 (drift window), else 0
      db_pead_underreaction — 1 if the PEAD engine flagged underreaction
      db_pead_quality_score — pead_setup_quality mapped to an ordinal
                              (High=3, Medium=2, Low=1, Disqualified=0)

    LEAKAGE NOTE: pead_setups.csv also has drift_21d, drift_63d, and
    outcome_label_correct — these are the ACTUAL FORWARD RETURN OUTCOMES
    (pead_engine/screener.py::_price_return, computed looking forward from
    entry_date). They are deliberately never read here. Using them would
    not be a subtle leak, it would be training on the label.

    LOOKAHEAD PROTECTION: a row at date t uses the most recent setup with
    entry_date < t only (merge_asof, backward direction).
    """
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.normpath(os.path.join(
        here, '..', '..', '..', '..', 'shared', 'state', 'pead_setups.csv'
    ))

    for col in ('db_pead_surprise_pct', 'db_pead_days_since', 'db_pead_in_window',
                'db_pead_underreaction', 'db_pead_quality_score'):
        df[col] = np.nan

    if not os.path.exists(csv_path):
        log.warning(f"[PEAD] pead_setups.csv not found at {csv_path} — skipping")
        return df

    try:
        raw = pd.read_csv(csv_path, parse_dates=['entry_date'])
    except Exception as e:
        log.warning(f"[PEAD] CSV read failed: {e} — skipping")
        return df

    raw = raw[raw['ticker'] == ticker].copy()
    raw = raw.dropna(subset=['entry_date']).sort_values('entry_date')
    if raw.empty:
        return df

    quality_map = {'High': 3, 'Medium': 2, 'Low': 1, 'Disqualified': 0}
    raw['quality_score'] = raw['pead_setup_quality'].map(quality_map)
    raw['underreaction_num'] = raw['underreaction_flag'].astype(bool).astype(float)

    keep_cols = ['entry_date', 'surprise_pct', 'quality_score', 'underreaction_num']
    raw = raw[keep_cols].drop_duplicates(subset=['entry_date'], keep='last')

    dates = df.index.to_series().rename('row_date').reset_index(drop=True)
    merged = pd.merge_asof(
        dates.sort_values().to_frame(), raw,
        left_on='row_date', right_on='entry_date',
        direction='backward', allow_exact_matches=False,
    ).set_index('row_date').reindex(dates.values)
    merged.index = df.index

    days_since = (df.index.to_series() - merged['entry_date']).dt.days
    in_window = ((days_since > 0) & (days_since < 63)).astype(float)
    in_window[days_since.isna()] = np.nan

    df['db_pead_surprise_pct']  = merged['surprise_pct'].values
    df['db_pead_days_since']    = days_since.values
    df['db_pead_in_window']     = in_window.values
    df['db_pead_underreaction'] = merged['underreaction_num'].values
    df['db_pead_quality_score'] = merged['quality_score'].values

    return df


def add_earnings_calendar_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Adds forward-looking earnings-calendar features from the earnings_calendar
    DB table (real columns: ticker, report_date, report_time, eps_estimate,
    revenue_estimate — there is no 'confirmed' column; Finnhub's calendar
    endpoint returns a rolling ~30-day-forward estimate that gets overwritten
    in place via ON CONFLICT as dates firm up. See engine/data/earnings_calendar.py).

      db_days_to_earnings    — trading days until next scheduled report
                                (NaN if none found in next 90 days)
      db_pre_earnings_window — 1 if within 5 trading days of next report

    LOOKAHEAD CAVEAT: rows are overwritten as Finnhub's estimate changes
    (dates sometimes move), and there is no way to reconstruct what was
    known as of a historical row's date — this always uses whatever is in
    the table right now. For dates before HOLDOUT_START this is a mild,
    accepted approximation (same category as Risk C in 00-OVERVIEW.md); it
    is NOT valid for precise backtesting of pre-earnings timing strategies.
    """
    import sqlite3
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.normpath(os.path.join(here, '..', '..', '..', '..', 'engine_data.db'))

    df['db_days_to_earnings'] = np.nan
    df['db_pre_earnings_window'] = np.nan

    if not os.path.exists(db_path):
        log.warning(f"[Earnings] engine_data.db not found at {db_path} — skipping")
        return df

    try:
        conn = sqlite3.connect(db_path)
        raw = pd.read_sql(
            "SELECT report_date FROM earnings_calendar WHERE ticker = ? ORDER BY report_date ASC",
            conn, params=(ticker,), parse_dates=['report_date'],
        )
        conn.close()
    except Exception as e:
        log.warning(f"[Earnings] DB read failed for {ticker}: {e} — skipping")
        return df

    if raw.empty:
        return df

    expected_dates = raw['report_date'].sort_values().values
    row_dates = df.index.to_series()

    def next_report_calendar_days(t):
        future = expected_dates[expected_dates > np.datetime64(t)]
        if len(future) == 0:
            return np.nan
        return (pd.Timestamp(future[0]) - t).days

    calendar_days_to = row_dates.apply(next_report_calendar_days)
    # Approximate trading days from calendar days (5/7 ratio); good enough
    # for a "within N days" style feature, not used for precise scheduling.
    trading_days_to = (calendar_days_to * (5.0 / 7.0)).round()
    trading_days_to = trading_days_to.where(trading_days_to <= 90, np.nan)

    df['db_days_to_earnings'] = trading_days_to.values
    df['db_pre_earnings_window'] = (trading_days_to <= 5).astype(float).where(
        trading_days_to.notna(), np.nan
    ).values

    return df

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1B — Cross-sectional features + price acceleration
# ─────────────────────────────────────────────────────────────────────────────

def get_universe_snapshot(prices_dict: dict, date: pd.Timestamp,
                          max_stale_days: int = 5) -> list:
    """
    Returns list of tickers that had valid (non-stale) prices on the given date.
    A ticker is valid if it has at least one non-NaN price in the 5 trading days
    up to and including date.
    """
    valid = []
    for ticker, df in prices_dict.items():
        if date not in df.index:
            continue
        # Last 5 rows up to date
        subset = df.loc[:date].tail(max_stale_days)
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        if price_col in df.columns and subset[price_col].notna().any():
            valid.append(ticker)
    return valid


CROSSSECTIONAL_WINDOWS = [5, 21, 63]

def add_crosssectional_features(df: pd.DataFrame, ticker: str,
                                cs_cache: dict) -> pd.DataFrame:
    """
    Adds precomputed cross-sectional ranks across the universe.
    
    Features:
      cs_ret_{n}d_rank    — percentile rank of this ticker's n-day return
      cs_vol_21d_rank     — percentile rank of this ticker's 21d realised vol
    """
    if cs_cache is None:
        log.warning("[Cross-sectional] cs_cache is None, skipping.")
        return df

    for k, matrix in cs_cache.items():
        if ticker in matrix.columns:
            # Align the ticker's column from the matrix to the current df.index
            df[k] = matrix[ticker].reindex(df.index).values
        else:
            df[k] = np.nan
    return df


def add_acceleration_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Momentum acceleration: is the momentum speeding up or slowing down?
    
    Features:
      ret_accel_1m    = ret_5d / ret_21d
      ret_accel_3m    = ret_21d / ret_63d
      vol_regime      = vol_21d / vol_63d
      bb_width        = (bb_upper - bb_lower) / bb_mid
      rsi_momentum    = rsi_14 - rsi_14.shift(5)
    """
    c = df['Adj Close']
    
    # Price-based acceleration
    ret_5d  = c.pct_change(5)
    ret_21d = c.pct_change(21)
    ret_63d = c.pct_change(63)
    
    df['ret_accel_1m'] = ret_5d / ret_21d.replace(0, np.nan)
    df['ret_accel_3m'] = ret_21d / ret_63d.replace(0, np.nan)
    
    # Clip extremes: acceleration > 5x or < -5x is likely noise/data error
    df['ret_accel_1m'] = df['ret_accel_1m'].clip(-5, 5)
    df['ret_accel_3m'] = df['ret_accel_3m'].clip(-5, 5)
    
    # Vol regime
    lr = np.log(c / c.shift(1))
    vol_21 = lr.rolling(21).std() * np.sqrt(252)
    vol_63 = lr.rolling(63).std() * np.sqrt(252)
    df['vol_regime'] = vol_21 / vol_63.replace(0, np.nan)
    
    # Bollinger Band width (requires bb_position already computed)
    ma20  = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df['bb_width'] = (4 * std20) / ma20.replace(0, np.nan)   # (upper - lower) / mid = 4σ / mid
    
    # RSI momentum
    if 'rsi_14' in df.columns:
        df['rsi_momentum'] = df['rsi_14'] - df['rsi_14'].shift(5)
    
    return df


def add_target(df, horizons=None, benchmark_df=None, enable_alpha_target=False):
    if horizons is None:
        horizons = [5, 21, 63]
    c = df["Adj Close"]
    
    if enable_alpha_target and benchmark_df is not None:
        bench_c = benchmark_df["Adj Close"].reindex(df.index, method='ffill')
        
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
                   options_dict=None, horizons=None,
                   ticker=None,                          # NEW — Phase 1A
                   cs_cache=None,                        # NEW — Phase 1B
                   enable_db_regime=False,                # NEW — Phase 1A
                   enable_pead=False,                      # NEW — Phase 1A
                   enable_earnings=False,                  # NEW — Phase 1A
                   enable_crosssectional=False,            # NEW — Phase 1B
                   enable_acceleration=False,              # NEW — Phase 1B
                   benchmark_df=None,                      # NEW — Phase 1D
                   enable_alpha_target=False):             # NEW — Phase 1D
    """
    Builds all feature families for one ticker.

    Args:
        price_df:     OHLCV DataFrame (yfinance format)
        fundamentals: dict from fetch_fundamentals()
        macro_df:     macro DataFrame from fetch_macro_data()
        options_dict: dict from options_scraper.fetch_options_features()  ← NEW
        horizons:     list of prediction horizons in days
        ticker:              current ticker symbol; required if enable_pead
                             or enable_earnings is True.                    ← Phase 1A
        cs_cache:            precomputed cross-sectional matrices           ← Phase 1B
        enable_db_regime:    if True, calls add_db_regime_features().       ← Phase 1A
        enable_pead:         if True, calls add_pead_features(). Requires
                             ticker to be set.                              ← Phase 1A
        enable_earnings:     if True, calls add_earnings_calendar_features().
                             Requires ticker to be set.                     ← Phase 1A
        enable_crosssectional: if True, calls add_crosssectional_features() ← Phase 1B
        enable_acceleration:   if True, calls add_acceleration_features()   ← Phase 1B

    Returns:
        DataFrame with all features + target columns.

    All Phase 1A/B flags default to False, preserving exact prior behaviour
    (baseline_v1) when the caller passes none of them. See
    before-go-live/better-alpha/01-feature-additions.md.
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
    if enable_db_regime:
        df = add_db_regime_features(df)
    if enable_pead:
        if not ticker:
            log.warning("[PEAD] enable_pead=True but no ticker passed — skipping")
        else:
            df = add_pead_features(df, ticker)
    if enable_earnings:
        if not ticker:
            log.warning("[Earnings] enable_earnings=True but no ticker passed — skipping")
        else:
            df = add_earnings_calendar_features(df, ticker)
    if enable_crosssectional:
        if not ticker:
            log.warning("[Cross-sectional] enable_crosssectional=True but no ticker passed — skipping")
        else:
            df = add_crosssectional_features(df, ticker, cs_cache)
    if enable_acceleration:
        df = add_acceleration_features(df)
        
    df = add_target(df, horizons=horizons, benchmark_df=benchmark_df, enable_alpha_target=enable_alpha_target)

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
        "ret_", "log_ret_", "vol_", "var_", "price_vs_ma", "dist_52w_", "gap_pct",
        "rel_volume", "volume_trend", "obv_zscore", "vol_price_div_",
        "rsi_", "macd_", "bb_position", "atr_norm", "stoch_k",
    )
    core_cols = [c for c in df.columns
                 if not c.startswith(("target_", "future_")) and c.startswith(core_prefixes)]
    if core_cols:
        df = df[df[core_cols].isnull().mean(axis=1) <= 0.20].copy()
    return df
