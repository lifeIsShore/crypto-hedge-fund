> **STATUS (2026-08-09, verified by Claude): NOT IMPLEMENTED.** Checked `engine/features/feature_store.py` directly — it still computes exactly the original 8 features (mom_1m/3m/6m/12m, vol_21d/63d, vol_of_vol, rsi_14). None of the 16 new features below exist in the live code. This doc was archived without the work being done. Moved back here as genuinely open.
>
> Note: the trailing "institutional-grade" section that used to be pasted at the bottom of this file (covering scheduler conflicts, unverified execution modules, missing risk policy, liquidity gating) was stray AI-generated meta-content from an unrelated editing session — it's been removed from this file since it wasn't about feature expansion at all. For the record: the dual-scheduler issue it described is already fixed (see PROJECT-STATE.md, 2026-08-04 entry), the liquidity gating item is already fixed (PROJECT-STATE.md, 2026-08-09 entry), and the risk-policy/unverified-execution items are tracked separately in RISK-POLICY.md and PROJECT-STATE.md §7b — not duplicated here.

# Feature Expansion: 8 → 24 Features
# Add to `engine/features/feature_store.py`
# Estimated time: 1 day. Immediate impact on all alpha models.

---

## Why this matters

Your alpha models (Momentum, MeanReversion, VolTiming, LSTM) read from the
`feature_store` table. The LSTM specifically uses this exact list:

```python
FEATURE_NAMES = [
    'mom_1m', 'mom_3m', 'mom_6m', 'mom_12m',
    'vol_21d', 'vol_63d', 'vol_of_vol',
    'rsi_14',
]
```

8 features for 130 tickers across 16 sectors. Every model is working with
the same thin slice of information. Adding 16 more well-chosen features
immediately improves the LSTM's predictive ability, adds new raw_scores for
the mean-reversion and momentum models, and gives the Black-Litterman optimizer
a richer signal set to work with.

All features below are computed purely from `prices` data already in your DB.
No new API calls required. No new dependencies beyond what's installed.

---

## New functions to add to `feature_store.py`

### 1. `compute_extended_momentum_features(prices)` — 3 new features

Fills the gaps in your current momentum ladder:

```python
def compute_extended_momentum_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Extends existing momentum with:
      mom_1w   : 5-day momentum rank (short-term reversal capture)
      mom_9m   : 189-day momentum rank (fills the 6m-12m gap)
      mom_ret_to_52w_high : price / 52-week high, cross-sectionally ranked
    """
    skip = 21
    features = {}

    # 1-week momentum (NO skip — we want the very short-term reversal signal)
    if len(prices) >= 5:
        raw = prices / prices.shift(5) - 1
        latest = raw.iloc[-1].dropna()
        features['mom_1w'] = latest.rank(pct=True)

    # 9-month momentum (with 21-day skip)
    if len(prices) >= 189 + skip:
        raw = prices.shift(skip) / prices.shift(189 + skip) - 1
        latest = raw.iloc[-1].dropna()
        features['mom_9m'] = latest.rank(pct=True)

    # Price distance from 52-week high — strong documented predictor
    # Stocks near their 52w high tend to outperform (nearness = investor anchoring)
    if len(prices) >= 252:
        high_52w = prices.tail(252).max()
        latest_price = prices.iloc[-1]
        ratio = latest_price / high_52w.replace(0, np.nan)
        features['price_to_52w_high'] = ratio.rank(pct=True)  # cross-sectional rank

    if not features:
        return pd.DataFrame()
    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result
```

---

### 2. `compute_extended_technical_features(prices, log_returns)` — 6 new features

```python
def compute_extended_technical_features(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    RSI(21), Bollinger Band width, ATR(14), rolling beta vs benchmark,
    return skewness, and vol-adjusted momentum (Sharpe-like signal).
    """
    features = {}

    # RSI(21) — medium-term RSI complements RSI(14)
    rsi21_vals = {}
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 30:
            continue
        delta = series.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/21, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/21, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        rsi21_vals[ticker] = float(rsi.iloc[-1])
    if rsi21_vals:
        features['rsi_21'] = pd.Series(rsi21_vals)

    # Bollinger Band width — measures volatility compression
    # Compression (low bb_width) often precedes directional breakouts
    bb_vals = {}
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 20:
            continue
        mid   = series.rolling(20).mean()
        std   = series.rolling(20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        bb_width = (upper - lower) / mid.replace(0, np.nan)
        bb_vals[ticker] = float(bb_width.iloc[-1]) if not pd.isna(bb_width.iloc[-1]) else np.nan
    if bb_vals:
        bb_series = pd.Series(bb_vals).dropna()
        features['bb_width'] = bb_series.rank(pct=True)   # rank: low width = compressed

    # ATR(14) normalised by price — better position-sizing signal than raw vol
    atr_vals = {}
    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 15:
            continue
        high = series  # we only have adj_close, approximate H=L=C
        tr   = series.diff().abs()
        atr  = tr.ewm(span=14, adjust=False).mean()
        atr_pct = atr / series.replace(0, np.nan)
        atr_vals[ticker] = float(atr_pct.iloc[-1]) if not pd.isna(atr_pct.iloc[-1]) else np.nan
    if atr_vals:
        atr_series = pd.Series(atr_vals).dropna()
        features['atr_14_pct'] = atr_series.rank(pct=True)

    # Rolling 63-day beta vs equal-weight portfolio (proxy for market beta)
    # Low beta stocks tend to outperform on a risk-adjusted basis (low-vol anomaly)
    if len(log_returns) >= 63:
        mkt_ret = log_returns.tail(63).mean(axis=1)  # equal-weight proxy
        beta_vals = {}
        for ticker in log_returns.columns:
            ticker_ret = log_returns[ticker].tail(63).dropna()
            aligned = pd.concat([ticker_ret, mkt_ret], axis=1).dropna()
            if len(aligned) < 20:
                continue
            cov = aligned.cov().iloc[0, 1]
            var = aligned.iloc[:, 1].var()
            if var > 0:
                beta_vals[ticker] = cov / var
        if beta_vals:
            beta_series = pd.Series(beta_vals).dropna()
            features['beta_63d'] = beta_series.rank(pct=True)

    # Return skewness (63d) — negative skew stocks underperform systematically
    if len(log_returns) >= 63:
        skew_vals = log_returns.tail(63).skew()
        features['return_skew_63d'] = skew_vals.rank(pct=True)

    # Vol-adjusted momentum (Sharpe-like 12m signal)
    # Normalises 12m return by 63d vol — rewards consistent uptrends over volatile spikes
    if len(prices) >= 252 + 21 and 'vol_63d' in features or len(log_returns) >= 63:
        skip = 21
        ret_12m = prices.shift(skip) / prices.shift(252 + skip) - 1
        vol_63  = log_returns.tail(63).std() * np.sqrt(252)
        sharpe_mom = (ret_12m.iloc[-1] / vol_63.replace(0, np.nan)).dropna()
        features['sharpe_mom_12m'] = sharpe_mom.rank(pct=True)

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result
```

---

### 3. `compute_sector_relative_features(prices, sector_map)` — 4 new features

This is the highest-impact addition. Currently your signals compare a
semiconductor to a consumer staple — a completely different animal. Sector-
relative ranking tells you "is this the BEST semiconductor, not just whether
semiconductors are better than supermarkets today."

```python
def compute_sector_relative_features(
    prices: pd.DataFrame,
    sector_map: dict,
) -> pd.DataFrame:
    """
    Computes intra-sector ranks for the 4 core momentum windows.
    A rank of 1.0 means this ticker is the top momentum stock in its sector.

    sector_map: {ticker: sector_name}  — from TICKER_SECTORS in config.py
    """
    skip = 21
    windows = {
        'sector_mom_1m':  21,
        'sector_mom_3m':  63,
        'sector_mom_6m':  126,
        'sector_mom_12m': 252,
    }
    features = {}

    for feat_name, lookback in windows.items():
        required_len = lookback + skip
        if len(prices) < required_len:
            continue

        raw = prices.shift(skip) / prices.shift(lookback + skip) - 1
        latest = raw.iloc[-1].dropna()

        # Rank within each sector separately
        sector_ranks = {}
        for ticker in latest.index:
            sector = sector_map.get(ticker, 'other')
            sector_ranks.setdefault(sector, {})[ticker] = latest[ticker]

        result_ranks = {}
        for sector, ticker_vals in sector_ranks.items():
            if len(ticker_vals) < 2:
                # Only one ticker in sector — assign neutral rank
                for t in ticker_vals:
                    result_ranks[t] = 0.5
                continue
            vals_series = pd.Series(ticker_vals)
            ranked = vals_series.rank(pct=True)
            result_ranks.update(ranked.to_dict())

        features[feat_name] = pd.Series(result_ranks)

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result
```

---

### 4. `compute_mean_reversion_features(prices, log_returns)` — 3 new features

```python
def compute_mean_reversion_features(
    prices: pd.DataFrame,
    log_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Z-score mean reversion signals:
      z_score_63d  : price z-score over 63 days (over-extension from mean)
      z_score_21d  : price z-score over 21 days (shorter-term reversion)
      volume_ratio : not available from adj_close only — skip

    z-scores are negative when price is below mean (oversold), positive when above.
    For the MeanReversionAlpha model, low z-score = buy signal.
    """
    features = {}

    # 63-day z-score
    if len(prices) >= 63:
        mean_63 = prices.rolling(63).mean()
        std_63  = prices.rolling(63).std()
        z_63    = (prices - mean_63) / std_63.replace(0, np.nan)
        z_63_latest = z_63.iloc[-1].dropna()
        # Rank: low z-score (below mean) gets HIGH rank = buy signal
        features['z_score_63d'] = (-z_63_latest).rank(pct=True)

    # 21-day z-score
    if len(prices) >= 21:
        mean_21 = prices.rolling(21).mean()
        std_21  = prices.rolling(21).std()
        z_21    = (prices - mean_21) / std_21.replace(0, np.nan)
        z_21_latest = z_21.iloc[-1].dropna()
        features['z_score_21d'] = (-z_21_latest).rank(pct=True)

    # Mean reversion strength: how far from 52w SMA (useful for regime-conditional reversion)
    if len(prices) >= 252:
        sma_252 = prices.rolling(252).mean()
        deviation = (prices / sma_252.replace(0, np.nan) - 1)
        dev_latest = deviation.iloc[-1].dropna()
        features['sma_deviation_pct'] = dev_latest.rank(pct=True)

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result
```

---

## Wire all new functions into `run_feature_pipeline()`

At the end of `run_feature_pipeline()`, after `compute_technical_features`,
add these calls and join to `all_features`:

```python
# ── Extended momentum ─────────────────────────────────────────────────────────
from portfolio.src.config import TICKER_SECTORS

ext_mom = compute_extended_momentum_features(prices)
if not ext_mom.empty:
    frames.append(ext_mom)
    logger.info(f"Extended momentum features: {ext_mom.shape[1]} cols")

# ── Extended technical ────────────────────────────────────────────────────────
ext_tech = compute_extended_technical_features(prices, log_returns)
if not ext_tech.empty:
    frames.append(ext_tech)
    logger.info(f"Extended technical features: {ext_tech.shape[1]} cols")

# ── Sector-relative momentum ──────────────────────────────────────────────────
sector_rel = compute_sector_relative_features(prices, TICKER_SECTORS)
if not sector_rel.empty:
    frames.append(sector_rel)
    logger.info(f"Sector-relative features: {sector_rel.shape[1]} cols")

# ── Mean reversion z-scores ───────────────────────────────────────────────────
mr_features = compute_mean_reversion_features(prices, log_returns)
if not mr_features.empty:
    frames.append(mr_features)
    logger.info(f"Mean reversion features: {mr_features.shape[1]} cols")
```

---

## Update LSTM `FEATURE_NAMES` list

In `engine/alpha/lstm_model.py`, update the feature list to include the new features:

```python
FEATURE_NAMES = [
    # Core momentum
    'mom_1w', 'mom_1m', 'mom_3m', 'mom_6m', 'mom_9m', 'mom_12m',
    # Volatility
    'vol_21d', 'vol_63d', 'vol_of_vol',
    # Technical
    'rsi_14', 'rsi_21', 'bb_width', 'atr_14_pct',
    # Risk
    'beta_63d', 'return_skew_63d', 'sharpe_mom_12m',
    # Mean reversion
    'z_score_21d', 'z_score_63d', 'sma_deviation_pct',
    # Sector-relative (most powerful addition)
    'sector_mom_1m', 'sector_mom_3m', 'sector_mom_6m', 'sector_mom_12m',
    # 52-week positioning
    'price_to_52w_high',
]
```

This takes the LSTM from 8 → 24 input features. Retrain on Saturday
after deploying by running the weekly ML refresh.

---

## Feature count summary

| Category | Before | After |
|----------|--------|-------|
| Momentum | 4 | 8 (added 1w, 9m, 52w_high, sharpe_mom) |
| Volatility | 3 | 3 (unchanged) |
| Technical | 1 (rsi_14) | 6 (rsi_21, bb_width, atr_14_pct, beta, skew) |
| Mean reversion | 0 | 3 (z-scores, sma deviation) |
| Sector-relative | 0 | 4 (sector momentum ranks) |
| **Total** | **8** | **24** |

Expected LSTM AUC improvement: from ~0.54–0.56 to ~0.57–0.61 range,
based on typical feature-expansion effects on similar architectures.
No guarantees — but the signal quality improvement will be measurable
within 4–6 weeks of the IC tracking catching up.