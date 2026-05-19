# I2: Signal Explainability on Rebalance Page
**Improvement (post go-live) | Files: `engine/scheduler.py`, `engine/db/schema.sql`, `templates/rebalance.html`**

---

## Overview

Currently, the rebalance page shows:
```
NVDA   current: 4.2%   suggested: 7.1%   delta: +2.9%   BL return: 0.032
```

There is no explanation of *why* the system is suggesting this trade. Is it
driven by momentum? Mean reversion? ML signal? The current regime? As the human
in the loop, you need this to make an informed override decision.

Your own `improvements.md` and `fix-before.md` both flag this:
> "The Explainability: The trade suggestions (Delta Weights) are presented as
> raw numbers. There is no 'Why' (e.g., 'Driven by Momentum and VIX expansion')"

---

## Implementation Plan

### Step 1 — Extend `model_outputs` table schema

Add a `signal_breakdown` column to store the top contributing alpha signals:

```sql
ALTER TABLE model_outputs ADD COLUMN signal_breakdown TEXT;
-- TEXT column stores JSON: [{"model": "momentum", "contribution": 0.42}, ...]
```

Add this to `schema.sql` as well (with `IF NOT EXISTS` guard via the ALTER or
a new migration):
```sql
-- In schema.sql, update model_outputs definition:
CREATE TABLE IF NOT EXISTS model_outputs (
    date             TEXT        NOT NULL,
    ticker           TEXT        NOT NULL,
    suggested_weight REAL,
    current_weight   REAL,
    delta_weight     REAL,
    expected_return  REAL,
    bl_return        REAL,
    signal_breakdown TEXT,       -- JSON: top contributing signals
    computed_at      TEXT        DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);
```

### Step 2 — Compute signal breakdown in Black-Litterman

In `engine/portfolio/black_litterman.py`, after computing views per model,
record the proportional contribution of each alpha signal to the final BL return:

```python
# After computing mu_bl (the final posterior expected returns):
signal_breakdown = {}
for ticker in tickers:
    contributions = {}
    total_abs = 0
    for model_name, model_signals in all_model_signals.items():
        sig = float(model_signals.get(ticker, 0))
        contributions[model_name] = sig
        total_abs += abs(sig)
    # Normalize to percentage contribution
    if total_abs > 0:
        signal_breakdown[ticker] = {
            k: round(abs(v) / total_abs * 100, 1)
            for k, v in sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)
        }
```

Then pass `signal_breakdown` to `persist_model_outputs()` and store as JSON.

### Step 3 — Update `persist_model_outputs()` in `optimizer.py`

```python
def persist_model_outputs(date, suggested, current, mu_bl, signal_breakdown=None):
    session = get_session()
    try:
        for ticker in suggested.index:
            breakdown_json = json.dumps(
                signal_breakdown.get(ticker, {}) if signal_breakdown else {}
            )
            session.execute(text("""
                INSERT INTO model_outputs
                    (date, ticker, suggested_weight, current_weight, delta_weight,
                     bl_return, signal_breakdown, computed_at)
                VALUES (:date, :ticker, :suggested, :current, :delta,
                        :bl_return, :breakdown, datetime('now'))
                ON CONFLICT (date, ticker) DO UPDATE SET
                    suggested_weight = :suggested,
                    delta_weight     = :delta,
                    bl_return        = :bl_return,
                    signal_breakdown = :breakdown,
                    computed_at      = datetime('now')
            """), {
                "date": date, "ticker": ticker,
                "suggested": float(suggested.get(ticker, 0)),
                "current": float(current.get(ticker, 0)),
                "delta": float(suggested.get(ticker, 0)) - float(current.get(ticker, 0)),
                "bl_return": float(mu_bl.get(ticker, 0)),
                "breakdown": breakdown_json,
            })
        session.commit()
    finally:
        session.close()
```

### Step 4 — Display on `rebalance.html`

In the rebalance table, add a "Why" column that parses `signal_breakdown` JSON
and renders the top 2 signals as colored tags:

```html
<!-- In the table header -->
<th>Why</th>

<!-- In each table row, in the Jinja template -->
{% if row.signal_breakdown %}
  {% set breakdown = row.signal_breakdown | fromjson %}
  {% for signal, pct in breakdown.items() | list | sort(attribute='1', reverse=True) | first(2) %}
    <span class="signal-tag signal-{{ signal }}">
      {{ signal | replace('_', ' ') | title }} {{ pct }}%
    </span>
  {% endfor %}
{% endif %}
```

Add CSS for the signal tags:
```css
.signal-tag {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    margin: 1px;
    font-weight: 500;
}
.signal-momentum     { background: rgba(0,229,160,0.15); color: var(--accent); }
.signal-mean-reversion { background: rgba(245,166,35,0.15); color: var(--accent-yellow); }
.signal-ml-model     { background: rgba(99,102,241,0.15); color: #818cf8; }
.signal-pead         { background: rgba(59,130,246,0.15); color: #60a5fa; }
.signal-vol-timing   { background: rgba(255,77,106,0.15); color: var(--accent-red); }
```

---

## Result

Rebalance page will show:
```
NVDA  +2.9%  [Momentum 58%] [ML Model 31%]    BL: 0.032
SAP   -1.2%  [Mean Reversion 71%] [PEAD 22%]  BL: -0.008
```

You can now see at a glance whether a BUY is conviction-driven (multiple models
agree) or noise-driven (only one weak model), making override decisions
data-driven rather than instinct-driven.
