> **STATUS: NOT IMPLEMENTED. DO NOT START.**
> Hard prerequisite: Gate 5 from `00-OVERVIEW.md` must fully pass.
> This means Phase 1 features validated through Gate 4 AND 4 Saturdays of live IC.
> This doc is written now for design clarity — it is NOT approved for implementation.

# Phase 2 — Panel Model Architecture
# `run_ml_pipeline_panel.py` (NEW — never replaces run_ml_pipeline.py)
# Estimated time: 1–2 weeks after Gate 5 passes

---

## Why a panel model, precisely

The per-ticker model for NVDA trains on ~1,000 rows. But stock returns are
notoriously low-signal. In practice, the ML model is trying to distinguish
signal from noise across those 1,000 rows using ~50 features. The effective
sample size is far lower once you account for autocorrelation between adjacent
trading days (a real correlation structure that makes independent observations
maybe 1/5th of total rows).

A panel model trains on all 130 tickers × all dates simultaneously. Each row
is one observation: `(ticker=NVDA, date=2024-03-15, features=..., target=1)`.
This gives you ~130,000 rows instead of ~1,000. The model learns patterns that
generalise *across stocks* — "RSI > 70 AND below sector median momentum AND
in Risk-Off regime → negative return" might appear 3 times in NVDA's history
but 400+ times across the universe.

---

## The structural problems with a naive panel model

Getting this wrong is easy. These are the failure modes in order of severity:

### Problem 1 — Date-based train/test split (the most critical)

**WRONG split (ticker-based):**
```
Train: 80 tickers (including NVDA)
Test:  50 tickers (never seen by model)
```
This looks like valid cross-validation but it isn't. NVDA in the test set has
dates that OVERLAP with the training set. AMD was in training data on 2024-03-15
with target=1. Now you're asking the model to predict NVDA on the same date.
AMD's target leaked into training — the model knows what the market did on
that date.

**CORRECT split (date-based, same as walk-forward):**
```
Train: all 130 tickers, dates 2022-01-01 to 2024-01-01
Test:  all 130 tickers, dates 2024-01-01 to 2024-07-01
```
The future (test period) is never in the training set for ANY ticker.
This is the only valid split structure.

### Problem 2 — Cross-sectional leakage in features

If feature `cs_ret_21d_rank` is computed using all tickers in the universe,
then at any given date t, the rank of NVDA depends on the returns of all
other tickers including those in the test set. This is NOT leakage in the
time sense (we're only using returns up to date t), but it is a form of
cross-sectional contamination that doesn't exist in live trading (the rank
is computed on available tickers at date t, not a fixed universe).

Mitigation: ranks are computed at each date using only tickers with valid
prices at that date, using only prices up to that date. Same logic as
Phase 1B — the CS precomputation already handles this.

### Problem 3 — Ticker-specific patterns disappear

The per-ticker model for NVDA can learn:
"NVDA specifically tends to revert after earnings gaps > 5%."
A panel model trained on 130 tickers treats all stocks equally.
NVDA's specific tendency gets diluted by 129 other stocks with different behaviors.

Mitigation: **ticker embeddings** (categorical encoding of the ticker as a feature).
The model can learn NVDA-specific adjustments. But this requires enough data
per ticker for the embedding to be meaningful (~300+ observations per ticker,
which you have).

Alternative: **sector fixed effects** — encode sector as a one-hot feature.
The model learns sector-level patterns without needing per-ticker embeddings.
This is simpler and less overfit-prone.

### Problem 4 — Data imbalance across tickers

Some tickers have data from 2022 (full 4 years). Others might have joined
the universe in 2024 (only 2 years). If the model trains on all rows equally,
heavily-represented tickers dominate the weight updates.

Mitigation: sample weights inversely proportional to the number of observations
per ticker. Each ticker contributes equally to the loss function regardless of
how many rows it has.

### Problem 5 — Heteroscedasticity (different volatility regimes per ticker)

NVDA's daily moves are ±3–5%. A utility stock's daily moves are ±0.5%.
The same feature value (e.g., `ret_5d = 0.08`) means very different things
for each stock. In the per-ticker model, each model normalises implicitly
because it only trains on one stock. In the panel model, you must normalise
explicitly.

Mitigation: before training, cross-sectionally standardise all features at
each date (z-score within the universe snapshot at date t). Each feature
becomes "how extreme is this ticker relative to peers today" — a dimensionless
signal.

---

## Architecture: the correct panel model design

### Data structure

```
Panel DataFrame: one row per (ticker, date)
Columns:
  ticker              — string identifier (for embedding or exclusion)
  date                — datetime (used ONLY for train/test split, never as feature)
  sector_enc_*        — one-hot encoded sector (n_sectors columns)
  [all phase 1 features, cross-sectionally standardised at each date]
  target_dir_21d      — binary label (0/1)
```

### Cross-sectional standardisation (at each date, not globally)

```python
def crosssectional_standardize(panel_df: pd.DataFrame,
                                feature_cols: list,
                                date_col: str = 'date') -> pd.DataFrame:
    """
    At each date, standardise all feature columns to zero mean, unit std
    across all tickers in the universe on that date.
    
    This is different from global standardisation (StandardScaler on full dataset):
    global standardisation leaks the mean/std of future dates into past normalisation.
    
    Cross-sectional: each date is normalised independently.
    NVDA's ret_5d=0.08 might become cs-zscore=1.2 on a flat day,
    but cs-zscore=0.3 on a day when everything rallied.
    That's the correct signal.
    """
    result = panel_df.copy()
    for date, group in panel_df.groupby(date_col):
        idx = group.index
        for feat in feature_cols:
            vals = group[feat]
            mu  = vals.mean()
            std = vals.std()
            if std < 1e-8:
                result.loc[idx, feat] = 0.0
            else:
                result.loc[idx, feat] = (vals - mu) / std
    return result
```

### Walk-forward split for the panel

```python
def panel_walk_forward_splits(panel_df: pd.DataFrame,
                               date_col: str,
                               train_years: float = 2.0,
                               val_months: float = 6.0,
                               step_months: float = 6.0):
    """
    Expanding window walk-forward for the panel.
    
    Each split: all tickers, all dates.
    Train:      dates in [start, cutoff)
    Validation: dates in [cutoff, cutoff + val_months)
    
    Yields (train_idx, val_idx) — integer positional indices.
    """
    dates = pd.to_datetime(panel_df[date_col])
    all_dates = sorted(dates.unique())
    
    min_train = pd.DateOffset(years=train_years)
    val_window = pd.DateOffset(months=val_months)
    step = pd.DateOffset(months=step_months)
    
    first_date = all_dates[0]
    first_valid_cutoff = first_date + min_train
    
    cutoff = first_valid_cutoff
    while cutoff + val_window <= all_dates[-1]:
        train_mask = dates < cutoff
        val_mask   = (dates >= cutoff) & (dates < cutoff + val_window)
        
        train_idx = panel_df.index[train_mask].tolist()
        val_idx   = panel_df.index[val_mask].tolist()
        
        if len(train_idx) > 1000 and len(val_idx) > 100:
            yield train_idx, val_idx
        
        cutoff += step
```

### Sample weights to equalise ticker contribution

```python
def compute_ticker_weights(panel_df: pd.DataFrame,
                           ticker_col: str = 'ticker') -> np.ndarray:
    """
    Each ticker's rows get weight = 1 / n_rows_for_that_ticker,
    then normalised so weights sum to 1.
    
    Result: each ticker contributes equally to the loss, regardless
    of how many observations it has.
    """
    counts = panel_df.groupby(ticker_col).size()
    weights = panel_df[ticker_col].map(lambda t: 1.0 / counts[t])
    weights = weights / weights.sum()
    return weights.values
```

### Model recommendations for panel

**Do not use:** LogisticRegression on the raw panel (too underpowered, can't learn
interactions between features × sector × regime).

**Recommended:**
1. `LightGBM` (preferred over XGBoost for tabular data with categorical features)
   — can handle ticker and sector as native categoricals without one-hot encoding
   — faster training than XGBoost on large panels
   — supports sample weights natively

2. `RandomForest` as baseline comparison (already in your stack)
   — runs as sanity check: if LightGBM doesn't beat RF on the panel, something is wrong

3. Do NOT use: LSTM, Transformer, or any sequential model. The panel rows are not
   sequential — each row is an independent (ticker, date) observation after CS standardisation.
   Time dependence is handled by the walk-forward split, not by the model architecture.

---

## Output: `ml_state_panel.json`

The panel model writes to a SEPARATE state file. Never overwrites `ml_state.json`.

```json
{
  "available": true,
  "generated_at": "2026-10-01T09:30:00",
  "architecture": "panel_lgbm",
  "n_tickers": 130,
  "n_rows_trained": 98000,
  "n_features": 48,
  "walk_forward_auc": 0.591,
  "model_signals": {
    "NVDA": {
      "up_proba_21d": 0.623,
      "auc": 0.591,
      "panel_model": true
    }
  }
}
```

The Flask dashboard `lab.html` shows BOTH `ml_state.json` and `ml_state_panel.json`
side by side for comparison. The BL engine (`ml_alpha.py`) continues using
`ml_state.json` until the panel model has 4 weeks of live IC evidence showing
superiority.

---

## How to decide: per-ticker vs panel

After 4 Saturdays of panel model IC measurement, compare:

| Metric | Per-ticker wins if: | Panel wins if: |
|---|---|---|
| Mean AUC | per-ticker AUC > panel AUC | panel AUC > per-ticker by > 0.010 |
| IC 21d | per-ticker IC > panel IC | panel IC > per-ticker by > 0.005 |
| ICIR | per-ticker ICIR > panel ICIR | panel ICIR > per-ticker by > 0.10 |
| Training time | — | panel must finish in < 90 min on your hardware |
| IC consistency | per-ticker is more consistent across tickers | panel is more consistent |

**If per-ticker wins or ties:** keep per-ticker. The panel model is not worth maintaining.
**If panel wins on all 3 metrics:** migrate `ml_alpha.py` to read `ml_state_panel.json`.
**If mixed results:** run both in production with equal weight blending.

---

## What the panel model cannot fix

Even a perfect panel model cannot overcome:

1. **2 years of data.** Your universe only has reliable prices back to 2022.
   A panel gives you 130× more rows but the temporal depth is still 2 years.
   Patterns that require 5+ years to observe (full business cycles) simply don't
   exist in your training data.

2. **Sparse fundamentals.** PE/PB/EV_EBITDA from yfinance are point-in-time
   snapshots with no historical quarterly data. The panel model has the same
   stale fundamental features as the per-ticker model.

3. **Low signal-to-noise in equity returns.** Even the best quant funds achieve
   IC around 0.05–0.10 at 21-day horizons. If your IC ceiling is ~0.06, no
   architecture change will push it to 0.20. Architecture changes affect how well
   you extract the existing signal, not how much signal exists.

4. **Small universe.** 130 tickers is too small for deep embeddings or complex
   cross-sectional learning. The panel model helps here, but 5,000+ tickers is
   where panel models really excel. You'll get improvement but not a step-change.
