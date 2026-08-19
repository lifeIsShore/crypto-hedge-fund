> **STATUS (2026-08-20, written by Claude): NOT IMPLEMENTED.** Design doc only.
> Read-time UI feature only — no DB or strategy changes. The optimizer, ML
> pipeline, risk engine, and everything else stays in EUR internally. This
> is purely a presentation layer concern.

# USD Display Toggle
# `templates/base.html` · `flask_app.py` · `engine/data/fx_utils.py` (new)
# Estimated time: 0.5 day

---

## What this does

Adds a **EUR / USD toggle** to the dashboard footer (the single `CURRENCY EUR`
status strip in `base.html` line 370) that converts displayed prices across all
pages at read time. The DB, optimizer, and every internal calculation remain
in EUR — this is a *view-layer* conversion only, applied in JavaScript client-side
using a rate from the `fx_rates` table.

**What changes:**
- `CURRENCY EUR` label becomes a clickable `EUR | USD` pill toggle
- Prices, values, P&L, targets, stop levels on all pages reformat to the
  selected currency on toggle (no page reload — JS-based)
- A new `/api/fx_rate` endpoint serves the latest `USDEUR` rate from the
  `fx_rates` table (already populated daily by ingestion)
- A small `localStorage` key (`currency_display`) remembers preference across
  sessions
- Labels that read "EUR" (kpi-sub lines, column headers, panel badges) update
  to "USD" dynamically
- A subtle `(~)` indicator appears next to USD prices to signal "converted
  from EUR using yesterday's FX close" — important transparency signal for
  names where USD matters most (the cross-listings)

**What does NOT change:**
- DB schema — `prices` stays in EUR, `fx_rates` table unchanged
- Optimizer, features, ML pipeline, risk engine — all still EUR
- Trade execution values logged in EUR (EUR is the base currency of the
  Trade Republic account — these are real settlement amounts)
- Any US-native ticker that currently shows a price that was already fetched
  in USD and converted to EUR at ingestion time will show *that converted EUR
  value reconverted to USD* — which is slightly lossy but unavoidable at
  display-only time. See "Limitations" below.

---

## New API endpoint

Add to `flask_app.py`:

```python
@app.route("/api/fx_rate")
def api_fx_rate():
    """Latest USDEUR and GBPEUR rates for client-side currency display toggle."""
    return jsonify({
        "USDEUR": _get_latest_fx_rate("USDEUR"),
        "GBPEUR": _get_latest_fx_rate("GBPEUR"),
        "date":   _q("SELECT date FROM fx_rates ORDER BY date DESC LIMIT 1")[0]["date"]
                  if _q("SELECT date FROM fx_rates ORDER BY date DESC LIMIT 1") else None,
    })
```

`_get_latest_fx_rate()` already exists in `flask_app.py` (line 115) — this
endpoint just exposes it. No new DB queries.

---

## Frontend changes

### `templates/base.html` — toggle pill

Replace the static status strip line (currently line 370):

```html
<!-- BEFORE -->
<div class="status-item">CURRENCY <span>EUR</span></div>

<!-- AFTER -->
<div class="status-item" id="currency-toggle-wrap">
  CURRENCY
  <button id="currency-toggle" class="currency-pill" title="Toggle display currency">
    <span id="currency-eur-label" class="active">EUR</span>
    <span class="pill-sep">/</span>
    <span id="currency-usd-label">USD</span>
  </button>
</div>
```

Minimal CSS (add to base.html `<style>` block):

```css
.currency-pill {
  background: none; border: 1px solid rgba(255,255,255,0.25);
  border-radius: 12px; padding: 1px 8px; cursor: pointer;
  color: inherit; font-size: 0.75rem; letter-spacing: 0.05em;
}
.currency-pill .active { font-weight: 700; text-decoration: underline; }
.currency-pill .pill-sep { opacity: 0.4; margin: 0 3px; }
```

### `templates/base.html` — JavaScript (add to end of `<body>`)

```javascript
// ── Currency Display Toggle ────────────────────────────────────────────────
(function() {
  // Rate fetched once per page load from /api/fx_rate
  let EUR_TO_USD = null;
  let displayCurrency = localStorage.getItem('currency_display') || 'EUR';

  // Elements tagged with data-eur="<float>" hold the EUR source value.
  // The toggle reconverts these without touching the DOM's source truth.
  function _fmtEUR(v, decimals) {
    return v.toFixed(decimals !== undefined ? decimals : 2);
  }
  function _fmtUSD(v, decimals) {
    return (v * (1 / EUR_TO_USD)).toFixed(decimals !== undefined ? decimals : 2);
  }

  function applyDisplayCurrency(currency) {
    if (currency === 'USD' && EUR_TO_USD === null) return; // rate not loaded yet

    document.querySelectorAll('[data-eur]').forEach(el => {
      const eurVal = parseFloat(el.dataset.eur);
      if (isNaN(eurVal)) return;
      const decimals = parseInt(el.dataset.decimals || '2', 10);
      const prefix   = currency === 'USD' ? '$' : '€';
      const val      = currency === 'USD' ? _fmtUSD(eurVal, decimals) : _fmtEUR(eurVal, decimals);
      // Preserve any suffix (tilde indicator) from prior runs
      el.textContent = prefix + val + (currency === 'USD' ? ' ~' : '');
    });

    // Update "EUR" text labels (kpi-sub, panel badges, column headers)
    document.querySelectorAll('[data-currency-label]').forEach(el => {
      el.textContent = currency === 'USD' ? 'USD ~' : 'EUR';
    });

    // Toggle pill active state
    document.getElementById('currency-eur-label')?.classList.toggle('active', currency === 'EUR');
    document.getElementById('currency-usd-label')?.classList.toggle('active', currency === 'USD');
  }

  // Fetch rate then apply stored preference
  fetch('/api/fx_rate')
    .then(r => r.json())
    .then(data => {
      EUR_TO_USD = data.USDEUR; // USDEUR = how many USD per 1 EUR
      // Wait: USDEUR in our DB is "how many EUR per 1 USD" (USDEUR rate = 0.92).
      // So EUR→USD = 1 / USDEUR rate. Confirmed in ingestion.py: USDEUR pair,
      // inverted from EURUSD=X, so USDEUR = 0.92 means $1 = €0.92.
      // EUR→USD conversion: price_usd = price_eur / USDEUR_rate = price_eur * (1/0.92)
      applyDisplayCurrency(displayCurrency);
    })
    .catch(() => { /* silently degrade to EUR on fetch error */ });

  document.getElementById('currency-toggle')?.addEventListener('click', () => {
    displayCurrency = displayCurrency === 'EUR' ? 'USD' : 'EUR';
    localStorage.setItem('currency_display', displayCurrency);
    applyDisplayCurrency(displayCurrency);
  });
})();
```

### Per-page template changes — tagging EUR values

Each template that displays EUR prices needs its numeric spans tagged with
`data-eur="<value>"` and its label spans tagged with `data-currency-label`.

This is the only repetitive part. The pattern is identical across pages:

**Before** (example from `overview.html`):
```html
<div class="kpi-value" id="kpi-total">—</div>
<div class="kpi-sub">EUR · all positions</div>
```

**After** (JS still fills `kpi-total`; also sets `data-eur` for the toggle):
```html
<div class="kpi-value" id="kpi-total" data-eur="" data-decimals="0">—</div>
<div class="kpi-sub" data-currency-label>EUR · all positions</div>
```

The JS that already populates these KPIs (in each page's inline `<script>`)
needs one extra line alongside wherever it sets `textContent`:
```javascript
el.dataset.eur = rawEurValue; // set the source truth for toggle
```

**Pages to update** (all minor, same 2-line pattern each):
- `overview.html` — portfolio total, cash
- `holdings.html` — portfolio total, per-position value, price
- `risk.html` — current price, price targets, stop levels
- `ticker_detail.html` — current price, position value, targets
- `analytics.html` — P&L, values
- `history.html` — trade price column, trade total column
- `lab.html` — allocation table EUR values

---

## What `data-eur` must NOT tag

- Weights (%) — these are dimensionless, no toggle needed
- Returns (%) — same
- Dates, labels, counts — obvious
- The `€` prefix on statically server-rendered Jinja values (e.g.
  `ticker_detail.html` line 33 `'€%.2f'|format(...)`) — these need to be
  converted to JS-rendered spans instead, which is a small refactor but
  necessary for the toggle to work on them

---

## Limitations — document these visibly in the UI tooltip

1. **Double conversion for cross-listed names**: A `.DE` ticker's price was
   already the Xetra EUR close at ingestion time. Multiplying by EUR/USD to
   show "USD" gives a synthetic number — it's what you'd pay in USD for the
   EUR-priced Xetra share, not the actual NYSE/NASDAQ close price. This is
   inherent to "display-only" conversion. Once the cross-listing basis scanner
   (`NEW-crosslisting-basis-scanner.md`) stores native US closes, that data
   should be shown separately — not merged into this toggle.

2. **FX rate is yesterday's close**: Intraday moves in EUR/USD are not reflected.
   The `~` indicator communicates this.

3. **Trade history stays in EUR**: EUR is the true settlement currency of the
   Trade Republic account. Converting historical trade values to USD is
   misleading (you didn't pay in USD). Consider leaving the history page in EUR
   always, or adding a stronger disclaimer there.

---

## Explicitly out of scope

- No change to DB storage (all prices stay EUR)
- No change to optimizer, ML, or risk logic
- No GBP display option (not needed — GBP-listed names are already EUR-converted
  at ingestion, no meaningful GBP display makes sense)
- No live FX intraday rate (not needed for EOD pipeline)
- No USD-denominated portfolio tracking (the portfolio IS a EUR account)
