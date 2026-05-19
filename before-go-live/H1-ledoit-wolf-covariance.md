# H1: Ledoit-Wolf Covariance Shrinkage
**High Priority | File: `engine/scheduler.py` → `step_portfolio_construction()`**

---

## What is wrong

`step_portfolio_construction()` computes the covariance matrix as:
```python
cov_matrix = log_returns[available_tickers].cov() * 252
```

Standard historical covariance has a well-known problem: with N tickers and
T observations, if N is close to T, the matrix is "noisy" — small sample
estimation error creates artificially extreme eigenvalues. The optimizer treats
this noise as signal and produces extreme, unstable weights.

Your universe has ~130 tickers. With 252 days of history, this is right at the
boundary where noise becomes a serious problem. The result is the optimizer
suggesting large concentrations that shift dramatically week-to-week based on
noise, not genuine co-movement changes.

Ledoit-Wolf shrinkage solves this by pulling the covariance matrix toward a
structured target (usually the identity), reducing estimation noise without
losing real correlation structure.

---

## Fix

`scikit-learn` (already in your environment) includes `LedoitWolf`. Replace
the raw `.cov()` call:

**Before:**
```python
cov_matrix = log_returns[available_tickers].cov() * 252
```

**After:**
```python
from sklearn.covariance import LedoitWolf

returns_matrix = log_returns[available_tickers].dropna()
if len(returns_matrix) >= len(available_tickers):
    lw = LedoitWolf().fit(returns_matrix.values)
    cov_matrix = pd.DataFrame(
        lw.covariance_ * 252,
        index=available_tickers,
        columns=available_tickers,
    )
    logger.info(f"[portfolio] Covariance: Ledoit-Wolf shrinkage applied (shrinkage={lw.shrinkage_:.3f})")
else:
    # Fallback to standard if insufficient observations
    cov_matrix = log_returns[available_tickers].cov() * 252
    logger.warning("[portfolio] Insufficient data for Ledoit-Wolf — using raw covariance")
```

---

## Also apply in `engine/portfolio/optimizer.py`

The `optimize_with_bl()` function receives `cov_matrix` from the scheduler.
If you apply the fix in the scheduler, the optimizer automatically uses the
shrunk matrix. No changes needed in `optimizer.py`.

---

## Expected impact

- Portfolio weights will be more stable week-to-week
- Fewer spurious rebalance orders (less churn, lower fees)
- Sharpe ratio of live execution should improve vs backtest gap
- The Black-Litterman uncertainty parameter `tau` will be more meaningful

---

## Validation test

After implementing, run:
```python
from sklearn.covariance import LedoitWolf
import numpy as np

# Should print a shrinkage value between 0 and 1
# Near 0 = data was clean, near 1 = heavy shrinkage applied
lw = LedoitWolf()
lw.fit(np.random.randn(252, 50))
print(f"Shrinkage factor: {lw.shrinkage_:.3f}")
```
