> **STATUS: NOT IMPLEMENTED. DO NOT START.**
> Phase 1D — Target Refinement.
> Prerequisites: Phase 1A, 1B, 1C must be completed and validated via Gate 4, OR
> you can run this test completely independently on baseline_v1.
> Never modify `feature_builder.py` without setting the corresponding ENABLE_* flag.

# Phase 1D — Target Refinement (Predicting Alpha)
# `utils/feature_builder.py` — modify `add_target()`
# `run_ml_pipeline.py` — config flags only
# Estimated time: 0.5 days

---

## The structural flaw in absolute return targets

Currently, the ML pipeline predicts `target_dir_21d`, which is `1` if the stock's 21-day forward return is `> 0`.

**The problem:**
In a strong bull market (like 2023-2024), the MSCI World index might go up 5% in a month. During that month, a poorly performing stock might drift up 1%. 
Under the current logic, the model receives a `1` (Success) for that stock. The model is rewarded for picking a stock that underperformed the market simply because the market dragged it up. It learns bad habits.

In a bear market, an excellent stock might fall 2% while the market falls 10%. The model receives a `0` (Failure), penalizing it for picking relative strength.

## The Fix: Market-Adjusted Returns (Alpha)

Instead of absolute return, the model should predict **Excess Return (Alpha)**.
Target = `(Stock_Return_21d > Benchmark_Return_21d)`

This forces the model to learn the true characteristics of outperformance, immune to the general market tide.

### New Config Flag in `run_ml_pipeline.py`

Add to the Phase 1 config block:
```python
ENABLE_ALPHA_TARGET = False  # Phase 1D: Predict return relative to benchmark
```

### Passing the benchmark to the feature builder

To compute Alpha, `feature_builder.py` needs the benchmark returns.
In `run_ml_pipeline.py`, update the `build_features` call to pass the benchmark prices. The benchmark `EUNL.DE` (iShares MSCI World) is already in the `prices` dict.

```python
# In run_ml_pipeline.py
benchmark_df = prices.get('EUNL.DE')
```
Pass this to `build_features`:
```python
feat_df = build_features(
    # ... existing args ...
    benchmark_df=benchmark_df if ENABLE_ALPHA_TARGET else None,
    enable_alpha_target=ENABLE_ALPHA_TARGET
)
```

### Updating `add_target()` in `utils/feature_builder.py`

```python
def add_target(df: pd.DataFrame, horizons=None, benchmark_df=None, enable_alpha_target=False) -> pd.DataFrame:
    if horizons is None:
        horizons = [5, 21, 63]
    c = df["Adj Close"]
    
    # If alpha target is enabled and benchmark is provided
    if enable_alpha_target and benchmark_df is not None:
        bench_c = benchmark_df["Adj Close"]
        # Align benchmark to the current stock's dates
        bench_c = bench_c.reindex(df.index, method='ffill')
        
    for n in horizons:
        fut = c.shift(-n) / c - 1
        df[f"future_ret_{n}d"] = fut
        
        if enable_alpha_target and benchmark_df is not None:
            bench_fut = bench_c.shift(-n) / bench_c - 1
            excess_fut = fut - bench_fut
            df[f"target_dir_{n}d"] = (excess_fut > 0).astype(int)
            
            # The magnitude bins shift to represent relative performance
            bins = [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf]
            df[f"target_mag_{n}d"] = pd.cut(excess_fut, bins=bins, labels=[0, 1, 2, 3, 4]).astype("Int64")
        else:
            df[f"target_dir_{n}d"] = (fut > 0).astype(int)
            
            bins = [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf]
            df[f"target_mag_{n}d"] = pd.cut(fut, bins=bins, labels=[0, 1, 2, 3, 4]).astype("Int64")
            
    return df
```

## How to test this (Gate 2 + Gate 3)

This is a **Target** change, not a feature change. Therefore, it changes what the model considers a "correct" prediction.

When evaluating `alpha_ic_results.csv` in Gate 2:
1. Run the pipeline with `ENABLE_ALPHA_TARGET = True` on the walk-forward window.
2. The IC score (`mean_ic`) will now measure the correlation between the model's predictions and the *forward excess returns*. Because IC naturally measures rank ordering, a model that predicts relative strength (alpha) should naturally achieve a higher IC.
3. **Pass condition:** The `mean_ic` must improve by `> 0.003` over baseline_v1. Because we are stripping out market noise, the model's ability to rank stocks top-to-bottom should become mathematically cleaner.
4. If it passes Gate 2, proceed to Gate 3 (2 weeks of live Saturday IC evaluation).

---

## Why we rejected other ideas

For strict documentation purposes, the following ideas were brainstormed and explicitly **REJECTED** due to overengineering risk:

- **Continuous Hyperparameter Tuning (Optuna inside walk-forward):** REJECTED. Turns a 30-minute run into a 6-hour run. High risk of overfitting to noise in small temporal windows. Hardcoded robust defaults (`max_depth=4`, etc.) are safer.
- **Regime-Conditional Ensembling (e.g. 80% LR in high vol, 80% XGB in low vol):** REJECTED. The portfolio engine (`Black-Litterman`) already cuts risk based on `stress_score`. Doing it in the ML model double-counts the regime risk and causes over-shrinkage (moving to cash too aggressively).
- **Custom Asymmetric Loss Functions:** REJECTED. Writing custom gradients for XGBoost is highly error-prone, fails silently, and is extremely hard to debug or revert. Standard LogLoss is mathematically robust.
