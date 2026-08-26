> **STATUS: NOT IMPLEMENTED.**
> Phase 1 — three sub-phases, each with their own Gate 2 + Gate 3 before proceeding.
> Prerequisites: Gates 0 and 1 from `00-OVERVIEW.md` must be complete.
> Never modify `feature_builder.py` without setting the corresponding ENABLE_* flag.

# Phase 1 — Feature Additions
# `utils/feature_builder.py` — additive changes only
# `run_ml_pipeline.py` — config flags only
# Estimated time: Phase 1A: 2 days | 1B: 2 days | 1C: 1 day

---

## Phase 1A — Bridge existing DB signals into the ML pipeline

### The problem

Your ML pipeline and your production engine are two separate data universes:

```
Production engine (engine_data.db)         ML pipeline (parquet files)
────────────────────────────────           ──────────────────────────
feature_store table                        fetch_macro_data() → macro.parquet
  └─ stress_score (daily)                  fetch_fundamentals() → fundamentals.parquet
  └─ macro_vix (daily)
  └─ macro_risk_on (daily)
  └─ macro_yield_spread (daily)
pead_setups table                          ← not connected
earnings_calendar table                    ← not connected
```

The ML model makes the final signal decision but has never seen:
- The regime stress score your engine computes every day
- The PEAD setup for a stock (was there an earnings beat? how many days ago?)
- Whether a stock is within 5 days of an earnings report

These are real signals that the production pipeline already computes. The gap is
purely a data plumbing problem — no new logic needed.

### Why this is higher priority than new features

Adding new features that require new computation risks overfitting on the feature
construction itself. Bridging existing signals doesn't introduce new computation —
the signals are already validated by daily use in the production pipeline.
Regime features specifically have proven predictive in the BL model (the regime
view is one of your alpha sources). The ML model should know about them too.

### New function: `add_db_regime_features()`

**Location:** `utils/feature_builder.py`, new function at bottom.
**Enable flag:** `ENABLE_DB_REGIME_FEATURES = True` in `run_ml_pipeline.py` config block.

```python
ENABLE_DB_REGIME_FEATURES = False  # Gate 2 must pass before setting True
```

**What it fetches:**

From `feature_store` table (already populated by production scheduler):
```sql
SELECT date, feature_name, feature_value
FROM feature_store
WHERE ticker = '_PORTFOLIO'
  AND feature_name IN (
    'stress_score',
    'macro_vix',
    'macro_risk_on',
    'macro_risk_off',
    'macro_yield_spread',
    'macro_hy_spread',
    'macro_easing',
    'macro_tightening',
    'macro_expansion',
    'macro_slowdown',
    'macro_contraction',
    'macro_ew_transition',
    'macro_ew_count',
    'macro_streak_days'
  )
ORDER BY date ASC
```

This gives you 14 features that are already computed, already in the DB, already
validated by the production pipeline every week.

**How to add to the feature DataFrame (no lookahead):**

```python
def add_db_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds production engine regime features to the ML feature DataFrame.
    Reads from feature_store (ticker='_PORTFOLIO') in engine_data.db.
    
    LOOKAHEAD PROTECTION: features are aligned with a 1-day lag
    (feature date t-1 is used for training row at date t).
    This matches production: features computed at Monday close are used
    for Tuesday's signal.
    
    HOLDOUT PROTECTION: df.index dates must already be filtered to
    pre-holdout only before calling this function. This function does
    not filter — it is the caller's responsibility.
    """
    import sqlite3
    import os
    
    # Resolve path to production DB
    here = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.normpath(os.path.join(here, '..', '..', '..', '..', 'engine_data.db'))
    
    if not os.path.exists(db_path):
        log.warning(f"[DB regime] engine_data.db not found at {db_path} — skipping")
        return df
    
    FEATURES = [
        'stress_score', 'macro_vix', 'macro_risk_on', 'macro_risk_off',
        'macro_yield_spread', 'macro_hy_spread', 'macro_easing',
        'macro_tightening', 'macro_expansion', 'macro_slowdown',
        'macro_contraction', 'macro_ew_transition', 'macro_ew_count',
        'macro_streak_days',
    ]
    
    placeholders = ','.join([f'"{f}"' for f in FEATURES])
    
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
    
    # Pivot to wide format: index=date, columns=feature_name
    regime_wide = raw.pivot(index='date', columns='feature_name', values='feature_value')
    regime_wide.columns = [f'db_{c}' for c in regime_wide.columns]  # prefix to avoid collision
    
    # Forward-fill gaps (weekends, missed runs) up to 5 days
    regime_wide = regime_wide.sort_index().ffill(limit=5)
    
    # ── CRITICAL: 1-day lag to prevent lookahead ──────────────────────────────
    # Feature computed on day t is shifted to appear at row t+1.
    # Production already does this: Monday features → Tuesday signal.
    regime_wide = regime_wide.shift(1)
    
    # Align to df index
    aligned = regime_wide.reindex(df.index, method='ffill', limit=5)
    
    n_before = len(df.columns)
    df = df.join(aligned, how='left')
    n_added = len(df.columns) - n_before
    
    log.info(f"[DB regime] Added {n_added} regime features from production DB")
    return df
```

**Temporal clustering mitigation for this feature family:**

Because these features are identical for all tickers on the same date, the IC test
for this family specifically must verify:

1. Compute cross-sectional IC (Spearman rank between signal and return across tickers
   on the same date) — regime features have IC = 0 by construction because they don't
   vary cross-sectionally.
2. Their value is **not as a ranking signal but as a conditioning signal** — the model
   learns "when macro_risk_off=1, all momentum signals are less reliable." This is
   valid learning but must be verified by running IC evaluation *separately* for
   Risk-On periods and Risk-Off periods and checking that the model's discrimination
   is different across regimes.
3. If AUC in Risk-On periods vs Risk-Off periods is not statistically different after
   adding DB regime features, they're contributing nothing and should be excluded.

---

### New function: `add_pead_features()`

**Enable flag:** `ENABLE_PEAD_FEATURES = False`

**What it fetches:**

From `pead_setups` table:
```sql
SELECT ticker, report_date, eps_surprise_pct, pead_score
FROM pead_setups
ORDER BY report_date ASC
```

**Features generated:**

```python
def add_pead_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Adds PEAD-based features:
    - db_pead_surprise_pct: EPS surprise % from last earnings report
    - db_pead_days_since:   Calendar days since that report
    - db_pead_in_window:    1 if 0 < days_since < 63 (within drift window), else 0
    - db_pead_score:        PEAD score from pead_setups (0–1)
    
    LOOKAHEAD: uses report_date to assign features. A row at date t uses
    the most recent pead_setup with report_date < t. No future earnings used.
    """
```

**Columns added:** `db_pead_surprise_pct`, `db_pead_days_since`, `db_pead_in_window`, `db_pead_score`
**Count:** 4 features

**Why these are clean:**
- EPS surprise is known at report date — it's historical fact, not a forecast
- `days_since_report` is purely temporal — no market information
- The PEAD score in the DB was computed from data available at report time

---

### New function: `add_earnings_calendar_features()`

**Enable flag:** `ENABLE_EARNINGS_CALENDAR_FEATURES = False`

**Features generated:**
```python
def add_earnings_calendar_features(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    - db_days_to_earnings: trading days until next scheduled earnings report
      (NaN if no report found in next 90 days)
    - db_pre_earnings_window: 1 if within 5 trading days of next report, else 0
    
    LOOKAHEAD: uses earnings_calendar.expected_date. Only dates that were
    known as of the current row's date are used (no future-dated reports).
    This is imperfect — earnings dates are sometimes moved. Conservative
    approach: only use earnings_calendar rows where confirmed=1.
    """
```

**Columns added:** `db_days_to_earnings`, `db_pre_earnings_window`
**Count:** 2 features

**Why these matter:** Pre-earnings windows have documented return anomalies (pre-earnings
drift, IV crush post-earnings). The ML model having no idea that NVDA reports in 4 days
is a genuine gap.

---

### Phase 1A total new features: 20 (14 regime + 4 PEAD + 2 earnings)

After passing Gate 2 and Gate 3 for Phase 1A, the importance gate will prune the
low-contributors. Expect 8–14 to survive selection.

---

## Phase 1B — Cross-sectional features + price acceleration

### Why these are higher-value than more per-ticker features

A per-ticker model for NVDA can learn: "NVDA up 15% in 21 days → tends to continue."
But it cannot learn: "NVDA up 15% while the median stock in the universe is down 2%
→ this is a much stronger signal than NVDA up 15% in a rising market."

Cross-sectional features inject the **relative** information without requiring a panel
model. The per-ticker model still trains separately, but each feature now encodes
"where is this stock relative to its peers today."

### Prerequisite: Universe snapshot at each date

Cross-sectional features require knowing which tickers had valid (non-stale) prices
on each date. Do NOT compute ranks using the full universe indiscriminately —
this introduces survivorship bias for early dates.

```python
def get_universe_snapshot(prices_dict: dict, date: pd.Timestamp,
                          max_stale_days: int = 5) -> list:
    """
    Returns list of tickers that had valid (non-stale) prices on the given date.
    A ticker is valid if it has at least one non-NaN price in the 5 trading days
    up to and including date. This mirrors the ffill(limit=5) logic in the engine.
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
```

### New function: `add_crosssectional_features()`

**Enable flag:** `ENABLE_CROSSSECTIONAL_FEATURES = False`

**Location:** `utils/feature_builder.py`, requires `prices_dict` (full universe
prices passed from `run_ml_pipeline.py`). `build_features()` signature expands:

```python
def build_features(price_df, fundamentals=None, macro_df=None,
                   options_dict=None, horizons=None,
                   prices_dict=None,   # ← NEW: full universe for CS features
                   ticker=None):       # ← NEW: current ticker name
```

**Features generated:**

```python
CROSSSECTIONAL_WINDOWS = [5, 21, 63]

def add_crosssectional_features(df: pd.DataFrame, ticker: str,
                                prices_dict: dict) -> pd.DataFrame:
    """
    For each row (date t), computes cross-sectional ranks across the universe.
    
    Features:
      cs_ret_{n}d_rank    — percentile rank of this ticker's n-day return
                            within the universe at date t. [0, 1].
                            1.0 = top performer, 0.0 = worst performer.
      
      cs_vol_21d_rank     — percentile rank of this ticker's 21d realised vol
                            within the universe. High rank = high vol relative
                            to peers.
      
      cs_sector_excess_{n}d — this ticker's n-day return minus the median
                              n-day return of all tickers in the same sector.
                              Positive = outperforming sector peers.
    
    LOOKAHEAD PROTECTION: uses only prices on date t and earlier.
    No future prices are ever accessed.
    
    SURVIVORSHIP PROTECTION: universe at date t = only tickers with valid
    prices on date t (via get_universe_snapshot). Excludes tickers added
    after date t.
    
    COMPUTATIONAL NOTE: this is expensive — O(n_dates × n_universe).
    Precompute the full rank matrix once at the start of the ML run,
    not inside the per-ticker loop. See run_ml_pipeline.py modifications.
    """
```

**Precomputation pattern** (in `run_ml_pipeline.py`):

```python
# Compute cross-sectional rank matrices once before the per-ticker loop
# This avoids recomputing the same ranks 130 times
cs_features_cache = {}

if ENABLE_CROSSSECTIONAL_FEATURES:
    log.info("Precomputing cross-sectional rank matrices...")
    all_tickers_prices = {}
    for t, df in prices.items():
        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        all_tickers_prices[t] = df[price_col] if price_col in df.columns else None
    
    # Build return series for each ticker
    returns_df = pd.DataFrame({
        t: s.pct_change()
        for t, s in all_tickers_prices.items() if s is not None
    }).sort_index()
    
    for n in [5, 21, 63]:
        # Rolling n-day return for all tickers
        rolling_ret = returns_df.rolling(n).apply(lambda x: (1 + x).prod() - 1)
        # Cross-sectional rank at each date (pct=True → [0, 1])
        cs_features_cache[f'cs_ret_{n}d_rank'] = rolling_ret.rank(axis=1, pct=True)
    
    # Vol rank
    rolling_vol = returns_df.rolling(21).std() * np.sqrt(252)
    cs_features_cache['cs_vol_21d_rank'] = rolling_vol.rank(axis=1, pct=True)
    
    log.info(f"CS rank matrices precomputed: {len(cs_features_cache)} matrices")
```

**Columns added:** `cs_ret_5d_rank`, `cs_ret_21d_rank`, `cs_ret_63d_rank`, `cs_vol_21d_rank`,
`cs_sector_excess_5d`, `cs_sector_excess_21d`
**Count:** 6 features

---

### New function: `add_acceleration_features()`

**Enable flag:** `ENABLE_ACCELERATION_FEATURES = False`

**What it computes:**

```python
def add_acceleration_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Momentum acceleration: is the momentum speeding up or slowing down?
    
    Features:
      ret_accel_1m    = ret_5d / ret_21d  — short-term vs medium-term
                        > 1: momentum accelerating
                        < 1: momentum decelerating (possible mean reversion)
      
      ret_accel_3m    = ret_21d / ret_63d — medium-term vs long-term
      
      vol_regime      = vol_21d / vol_63d — is vol expanding or contracting?
                        > 1: volatility expanding (trend or stress)
                        < 1: volatility compressing (breakout risk)
      
      bb_width        = (bb_upper - bb_lower) / bb_mid
                        Bollinger Band width — volatility squeeze detector.
                        Very low width → tends to precede large moves.
      
      rsi_momentum    = rsi_14 - rsi_14.shift(5)
                        RSI change over 5 days — is momentum building or fading?
    
    All features are dimensionless ratios (no absolute price references).
    These can be computed from features already in df — no new data loading.
    
    Edge cases:
      - Division by near-zero: ret_21d ≈ 0 → ret_accel_1m = NaN (handled by dropna)
      - Negative return / negative return → positive ratio: OK, handled correctly
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
```

**Columns added:** `ret_accel_1m`, `ret_accel_3m`, `vol_regime`, `bb_width`, `rsi_momentum`
**Count:** 5 features

---

### Phase 1B total new features: 11 (6 CS + 5 acceleration)

---

## Phase 1C — Richer technical features (lowest priority, smallest gain)

**Enable flag:** `ENABLE_TECHNICAL_V2_FEATURES = False`

### Features to add

**VWAP deviation:**
```
vwap_deviation = (close - VWAP_21d) / VWAP_21d
```
VWAP_21d = sum(price × volume, last 21 days) / sum(volume, last 21 days)
Value: stocks consistently trading below VWAP are under distribution pressure.

**Chaikin Money Flow (CMF_21d):**
```
money_flow = ((close - low) - (high - close)) / (high - low) × volume
CMF = sum(money_flow, 21 days) / sum(volume, 21 days)
```
Range: -1 to +1. Strong positive: institutional accumulation.

**Average Directional Index (ADX_14):**
Measures trend strength, not direction. ADX > 25 = trending market for this stock.
Low ADX = ranging/mean-reverting regime.

**Price-to-52w-high momentum interaction:**
```
near_52w_high = (dist_52w_high > -0.05).astype(int)  # within 5% of 52w high
near_52w_low  = (dist_52w_low < 0.05).astype(int)    # within 5% of 52w low
```
These are binary features. Near-52w-high + strong momentum = breakout candidate.

**Columns added:** `vwap_deviation`, `cmf_21d`, `adx_14`, `near_52w_high`, `near_52w_low`
**Count:** 5 features

### Why Phase 1C is lowest priority

Technical features 1C are all derivable from price and volume — the same data your
existing 6 technical features use. The importance gate will likely prune most of them
because they'll be correlated with `bb_position`, `rsi_14`, `dist_52w_high`. Do not
implement Phase 1C until Phase 1A and 1B are validated through Gate 3. If Gate 4
passes after 1A + 1B, the marginal gain from 1C may not be worth the risk.

---

## Summary: total new features by phase

| Phase | Features added | Enable flag |
|---|---|---|
| 1A-Regime | 14 (stress_score, macro_vix, macro_risk_on/off, yield_spread, etc.) | `ENABLE_DB_REGIME_FEATURES` |
| 1A-PEAD | 4 (surprise_pct, days_since, in_window, score) | `ENABLE_PEAD_FEATURES` |
| 1A-Earnings | 2 (days_to_earnings, pre_earnings_window) | `ENABLE_EARNINGS_CALENDAR_FEATURES` |
| 1B-CS | 6 (ret ranks 5/21/63d, vol rank, sector excess 5/21d) | `ENABLE_CROSSSECTIONAL_FEATURES` |
| 1B-Accel | 5 (ret_accel_1m/3m, vol_regime, bb_width, rsi_momentum) | `ENABLE_ACCELERATION_FEATURES` |
| 1C-Technical | 5 (vwap, cmf, adx, near 52w high/low) | `ENABLE_TECHNICAL_V2_FEATURES` |
| **TOTAL** | **36 candidates** | Individual flags |

The feature selection pipeline will reduce this to ~10–20 survivors across all families
combined. That's the point — add broadly, let the importance gate prune, validate the survivors.

---

## Changes to `run_ml_pipeline.py`

Config block (add after line 76 in current file):

```python
# ── Phase 1 Feature Addition Flags ───────────────────────────────────────────
# Do NOT set any to True until the corresponding Gate 2 results are recorded
# in better-alpha/gate2_results.csv. See 00-OVERVIEW.md for gate definitions.
ENABLE_DB_REGIME_FEATURES         = False   # Phase 1A
ENABLE_PEAD_FEATURES              = False   # Phase 1A
ENABLE_EARNINGS_CALENDAR_FEATURES = False   # Phase 1A
ENABLE_CROSSSECTIONAL_FEATURES    = False   # Phase 1B
ENABLE_ACCELERATION_FEATURES      = False   # Phase 1B
ENABLE_TECHNICAL_V2_FEATURES      = False   # Phase 1C
```

Changes to `build_features()` call in `run_ticker()` (around line 151):

```python
feat_df = build_features(
    prices[ticker],
    fundamentals=fundamentals.get(ticker),
    macro_df=macro,
    options_dict=options_dict,
    horizons=HORIZONS,
    prices_dict=prices if ENABLE_CROSSSECTIONAL_FEATURES else None,  # NEW
    ticker=ticker if ENABLE_CROSSSECTIONAL_FEATURES else None,        # NEW
    cs_cache=cs_features_cache if ENABLE_CROSSSECTIONAL_FEATURES else None,  # NEW
    enable_db_regime=ENABLE_DB_REGIME_FEATURES,                       # NEW
    enable_pead=ENABLE_PEAD_FEATURES,                                 # NEW
    enable_earnings=ENABLE_EARNINGS_CALENDAR_FEATURES,                # NEW
    enable_acceleration=ENABLE_ACCELERATION_FEATURES,                 # NEW
    enable_technical_v2=ENABLE_TECHNICAL_V2_FEATURES,                # NEW
)
```

---

## Tracking file: `better-alpha/gate2_results.csv`

Create this file manually before starting Phase 1. Update it after each Gate 2 test.

```csv
date_tested,family,flag_name,mean_ic_before,mean_ic_after,delta_ic,icir_before,icir_after,mean_auc_before,mean_auc_after,delta_auc,pass,notes
```

Example after Phase 1A-Regime test:
```
2026-09-15,DB_Regime,ENABLE_DB_REGIME_FEATURES,0.048,0.053,+0.005,0.71,0.69,0.572,0.581,+0.009,PASS,regime transition in fold 2 (2022 bear)
```
