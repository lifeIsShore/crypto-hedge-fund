> **STATUS (2026-08-09): SPEC UPDATED per user request, then IMPLEMENTED — see PROJECT-STATE.md
> session-4 changelog entry.** Original version of this doc hardcoded a single
> German tax rate. Reworked below into a jurisdiction-selectable settings
> feature per your request, then built for real: `tax_settings` table,
> `engine/portfolio/tax_rates.py`, `/settings` page, and the optimizer wiring
> all exist in the live codebase. This doc is kept as design rationale.

# J2 — Tax-Aware Selling (Jurisdiction-Selectable Capital Gains Rate)
# `engine/portfolio/tax_rates.py` (new) + edits to `optimizer.py` / `flask_app.py`
# Estimated time: 1 day (up from the original 4 hours — the settings UI is the
# added scope). No new dependencies.

---

## Why jurisdiction-selectable, not hardcoded

Original version of this doc hardcoded `TAX_RATE = 0.26375` (German
Abgeltungsteuer + Soli). That's wrong to hardcode for two reasons you raised:
1. Different jurisdictions tax capital gains completely differently — not
   just a different flat number, but different *systems* (flat tax vs.
   progressive brackets vs. holding-period exemptions vs. no capital gains
   tax at all for private investors).
2. You may want to model a different jurisdiction later (a second account,
   a move, a "what if" scenario) without editing Python code each time.

**Design: a settings-driven jurisdiction selector, stored in the DB, with a
"Custom" escape hatch** for anything the presets don't cover exactly (your
personal `Kirchensteuer` status, a jurisdiction not in the preset list, or a
progressive system you want to approximate with your own effective rate).

---

## An important caveat on progressive-tax jurisdictions

Some jurisdictions (US, UK) don't have a single flat capital-gains rate —
US federal rates depend on income bracket and holding period (short vs.
long-term), UK has an annual tax-free allowance plus banded rates. **A flat
percentage can only ever approximate these.** The preset list below marks
these clearly as "approximate — use Custom for precision" rather than
presenting a false sense of exactness. For flat-tax jurisdictions (most of
continental Europe), the preset is the actual legal rate, not an
approximation.

---

## Preset jurisdiction table

| Jurisdiction | Rate | System | Notes |
|---|---|---|---|
| Germany (Abgeltungsteuer) | 26.375% | Flat | Excludes optional `Kirchensteuer` (+~8-9% relative) — use Custom if you pay church tax |
| Austria (KESt) | 27.5% | Flat | |
| France (Prélèvement Forfaitaire Unique) | 30.0% | Flat | Includes social charges |
| Belgium | 0% | Flat (private investors) | Belgium generally doesn't tax private capital gains on shares — verify your specific situation |
| Netherlands (Box 3) | — | Wealth tax, not capital gains | Taxes a *deemed* return on total assets, not realized gains — this whole tax-drag model doesn't map cleanly onto Box 3. Use Custom with 0% and treat NL wealth tax as a separate, non-per-trade cost if this applies to you |
| Switzerland | 0% | Exempt (private investors) | Private capital gains are generally tax-free for non-professional investors |
| United Kingdom (CGT) | 20% | Progressive + annual allowance | **Approximate.** Real UK CGT has a tax-free allowance (which shrinks the flat-rate approximation error at low gains) and a 10%/20% band split by income. Use Custom to enter your actual effective rate. |
| United States (federal, long-term) | 15% | Progressive by income + holding period | **Approximate.** Real US rates range 0/15/20% federal by income bracket, short-term gains taxed as ordinary income, plus state tax on top. Use Custom. |
| No tax modeling (disable) | 0% | — | Turns the tax-drag penalty off entirely — optimizer behaves exactly as it did before this feature existed |
| **Custom** | *user-entered* | — | Free-entry percentage, for anything above that needs correction, or a jurisdiction not listed |

---

## Implementation

### Step 1 — Settings table

```sql
CREATE TABLE IF NOT EXISTS tax_settings (
    id           INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    jurisdiction TEXT NOT NULL DEFAULT 'germany',
    tax_rate     REAL NOT NULL DEFAULT 0.26375,        -- the ACTIVE rate, whatever the source
    custom_rate  REAL,                                  -- only used when jurisdiction = 'custom'
    updated_at   TEXT DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO tax_settings (id, jurisdiction, tax_rate) VALUES (1, 'germany', 0.26375);
```

`tax_rate` is always the number actually used by the optimizer — when a
preset jurisdiction is selected, `tax_rate` is set to that preset's value;
when `custom` is selected, `tax_rate` is set to whatever the user typed into
`custom_rate`. This keeps the optimizer's read path simple (`SELECT tax_rate
FROM tax_settings`) regardless of how it got there.

### Step 2 — `engine/portfolio/tax_rates.py` (new file)

```python
"""
Jurisdiction-selectable capital gains tax rates for the tax-aware
selling penalty in optimizer.py. See before-go-live/J2-tax-aware-selling.md.
"""
import logging
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

JURISDICTION_PRESETS = {
    'germany':      {'label': 'Germany (Abgeltungsteuer)',      'rate': 0.26375, 'approximate': False},
    'austria':      {'label': 'Austria (KESt)',                  'rate': 0.275,   'approximate': False},
    'france':       {'label': 'France (PFU)',                    'rate': 0.30,    'approximate': False},
    'belgium':      {'label': 'Belgium (private investors)',     'rate': 0.0,     'approximate': False},
    'switzerland':  {'label': 'Switzerland (private investors)', 'rate': 0.0,     'approximate': False},
    'uk':           {'label': 'United Kingdom (CGT)',            'rate': 0.20,    'approximate': True},
    'us':           {'label': 'United States (federal, LT)',     'rate': 0.15,    'approximate': True},
    'none':         {'label': 'No tax modeling (disabled)',      'rate': 0.0,     'approximate': False},
    'custom':       {'label': 'Custom',                          'rate': None,    'approximate': False},
}

DEFAULT_JURISDICTION = 'germany'


def ensure_tax_settings_table():
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS tax_settings (
                id           INTEGER PRIMARY KEY CHECK (id = 1),
                jurisdiction TEXT NOT NULL DEFAULT 'germany',
                tax_rate     REAL NOT NULL DEFAULT 0.26375,
                custom_rate  REAL,
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        """))
        session.execute(text("""
            INSERT OR IGNORE INTO tax_settings (id, jurisdiction, tax_rate)
            VALUES (1, :j, :r)
        """), {'j': DEFAULT_JURISDICTION, 'r': JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate']})
        session.commit()
    finally:
        session.close()


def get_active_tax_rate() -> float:
    """
    Reads the currently active tax rate. Called by optimizer.py on every
    portfolio construction run — cheap (single-row lookup), so no caching.
    Falls back to the German default if the table is missing or empty,
    never raises — a missing settings table should never crash the pipeline.
    """
    try:
        session = get_session()
        try:
            row = session.execute(text(
                "SELECT tax_rate FROM tax_settings WHERE id = 1"
            )).fetchone()
        finally:
            session.close()
        if row and row[0] is not None:
            return float(row[0])
    except Exception as e:
        logger.warning(f"[tax_rates] get_active_tax_rate failed, using default: {e}")
    return JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate']


def get_tax_settings() -> dict:
    """Returns the full current settings row, for the settings page."""
    ensure_tax_settings_table()
    session = get_session()
    try:
        row = session.execute(text(
            "SELECT jurisdiction, tax_rate, custom_rate FROM tax_settings WHERE id = 1"
        )).fetchone()
    finally:
        session.close()
    if not row:
        return {'jurisdiction': DEFAULT_JURISDICTION,
                'tax_rate': JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate'],
                'custom_rate': None}
    return {'jurisdiction': row[0], 'tax_rate': float(row[1]), 'custom_rate': row[2]}


def set_tax_jurisdiction(jurisdiction: str, custom_rate: float = None) -> dict:
    """
    Updates the active jurisdiction. If jurisdiction == 'custom', custom_rate
    is required and becomes the active tax_rate. Otherwise the preset's rate
    is used and custom_rate is stored alongside (but not used) so switching
    back to Custom later remembers the last value the user typed.
    """
    ensure_tax_settings_table()

    if jurisdiction not in JURISDICTION_PRESETS:
        raise ValueError(f"Unknown jurisdiction: {jurisdiction}")

    if jurisdiction == 'custom':
        if custom_rate is None:
            raise ValueError("custom_rate is required when jurisdiction='custom'")
        effective_rate = float(custom_rate)
    else:
        effective_rate = JURISDICTION_PRESETS[jurisdiction]['rate']

    session = get_session()
    try:
        session.execute(text("""
            UPDATE tax_settings SET
                jurisdiction = :j,
                tax_rate     = :rate,
                custom_rate  = COALESCE(:custom, custom_rate),
                updated_at   = datetime('now')
            WHERE id = 1
        """), {'j': jurisdiction, 'rate': effective_rate, 'custom': custom_rate})
        session.commit()
    finally:
        session.close()

    logger.info(f"[tax_rates] Jurisdiction set to '{jurisdiction}' — active rate {effective_rate:.4%}")
    return {'jurisdiction': jurisdiction, 'tax_rate': effective_rate}
```

### Step 3 — Reuse cost basis + wire the dynamic rate into the optimizer

Same objective-function shape as the original doc, but `TAX_RATE` is no
longer a module constant — it's read fresh each call via
`get_active_tax_rate()`:

```python
# engine/portfolio/optimizer.py
from engine.risk.circuit_breaker import get_average_entry_prices
from engine.portfolio.tax_rates import get_active_tax_rate

def optimize_with_bl(
    mu_bl: pd.Series,
    cov_matrix: pd.DataFrame,
    current_weights: pd.Series,
    current_prices: pd.Series = None,
    sector_map: dict = None,
    risk_aversion: float = 2.5,
    date: str = None,
    apply_cluster_constraint: bool = True,
    apply_tax_penalty: bool = True,
) -> pd.Series:
    tickers = mu_bl.index.tolist()
    n = len(tickers)
    w0 = np.array([current_weights.get(t, 0.0) for t in tickers])
    mu = mu_bl.values
    Sigma = cov_matrix.loc[tickers, tickers].values

    unrealized_gain_pct = np.zeros(n)
    tax_rate = 0.0
    if apply_tax_penalty and current_prices is not None:
        tax_rate = get_active_tax_rate()   # NEW — reads tax_settings table
        if tax_rate > 0:
            entry_prices = get_average_entry_prices()
            unrealized_gain_pct = np.array([
                max(0.0, (current_prices.get(t, 0) - entry_prices.get(t, current_prices.get(t, 0)))
                    / entry_prices.get(t, current_prices.get(t, 1)))
                if entry_prices.get(t) else 0.0
                for t in tickers
            ])

    def objective(w):
        ret       = np.dot(mu, w)
        risk      = 0.5 * risk_aversion * w @ Sigma @ w
        delta_w   = w - w0
        turnover  = TURNOVER_PENALTY * np.sum(np.abs(delta_w))
        costs     = SLIPPAGE_PCT * np.sum(np.abs(delta_w))
        sell_amounts = np.clip(-delta_w, 0, None)
        tax_drag  = np.sum(sell_amounts * unrealized_gain_pct * tax_rate)
        return -(ret - risk - turnover - costs - tax_drag)

    # ... constraints, bounds, minimize() unchanged from the J1 version
```

### Step 4 — `/settings` page (`flask_app.py` + `templates/settings.html`)

```python
# flask_app.py
from engine.portfolio.tax_rates import (
    JURISDICTION_PRESETS, get_tax_settings, set_tax_jurisdiction
)

@app.route("/settings")
def settings():
    tax = get_tax_settings()
    return render_template(
        "settings.html", page="settings",
        tax=tax, jurisdictions=JURISDICTION_PRESETS,
    )

@app.route("/api/tax_settings", methods=["GET"])
def api_tax_settings_get():
    return jsonify(get_tax_settings())

@app.route("/api/tax_settings", methods=["POST"])
@require_auth
def api_tax_settings_post():
    data = request.get_json()
    jurisdiction = data.get("jurisdiction")
    custom_rate = data.get("custom_rate")
    if custom_rate is not None:
        custom_rate = float(custom_rate) / 100.0   # UI sends a percent, e.g. 26.375
    try:
        result = set_tax_jurisdiction(jurisdiction, custom_rate)
        return jsonify({"ok": True, **result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
```

`templates/settings.html` — dropdown + conditional custom input, follow the
existing dark theme + `--accent`/`--surface` CSS vars from `base.html`:

```html
{% extends "base.html" %}
{% block title %}Settings{% endblock %}
{% block content %}
<div class="panel" style="max-width:640px; margin:24px auto;">
  <h2 style="margin-bottom:16px;">Tax Settings — Capital Gains Jurisdiction</h2>
  <p style="color:var(--muted); margin-bottom:16px; font-size:11px;">
    Controls the tax-drag penalty the optimizer applies when trimming a
    winning position. Changing this does not retroactively affect past
    trades — it only shapes future rebalance suggestions.
  </p>

  <label for="jurisdiction-select">Jurisdiction</label>
  <select id="jurisdiction-select" style="width:100%; padding:8px; margin:8px 0 16px;
    background:var(--surface2); color:var(--text); border:1px solid var(--border);">
    {% for key, j in jurisdictions.items() %}
    <option value="{{ key }}" {% if key == tax.jurisdiction %}selected{% endif %}>
      {{ j.label }}{% if j.rate is not none and key != 'custom' %} — {{ '%.3f' % (j.rate * 100) }}%{% endif %}
      {% if j.approximate %} (approximate){% endif %}
    </option>
    {% endfor %}
  </select>

  <div id="custom-rate-row" style="display:{{ 'block' if tax.jurisdiction == 'custom' else 'none' }};">
    <label for="custom-rate-input">Custom rate (%)</label>
    <input id="custom-rate-input" type="number" step="0.001" min="0" max="100"
      value="{{ '%.3f' % (tax.custom_rate * 100) if tax.custom_rate else '' }}"
      style="width:100%; padding:8px; margin:8px 0 16px;
      background:var(--surface2); color:var(--text); border:1px solid var(--border);">
  </div>

  <div id="active-rate-display" style="color:var(--accent); font-size:13px; margin-bottom:16px;">
    Active rate: <strong>{{ '%.3f' % (tax.tax_rate * 100) }}%</strong>
  </div>

  <button onclick="saveTaxSettings()" style="padding:10px 20px; background:var(--accent);
    color:var(--bg); border:none; cursor:pointer; font-family:var(--mono); font-weight:600;">
    SAVE
  </button>
</div>
{% endblock %}

{% block scripts %}
<script>
document.getElementById('jurisdiction-select').addEventListener('change', function() {
  document.getElementById('custom-rate-row').style.display =
    this.value === 'custom' ? 'block' : 'none';
});

async function saveTaxSettings() {
  const jurisdiction = document.getElementById('jurisdiction-select').value;
  const customRateInput = document.getElementById('custom-rate-input').value;
  const body = { jurisdiction };
  if (jurisdiction === 'custom') {
    if (!customRateInput) { alert('Enter a custom rate'); return; }
    body.custom_rate = parseFloat(customRateInput);
  }
  const resp = await fetch('/api/tax_settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  });
  const result = await resp.json();
  if (result.ok) {
    document.getElementById('active-rate-display').innerHTML =
      'Active rate: <strong>' + (result.tax_rate * 100).toFixed(3) + '%</strong>';
    alert('Saved.');
  } else {
    alert('Error: ' + result.error);
  }
}
</script>
{% endblock %}
```

Add a nav link in `base.html`'s tab bar, near the existing "LEGAL &
COMPLIANCE" footer link (settings is infrequent, doesn't need a top-tier
tab):

```html
<div class="status-item"><a href="/settings" style="color:var(--muted); text-decoration:none;">SETTINGS</a></div>
```

### Step 5 — Wire `current_prices` through from `scheduler.py`

`step_portfolio_construction()` already fetches `current_prices_cb` for the
circuit breaker (I3) a few lines above the `optimize_with_bl()` call —
**reorder slightly** so that price fetch happens before the optimizer call
and pass the same dict through, rather than fetching prices twice:

```python
# Fetch current prices ONCE, use for both circuit breaker AND tax penalty
session_px = get_session()
px_rows = session_px.execute(text("""
    SELECT p.ticker, p.adj_close FROM prices p
    INNER JOIN (SELECT ticker, MAX(date) AS max_date FROM prices GROUP BY ticker)
    latest ON p.ticker=latest.ticker AND p.date=latest.max_date
""")).fetchall()
session_px.close()
current_prices = pd.Series({r[0]: float(r[1]) for r in px_rows if r[1] is not None})

suggested_weights = optimize_with_bl(
    mu_bl=mu_bl, cov_matrix=cov_matrix, current_weights=current_weights,
    current_prices=current_prices, sector_map=TICKER_SECTORS, date=TODAY,
)
```

(Then reuse `current_prices` for the circuit breaker block below instead of
re-querying — a small dedup while you're in there.)

---

## Tuning notes

- The `'none'` preset (0% tax modeling) is the fastest way to A/B test
  whether this feature is actually changing optimizer behavior in a way you
  like — flip to `'none'`, run sandbox, compare against a run with your real
  jurisdiction selected.
- If you ever manage capital across two jurisdictions (e.g. a German account
  and a US account) simultaneously, this singleton-row design won't scale to
  that — it assumes one tax regime applies to the whole portfolio. Flag this
  explicitly if that ever becomes true; it'd need a per-account or
  per-position jurisdiction tag instead, which is a bigger change.
- `belgium` and `switzerland` presets are 0% specifically for **private,
  non-professional investors** — if trading frequency/pattern ever risks
  being reclassified as professional trading in either jurisdiction (a real
  legal distinction in both countries), that changes everything about this
  section and is worth actual legal advice, not a code comment.
