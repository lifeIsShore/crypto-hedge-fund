# J2 — Tax-Aware Selling (Abgeltungsteuer Penalty)
# Add to `engine/portfolio/optimizer.py` + `engine/execution/order_manager.py`
# Estimated time: 4 hours. No new dependencies.

---

## The problem this closes

Germany applies a flat ~26.375% capital gains tax (`Abgeltungsteuer` +
solidarity surcharge) the moment a position with an unrealized gain is sold —
there is no long-term holding exemption like the US or UK. Right now,
`optimize_with_bl()` treats a sell of a position up 40% and a sell of a
position down 5% identically. If the optimizer trims a winner to fund a
marginally-higher-alpha buy elsewhere, you eat a permanent ~26% tax drag on
the realized gain that the model never saw or accounted for.

This is fully speced in `improvements.md` #1 ("Tax-Aware Selling
Optimization") and mentioned again in `BRAINSTORM-new-features-and-gaps.md`
Phase 4 item 4, but `optimizer.py` has no tax logic anywhere — checked
directly, confirmed not implemented.

---

## Design

Add a tax-drag penalty to the optimizer's objective function, proportional to
the *estimated realized tax liability* of trimming each position, using the
weighted-average cost basis you already compute in
`engine/risk/circuit_breaker.py`'s `get_average_entry_prices()` (built for
I3 — reuse it here rather than re-deriving cost basis a second way).

```
tax_penalty_i = max(0, current_price_i - cost_basis_i) × 0.26375 × sell_amount_i
```

Only applies to **sells below current holding weight** — buys and holds are
unaffected. The optimizer will now only trim a winning position when the
alpha gap to the replacement asset is large enough to survive the tax
haircut, not just marginally higher.

---

## Implementation

### Step 1 — Reuse cost basis from `circuit_breaker.py`

```python
# engine/portfolio/optimizer.py
from engine.risk.circuit_breaker import get_average_entry_prices

TAX_RATE = 0.26375  # Abgeltungsteuer + Soli, flat rate, no long-term exemption in Germany
```

### Step 2 — Add the tax penalty term to the objective function

```python
def optimize_with_bl(
    mu_bl: pd.Series,
    cov_matrix: pd.DataFrame,
    current_weights: pd.Series,
    current_prices: pd.Series,          # NEW — needed to compute unrealized gain
    portfolio_value: float,             # NEW — to convert weight deltas to EUR
    sector_map: dict = None,
    risk_aversion: float = 2.5,
    apply_tax_penalty: bool = True,     # allow disabling for sandbox/backtests
) -> pd.Series:
    tickers = mu_bl.index.tolist()
    n = len(tickers)

    w0 = np.array([current_weights.get(t, 0.0) for t in tickers])
    mu = mu_bl.values
    Sigma = cov_matrix.loc[tickers, tickers].values

    # NEW — cost basis and unrealized gain per ticker
    if apply_tax_penalty:
        entry_prices = get_average_entry_prices()  # {ticker: weighted_avg_cost}
        unrealized_gain_pct = np.array([
            max(0.0, (current_prices.get(t, 0) - entry_prices.get(t, current_prices.get(t, 0)))
                / entry_prices.get(t, current_prices.get(t, 1)))
            if entry_prices.get(t) else 0.0
            for t in tickers
        ])
    else:
        unrealized_gain_pct = np.zeros(n)

    def objective(w):
        ret       = np.dot(mu, w)
        risk      = 0.5 * risk_aversion * w @ Sigma @ w
        delta_w   = w - w0
        turnover  = TURNOVER_PENALTY * np.sum(np.abs(delta_w))
        costs     = SLIPPAGE_PCT * np.sum(np.abs(delta_w))

        # NEW — tax drag: only penalize SELLS (delta_w < 0) of positions with unrealized gains
        sell_amounts = np.clip(-delta_w, 0, None)  # positive only where we're trimming
        tax_drag = np.sum(sell_amounts * unrealized_gain_pct * TAX_RATE)

        return -(ret - risk - turnover - costs - tax_drag)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if sector_map:
        constraints += build_sector_constraints(tickers, sector_map)

    bounds = [(0, MAX_POSITION)] * n

    result = minimize(
        objective, x0=w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9}
    )
    # ... rest unchanged
```

### Step 3 — Update the caller in `engine/scheduler.py`

`step_portfolio_construction()` already fetches current prices for the
circuit breaker check (I3) — pass the same `current_prices` Series and
`portfolio_value` through to `optimize_with_bl()`:

```python
suggested_weights = optimize_with_bl(
    mu_bl, cov_matrix, current_weights,
    current_prices=latest_prices,        # already fetched for I3
    portfolio_value=total_portfolio_value,
    sector_map=TICKER_SECTORS,
)
```

### Step 4 — Surface the tax cost on `rebalance.html`

For every suggested sell, show the estimated tax hit next to the trade —
this is the single most useful piece of information for you to review before
clicking approve, since the optimizer's penalty is a soft nudge, not a hard
block, and you may still want to override it for other reasons (e.g. hitting
a circuit breaker, which should always fire regardless of tax).

```
SELL €5,340 of MSF.DE  (unrealized gain: +34.2%)
  → Estimated tax on this sale: ~€480 (26.375% of realized gain)
  → Net proceeds after tax: ~€4,860
```

Compute this inline in the `/api/rebalance` Flask route using the same
`get_average_entry_prices()` call, alongside the existing `signal_breakdown`
JSON from I2.

---

## Important: don't let this fight the circuit breaker

I3's circuit breaker (`circuit_breaker.py`) forces a position to 0% weight
on a stop-loss breach *before* the optimizer runs — that logic is untouched
by this change and takes priority. The tax penalty only affects the
optimizer's own discretionary trim decisions, never a forced stop-loss exit
(you don't want tax considerations delaying an emergency exit — a stop-loss
sale is virtually never at a gain anyway, so the penalty term would be ~0 in
that case regardless).

## Tuning notes

- `TAX_RATE = 0.26375` assumes the standard German flat rate with church tax
  *not* included (add ~8–9% relative increase to the rate if you pay church
  tax — check your own `Kirchensteuer` status and adjust).
- If Germany's tax-loss carryforward rules matter to you (losses from one
  position can offset gains from another within the same tax year), that's a
  materially bigger feature — a full `tax_lot_optimizer.py` that batches sells
  within a tax year to net gains against losses. Worth doing eventually but
  don't build it into this first pass; the per-trade penalty above already
  captures 80% of the value for a fraction of the complexity.
- This is unrelated to but complements the sandbox paper-trading gate (I4,
  already done) — test with `apply_tax_penalty=True` in sandbox mode for a
  few weeks before trusting the live weights it produces.
