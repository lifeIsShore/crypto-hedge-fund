# H6: Tolerance Bands — Stop Over-Trading
**High Priority | File: `engine/execution/order_manager.py` + `engine/portfolio/optimizer.py`**

---

## What is wrong

`generate_order_queue()` in `order_manager.py` generates a trade order any time
`abs(delta_eur) >= min_trade_eur` (currently €25). This means:

- If NVDA drifts from 8.00% to 8.15% of portfolio, a rebalance order is generated
- Every pipeline run will produce small "noise" orders from normal price fluctuation
- You execute these trades manually on Trade Republic at €1/trade — a 0.15%
  weight adjustment that costs €1 in fees is pure fee drag, no alpha

The optimizer itself has a `TURNOVER_PENALTY` and `SLIPPAGE_PCT` in its objective
function, but these are applied during optimization as soft penalties — they do
not hard-block small orders from appearing in the queue.

Your own `config.py` already defines the right concept:
```python
DRIFT_THRESHOLD_BUY  = -0.05   # -5% below target
DRIFT_THRESHOLD_SELL =  0.07   # +7% above target
```
But these thresholds are **never used** by `generate_order_queue()`.

---

## Fix

### Part 1 — Wire `config.py` thresholds into order generation

In `engine/execution/order_manager.py`, update `generate_order_queue()`:

```python
from portfolio.src.config import DRIFT_THRESHOLD_BUY, DRIFT_THRESHOLD_SELL

def generate_order_queue(
    suggested_weights: pd.Series,
    current_weights: pd.Series,
    total_portfolio_eur: float,
    min_trade_eur: float = 25.0,
) -> list:
    orders = []
    for ticker in suggested_weights.index:
        target_w  = float(suggested_weights.get(ticker, 0))
        current_w = float(current_weights.get(ticker, 0))
        delta_w   = target_w - current_w
        delta_eur = delta_w * total_portfolio_eur

        # Hard size floor
        if abs(delta_eur) < min_trade_eur:
            continue

        # Tolerance band check — asymmetric (let winners run, cut losers faster)
        # BUY: only if we are more than 5% BELOW target weight
        # SELL: only if we are more than 7% ABOVE target weight
        # "5% below" means delta_w > +0.05 * target_w
        if delta_w > 0:   # BUY signal
            drift_pct = delta_w / target_w if target_w > 0 else 0
            if drift_pct < abs(DRIFT_THRESHOLD_BUY):   # e.g. < 5% below target
                continue
        elif delta_w < 0:  # SELL signal
            drift_pct = abs(delta_w) / current_w if current_w > 0 else 0
            if drift_pct < DRIFT_THRESHOLD_SELL:       # e.g. < 7% above target
                continue

        action = "BUY" if delta_eur > 0 else "SELL"
        orders.append(Order(ticker=ticker, action=action, value_eur=abs(delta_eur)))

    orders.sort(key=lambda o: abs(o.value_eur), reverse=True)
    logger.info(f"Order queue: {len(orders)} orders generated (tolerance bands applied)")
    return orders
```

### Part 2 — Add minimum delta-weight floor in optimizer

In `engine/portfolio/optimizer.py`, after the optimization result, zero out
weights that are within a minimum threshold of current weights to prevent
micro-rebalancing noise:

```python
# After: weights = pd.Series(np.round(result.x, 4), index=tickers)
# Add:
MIN_DELTA_WEIGHT = 0.005  # 0.5% minimum meaningful weight change

for ticker in tickers:
    current = current_weights.get(ticker, 0.0)
    suggested = weights[ticker]
    if abs(suggested - current) < MIN_DELTA_WEIGHT:
        weights[ticker] = current  # snap back to current — not worth trading
```

---

## Expected impact

Running your pipeline daily will generate maybe 2-4 genuine orders per week
instead of 10-20 micro-adjustments. Estimated fee savings: €20-50/month
depending on portfolio size. More importantly, your manual review time drops
significantly.

---

## Configuration note

The thresholds in `config.py` can be tuned:
```python
DRIFT_THRESHOLD_BUY  = -0.05  # Tighter — captures underweight positions faster
DRIFT_THRESHOLD_SELL =  0.07  # Looser — lets winners run (tax-efficient)
```
Document any changes in `portfolio/docs/03-TUNING-LOG.md` as the comments suggest.
