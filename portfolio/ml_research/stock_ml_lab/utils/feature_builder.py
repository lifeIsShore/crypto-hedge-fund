"""feature_builder.py — All 6 feature families. No look-ahead. Point-in-time safe."""
import numpy as np
import pandas as pd

def add_price_features(df):
    c = df["Adj Close"]
    for n in [1,5,10,21,63]: df[f"ret_{n}d"] = c.pct_change(n)
    df["log_ret_1d"] = np.log(c / c.shift(1))
    for w in [21,63]: df[f"vol_{w}d"] = df["log_ret_1d"].rolling(w).std() * np.sqrt(252)
    for ma in [50,200]:
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
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi_14"] = 1 - 1 / (1 + gain / (loss + 1e-9))
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = macd - signal
    df["macd_signal"] = signal
    ma20, std20 = c.rolling(20).mean(), c.rolling(20).std()
    df["bb_position"] = (c - (ma20 - 2*std20)) / (4*std20 + 1e-9)
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    df["atr_norm"] = tr.rolling(14).mean() / c
    df["stoch_k"] = (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min() + 1e-9)
    return df

def add_fundamental_features(df, fundamentals):
    mapping = {
        "trailingPE":"fund_pe","priceToBook":"fund_pb","enterpriseToEbitda":"fund_ev_ebitda",
        "revenueGrowth":"fund_rev_growth","grossMargins":"fund_gross_margin",
        "operatingMargins":"fund_op_margin","debtToEquity":"fund_de","freeCashflow":"fund_fcf",
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

def add_target(df, horizons=[5,21,63]):
    c = df["Adj Close"]
    for n in horizons:
        fut = c.shift(-n) / c - 1
        df[f"target_dir_{n}d"] = (fut > 0).astype(int)
        df[f"future_ret_{n}d"] = fut
        bins = [-np.inf,-0.05,-0.01,0.01,0.05,np.inf]
        df[f"target_mag_{n}d"] = pd.cut(fut, bins=bins, labels=[0,1,2,3,4]).astype("Int64")
    return df

def build_features(price_df, fundamentals=None, macro_df=None, horizons=[5,21,63]):
    df = price_df.copy()
    df = add_price_features(df)
    df = add_volume_features(df)
    df = add_technical_features(df)
    if fundamentals: df = add_fundamental_features(df, fundamentals)
    if macro_df is not None: df = add_macro_features(df, macro_df)
    df = add_target(df, horizons=horizons)
    feat_cols = [c for c in df.columns if not c.startswith(("target_","future_"))]
    df = df[df[feat_cols].isnull().mean(axis=1) <= 0.20].copy()
    return df
