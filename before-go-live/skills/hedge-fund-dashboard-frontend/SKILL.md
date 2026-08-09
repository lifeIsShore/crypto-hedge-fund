---
name: hedge-fund-dashboard-frontend
description: >
  Design system, UX architecture, and implementation context for the Control Tower
  Flask dashboard frontend. Use when working on templates (Jinja2 HTML), CSS,
  JavaScript, or adding new tabs/panels to the dashboard. Covers the dark-mode
  design system, the HITL review queue, watchlist, highlighted picks, conviction
  scoring display, and the post-launch I1–I5 improvement roadmap.
---

# Hedge Fund Dashboard Frontend — Skill

## Stack
- **Backend:** Flask (Python), Jinja2 templates, SQLite via raw sqlite3
- **Frontend:** Vanilla HTML/CSS/JS — no framework, no bundler
- **Fonts:** IBM Plex Mono (primary), IBM Plex Sans (secondary) via Google Fonts
- **Charts:** Chart.js 4.4.1 (CDN)
- **Template directory:** `c:\Users\ahmty\Desktop\hedge-fund\templates\`
- **Base layout:** `templates/base.html` — all pages extend this

---

## Design system — CSS variables (from `base.html`)

```css
:root {
  --bg:       #07080a;    /* page background — near-black */
  --surface:  #0d0f13;    /* panel/card background */
  --surface2: #131720;    /* input fields */
  --border:   #1e2535;    /* all borders */
  --accent:   #00e5a0;    /* primary green — BUY, good, active */
  --accent2:  #ff4d6d;    /* red — SELL, danger, Risk-Off */
  --accent3:  #f5a623;    /* amber — warning, lean-sell, MEDIUM conviction */
  --accent4:  #6495ed;    /* cornflower blue — info, LONG side, nav badges */
  --text:     #f1f5f9;    /* primary text */
  --muted:    #cbd5e1;    /* secondary/metadata text */
  --mono:     'IBM Plex Mono', monospace;
  --sans:     'IBM Plex Sans', sans-serif;
}
```

**Conviction traffic lights (CSS classes):**
- `conv-high` → `--accent` (green) — conviction ≥ 0.70
- `conv-medium` → `--accent3` (amber) — 0.55–0.70
- `conv-low` → `--accent4` (blue) — < 0.55
- `conv-gated` → `--muted` (grey) — AUC < 0.53

**Signal colors:**
- `.sig-buy` → `--accent`, `.sig-lean-buy` → `#7ef5c8`
- `.sig-neutral` → `--muted`
- `.sig-lean-sell` → `--accent3`, `.sig-sell` → `--accent2`

---

## Navigation tabs (in order)

| Tab | Route | Template | Key data source |
|---|---|---|---|
| OVERVIEW | `/` | `overview.html` | `positions_history`, `performance_history` |
| ⭐ HIGHLIGHTED | `/highlighted` | `highlighted.html` | `/api/highlighted` (conviction-scored) |
| 👁 WATCHLIST | `/watchlist` | `watchlist.html` | `/api/watchlist` (enriched with live signals) |
| RISK & STRATEGY | `/risk` | `risk.html` | `price_targets`, `risk_metrics` |
| ML RESEARCH | `/research` | `research.html` | `ml_state.json`, `signals` |
| MACRO REGIME | `/regime` | `regime.html` | `regime_history_new` |
| PAIRS / STAT ARB | `/pairs` | `pairs.html` | pairs cointegration results |
| REBALANCE | `/rebalance` | `rebalance.html` | `model_outputs` |
| HOLDINGS | `/holdings` | `holdings.html` | `positions_history` |
| TRADES | `/trades` | `trades.html` | `trades` |
| ANALYTICS | `/analytics` | `analytics.html` | `performance_history`, `trades` |
| HISTORY | `/history` | `history.html` | `performance_history` |
| ETF DIVERGENCE | `/divergence` | `divergence.html` | `divergence_labels` |
| PIPELINE HEALTH | `/health` | `health.html` | `pipeline_runs`, `/api/freshness` |
| ⏳ REVIEW QUEUE | `/queue` | `queue.html` | `/api/signal_queue` |
| ⚗ PORTFOLIO LAB | `/lab` | `lab.html` | `saved_portfolios` |

Nav badges: `base.html` polls `/api/watchlist/count` and `/api/signal_queue/count` on every page load, showing count pills on the nav links.

---

## HITL Signal Review Queue — fully built ✅

**Tab:** ⏳ REVIEW QUEUE → `queue.html` + `/api/signal_queue*` routes in `flask_app.py`

**What it does:**
- Pending inbox: table of signals sorted by conviction desc, each row has ✅ APPROVE / ❌ SKIP buttons
- On action: modal opens with structured `reason_category` dropdown + free-text note
- Regime warning: if approving a BUY in Risk-Off, shows conviction discount alert (× 0.8)
- Decision Journal: last 30 reviewed signals with date, decision, reason, note
- Auto-expiry: signals expire after 3 days if not reviewed
- KPI strip: counts for PENDING / APPROVED / SKIPPED / EXPIRED / current REGIME

**Population flow:** `step_push_signals_to_queue()` in `engine/scheduler.py` (step 14) auto-populates the queue after each pipeline run. Thresholds: long conviction ≥ 0.65, short conviction ≥ 0.45, all PEAD setups (regardless of conviction).

**Source tags:** `'pipeline'` (auto), `'pead'` (PEAD auto-push), `'watchlist'` (user clicked ⚡ QUEUE from watchlist), `'ml'` (user clicked from Highlighted tab).

---

## Watchlist — fully built ✅

**Tab:** 👁 WATCHLIST → `watchlist.html` + `/api/watchlist*` routes

**What it does:**
- Tracks tickers the user wants to monitor before committing to the queue
- Enriches each ticker with live signals (current conviction, up_proba, price targets from DB)
- Computes conviction trend vs. snapshot taken when ticker was added (IMPROVING/WEAKENING/STABLE)
- Auto-promote banner: when conviction ≥ `alert_threshold` (default 0.70) → promote banner shown
- Each row has ⚡ QUEUE button (pushes to signal_queue) and ✕ remove button
- Add modal: ticker, side (LONG/SHORT), alert threshold, notes

---

## Highlighted tab — fully built ✅

**Tab:** ⭐ HIGHLIGHTED → `highlighted.html` + `/api/highlighted`

Surfaces top 12 long + 6 short conviction picks. Cards show conviction tier, tags (PEAD/RISK-ON/STRONG R:R), target/stop prices, Kelly%, Add to Queue button, Watch button.

---

## Component patterns (use consistently)

### KPI strip
```html
<div class="kpi-strip">
  <div class="kpi good">    <!-- or neutral / warn / danger / info -->
    <div class="kpi-label">LABEL</div>
    <div class="kpi-value" id="kpi-xxx">—</div>
    <div class="kpi-sub">subtext</div>
  </div>
</div>
```

### Panel
```html
<div class="panel">
  <div class="panel-header">
    <span class="panel-title">TITLE</span>
    <span class="panel-badge">BADGE TEXT</span>
  </div>
  <div class="panel-body">...</div>
</div>
```

### Table
```html
<table class="tbl">
  <thead><tr><th onclick="sortTable(0,'table-id','str')">COL</th>...</tr></thead>
  <tbody id="table-id-tbody"></tbody>
</table>
```
`sortTable(colIdx, tableId, type)` is a global in `base.html`. `type` = `'str'` | `'num'`.

### Tooltip (info-point)
```html
<th class="info-point" data-title="TITLE" data-info="Description shown on hover.">LABEL</th>
```

### Alert box
```html
<div class="alert alert-warn">text</div>   <!-- alert-ok / alert-error / alert-info -->
```

### Tag/pill
```html
<span class="tag tag-green">TEXT</span>  <!-- tag-red / tag-yellow / tag-blue / tag-muted -->
```

### Modal pattern
```html
<div class="modal-backdrop" id="my-modal">
  <div class="modal-box">
    <!-- content -->
    <div class="modal-actions">
      <button class="btn" onclick="...">OK</button>
      <button class="btn btn-danger" onclick="closeModal()">CANCEL</button>
    </div>
  </div>
</div>
```
Toggle with `.classList.add('open')` / `.classList.remove('open')`.

---

## Global JS helpers (available on all pages via base.html)

```javascript
fmtEur(v)            // → "€1,234.56" or "—"
fmtPct(v, dp=1)      // → "+3.4%" or "—"
sigClass(action)     // → CSS class string for BUY/LEAN_BUY/NEUTRAL/LEAN_SELL/SELL
sigLabel(action)     // → "🟢 BUY" etc.
sortTable(colIdx, tableId, type)   // column sort
```

---

## Data freshness banner
`base.html` always fetches `/api/freshness`. If any state file > 24h old, a red `#stale-banner` appears at top of every page: **"⚠️ STALE DATA — do not trade on these signals."**

---

## Post-launch UI improvements (not yet built)

| # | Feature | Spec file | Notes |
|---|---|---|---|
| I1 | Light/cream theme | `I1-light-theme.md` | CSS variable swap, theme toggle button in header |
| I2 | Signal explainability panel | `I2-signal-explainability.md` | Proportional alpha contribution bars (NOT SHAP) |
| I3 | Circuit breaker display | `I3-circuit-breakers.md` | Stop-loss indicator on Holdings + Risk tabs |
| I4 | Paper trading mode UI | `I4-paper-trading-sandbox.md` | Isolated sandbox DB, 21-day promotion checklist |
| I5 | Benchmark overlay | `I5-benchmark-tracking.md` | Equity curve + Active Share KPI on Analytics |

---

## Conventions

- All page routes pass `page="<name>"` to templates for active nav highlighting.
- All data is loaded via JS `fetch('/api/...')` after page load — no server-side rendering of data.
- Ticker names map: templates receive `{{ ticker_names | tojson | safe }}` — a JSON dict of ticker → company name, embedded in the page as a `<script type="application/json">` tag.
- Animations: `.panel` gets `animation: fadeUp .35s ease both` from `base.html`. Custom animations use `@keyframes fadeUp`.
- All currency displayed in EUR (€), locale `de-DE` for number formatting.
