# J3 — Wire Kelly Sizing Into Order Generation
# Edit `engine/execution/order_manager.py`
# Estimated time: 2 hours. No new dependencies, no new tables — the data already exists.

---

## The problem this closes

`price_targets` table already has a `kelly_half` column (confirmed added in
Session 5 of `todos/fix.md`, via `migrate_kelly_half.py`), and
`get_latest_targets()` already returns it to the Risk page for display. But
I checked `order_manager.py` directly — `generate_order_queue()` computes
order size purely as `delta_w * total_portfolio_eur`. Kelly is displayed on
a page but has **zero effect on actual order sizing**. You built the
plumbing and never connected the last pipe.

This is Gap 5 in `BRAINSTORM-new-features-and-gaps.md` — flagged, speced at
a conceptual level, never wired in.

---

## Design

Layer a Kelly scalar on top of the BL optimizer's output, the same way
`BRAINSTORM-new-features-and-gaps.md` originally proposed:

```
final_order_size = optimizer_delta_eur × kelly_scalar × regime_scalar
```

Where:
- `kelly_scalar` = `kelly_half` from `price_targets`, clipped to a sane range
  (Kelly formulas can spit out garbage — negative, >1, or NaN — when
  `up_proba` is near 0.5 or historical win-rate data is thin; never trust it
  raw)
- `regime_scalar` = 0.6 in Risk-Off, 1.0 in Risk-On/Neutral (you already
  compute regime state in `shared/state/regime_state.json` — reuse it, don't
  recompute)

**Important distinction from the BL optimizer's own position caps:** BL's
`MAX_POSITION` (10%) is a hard ceiling on the *target weight itself*. Kelly
here scales the *size of the trade needed to reach that target*, not the
target. This means Kelly won't stop you from reaching a 10% BL-suggested
position — it just slows down *how aggressively you buy into it in one
rebalance*, spreading conviction-building over several cycles instead of
one lump trade. That's the correct behavior: Kelly is a bet-sizing signal
about confidence in the edge, not a portfolio-construction constraint (BL
already handles construction).

---

## Implementation

### Step 1 — Fetch Kelly + regime scalars in `order_manager.py`

```python
# engine/execution/order_manager.py

def get_kelly_scalars(tickers: list) -> dict:
    """
    Fetches kelly_half per ticker from the latest price_targets row.
    Clips to [0.1, 1.0] — never let Kelly increase size beyond the
    optimizer's own suggestion (that's what MAX_POSITION already governs),
    and never let it zero out a trade entirely (0.1 floor keeps small
    rebalancing trades flowing even on low-confidence signals).
    """
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        rows = session.execute(text(f"""
            SELECT ticker, kelly_half
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
            AND ticker IN ({placeholders})
        """), params).fetchall()
    finally:
        session.close()

    scalars = {}
    for ticker, kelly_half in rows:
        if kelly_half is None or kelly_half != kelly_half:  # NaN check
            scalars[ticker] = 0.5   # neutral default when data is missing
            continue
        scalars[ticker] = max(0.1, min(1.0, float(kelly_half)))
    return scalars


def get_regime_scalar() -> float:
    """Reads current risk regime and returns a sizing multiplier."""
    try:
        import json
        from shared.state_paths import REGIME_STATE_PATH
        with open(REGIME_STATE_PATH) as f:
            state = json.load(f)
        risk = state.get('regime_risk', 'Neutral').lower()
        return 0.6 if 'risk-off' in risk or 'risk_off' in risk else 1.0
    except Exception as e:
        logger.warning(f"[kelly_sizing] regime read failed, defaulting to 1.0: {e}")
        return 1.0
```

### Step 2 — Apply scalars inside `generate_order_queue()`

Insert this **after** the ADV liquidity gate (Kelly should scale the
already-liquidity-capped size, not fight it) and **before** appending to
`orders`:

```python
def generate_order_queue(
    suggested_weights: pd.Series,
    current_weights: pd.Series,
    total_portfolio_eur: float,
    min_trade_eur: float = 25.0,
    adv_limit_pct: float = 0.05,
    apply_kelly_sizing: bool = True,   # NEW — allow disabling for sandbox comparison
) -> list:
    orders = []

    # NEW — fetch scalars once, outside the loop
    kelly_scalars = get_kelly_scalars(list(suggested_weights.index)) if apply_kelly_sizing else {}
    regime_scalar = get_regime_scalar() if apply_kelly_sizing else 1.0

    for ticker in suggested_weights.index:
        target_w  = float(suggested_weights.get(ticker, 0))
        current_w = float(current_weights.get(ticker, 0))
        delta_w   = target_w - current_w
        delta_eur = delta_w * total_portfolio_eur

        if abs(delta_eur) < min_trade_eur:
            continue

        if delta_w > 0:
            drift_pct = delta_w / target_w if target_w > 0 else 0
            if drift_pct < abs(DRIFT_THRESHOLD_BUY):
                continue
        elif delta_w < 0:
            drift_pct = abs(delta_w) / current_w if current_w > 0 else 0
            if drift_pct < DRIFT_THRESHOLD_SELL:
                continue

        abs_delta_eur = abs(delta_eur)

        adv_eur = get_adv_eur(ticker)
        max_order_eur = adv_eur * adv_limit_pct
        if abs_delta_eur > max_order_eur:
            logger.warning(f"[Liquidity Gate] {ticker} order capped at {adv_limit_pct*100}% ADV")
            abs_delta_eur = max_order_eur

        # NEW — Kelly + regime sizing scalar (BUYS ONLY — never shrink a sell,
        # since a smaller sell just delays reaching the BL target on the way DOWN,
        # which fights risk reduction rather than helping it)
        action = "BUY" if delta_eur > 0 else "SELL"
        if action == "BUY" and apply_kelly_sizing:
            k_scalar = kelly_scalars.get(ticker, 0.5)
            combined_scalar = k_scalar * regime_scalar
            original_eur = abs_delta_eur
            abs_delta_eur = abs_delta_eur * combined_scalar
            if abs_delta_eur < min_trade_eur:
                continue  # scaled below the floor — skip entirely rather than send a dust order
            logger.info(
                f"[Kelly Sizing] {ticker}: €{original_eur:,.0f} -> €{abs_delta_eur:,.0f} "
                f"(kelly={k_scalar:.2f}, regime={regime_scalar:.2f})"
            )

        orders.append(Order(
            ticker=ticker, action=action, value_eur=abs_delta_eur
        ))

    orders.sort(key=lambda o: abs(o.value_eur), reverse=True)
    logger.info(f"Order queue: {len(orders)} orders generated (tolerance bands, ADV gating, Kelly sizing applied)")
    return orders
```

### Step 3 — Surface it on `rebalance.html`

Show the Kelly scalar next to each BUY order so it's not a silent haircut —
same transparency principle as I2's signal breakdown:

```
BUY €3,200 of NVDA  (BL suggested €6,300 — scaled to 51% by Kelly½ + regime)
```

---

## Tuning notes

- Starting with **buys only** is deliberate — see the comment in Step 2.
  If you later want Kelly to also throttle sell *urgency*, that should be a
  separate, explicit decision, not a side effect of this change.
- The 0.5 neutral default when `kelly_half` is missing avoids silently
  killing trades for tickers your ML model hasn't scored yet (e.g. new
  additions to the universe with no signal history) — better to trade them
  at half-conviction than not at all, since BL already decided they belong
  in the target portfolio.
- Test this in `SANDBOX_MODE` (I4 sandbox gate, already built) with
  `apply_kelly_sizing=True` vs `False` for a couple of weeks and compare —
  the whole point of I4 existing is to validate exactly this kind of sizing
  change before it touches real capital.
