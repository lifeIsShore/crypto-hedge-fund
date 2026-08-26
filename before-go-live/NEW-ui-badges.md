> **STATUS (2026-08-26, written by Claude): NOT IMPLEMENTED.** Design doc only.
> This is `FINAL-GO-LIVE-CHECKLIST.md` item **2.5**. Pure wiring/display task — both
> data sources already exist and are already computed on every pipeline run; nothing
> in this doc adds a new signal or table. It closes two gaps explicitly flagged as
> "not built" when their underlying features shipped:
> J4 (`archive-implemented/J4-earnings-calendar.md` Step 5 — "dashboard badge for
> upcoming earnings on held positions... data-layer only this session") and
> J5 (`archive-implemented/J5-sector-relative-momentum.md` Step 4 — "ticker-detail
> divergence-display UI not built... data/signal layer only this session").

# 2.5 — Missing UI Badges (Upcoming Earnings + Sector-Relative Rank)
# Edit `flask_app.py` + `templates/overview.html` + `templates/ticker_detail.html`
# Estimated time: 3–4 hours (two independent, unrelated badges — can be done separately)

---

## The problem this closes

Two features were fully built through the data/signal layer and then stopped one step
short of the dashboard, confirmed directly against the live code:

1. **Upcoming earnings (J4).** `get_reporting_soon(tickers, within_days=3)` in
   `engine/data/earnings_calendar.py` already returns exactly the ticker set needed —
   it's the same function `order_manager.py`'s pre-earnings throttle already calls in
   production. Nothing in `flask_app.py` or any template calls it for display purposes.
   Ahmet currently has no way to see "this position reports in 2 days" anywhere on the
   dashboard short of checking the DB directly.
2. **Sector-relative momentum divergence (J5).** `sector_mom_12m` is computed daily by
   `compute_sector_relative_features()` and persisted to `feature_store` alongside the
   universe-wide `mom_12m` — both numbers exist, side by side, for every ticker, every
   day. `SectorMomentumAlpha` already uses this to generate BL views. But the specific
   comparison that makes it useful to a human — "this stock looks weak vs. the whole
   market but strong vs. its own sector" — is never rendered anywhere.

Both are read-only display additions against data that's already correct and already
updating daily. No new pipeline step, no new table.

---

## Part A — Upcoming Earnings Badge

### Where it should appear

- **Ticker detail page** (`templates/ticker_detail.html`) — most important spot, next
  to the existing `#action-badge` span in the header. This is the "risk event log"
  framing from the original Gap 3 brainstorm: someone looking at one ticker should
  immediately see if a binary event is imminent.
- **Overview page positions table** (`templates/overview.html`, `#pos-table`) — a small
  inline marker next to the ticker for any held position reporting soon, so it's visible
  without clicking into every ticker individually.

### Backend

Add a small helper in `flask_app.py` (or `engine/data/earnings_calendar.py` if you'd
rather keep DB-query helpers out of the Flask layer — matches where `get_reporting_soon`
already lives):

```python
def _get_earnings_badges(tickers: list) -> dict:
    """Returns {ticker: {'reporting_soon': bool, 'report_date': str, 'report_time': str}}
    for any of the given tickers reporting within 3 days. Empty dict entries omitted."""
    from engine.data.earnings_calendar import get_reporting_soon
    soon = get_reporting_soon(tickers, within_days=3)
    if not soon:
        return {}
    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(soon))])
        params = {f't{i}': t for i, t in enumerate(soon)}
        rows = session.execute(text(f"""
            SELECT ticker, report_date, report_time FROM earnings_calendar
            WHERE ticker IN ({placeholders})
            AND date(report_date) BETWEEN date('now') AND date('now', '+3 days')
        """), params).fetchall()
        return {r[0]: {'report_date': r[1], 'report_time': r[2]} for r in rows}
    finally:
        session.close()
```

Wire into the existing `/ticker/<ticker>` route — add one call and pass the result into
the template context alongside `ml_signal`, `target`, `position`, etc. that route
already assembles:

```python
earnings_badge = _get_earnings_badges([ticker]).get(ticker)
# ... existing render_template(...) call, add earnings_badge=earnings_badge
```

For the overview page, wire into whichever route/endpoint feeds `#pos-tbody` (the JS
fetches this — check whether it's server-rendered or an `/api/positions`-style JSON
endpoint before assuming which file to touch) — add `_get_earnings_badges()` for the
full set of currently-held tickers in one call (not per-row) to avoid N+1 queries.

### Frontend

`ticker_detail.html`, next to the existing action badge:

```html
<span id="action-badge" style="font-size:11px">{{ ...existing... }}</span>
{% if earnings_badge %}
<span class="tag tag-orange" title="{{ earnings_badge.report_date }} ({{ earnings_badge.report_time or '—' }})">
  📅 REPORTS {{ earnings_badge.report_date }}
</span>
{% endif %}
```

(`tag-orange` doesn't exist yet in the stylesheet as of this doc — check `base.html`'s
`.tag-green`/`.tag-red` definitions and add a matching orange variant; don't invent a
new badge visual language when a `.tag` class already exists for exactly this purpose.)

`overview.html`'s positions table — in the JS that builds `#pos-tbody` rows, append a
small marker to the ticker cell when the ticker is in the earnings-badge set returned
alongside the positions JSON:

```js
const tickerCell = row.reporting_soon
  ? `${row.ticker} <span class="tag tag-orange" style="font-size:8px" title="Reports ${row.report_date}">📅</span>`
  : row.ticker;
```

---

## Part B — Sector-Relative Rank / Divergence Display

### Where it should appear

**Ticker detail page only** — this is a deep-dive metric, not something that belongs in
a scannable positions table. Add a new small panel or fold it into the existing "ML
Signal" panel in `ticker_detail.html`.

### Backend

Both `mom_12m` and `sector_mom_12m` already live in `feature_store` for every ticker,
every date — this is a straight read, no computation needed:

```python
def _get_momentum_comparison(ticker: str) -> dict | None:
    session = get_session()
    try:
        row = session.execute(text("""
            SELECT
                MAX(CASE WHEN feature_name = 'mom_12m' THEN feature_value END) AS universe_rank,
                MAX(CASE WHEN feature_name = 'sector_mom_12m' THEN feature_value END) AS sector_rank
            FROM feature_store
            WHERE ticker = :t AND date = (SELECT MAX(date) FROM feature_store WHERE ticker = :t)
        """), {'t': ticker}).fetchone()
        if row is None or row[0] is None or row[1] is None:
            return None
        universe_rank, sector_rank = float(row[0]), float(row[1])
        divergence = sector_rank - universe_rank
        return {
            'universe_rank': round(universe_rank, 3),
            'sector_rank': round(sector_rank, 3),
            'divergence': round(divergence, 3),
            # Matches the J5 doc's own illustrative example: a sector rotation
            # candidate is strong within its sector but weak vs. the whole market.
            'flag': abs(divergence) >= 0.35,
        }
    finally:
        session.close()
```

Note: check the actual `feature_name` string for the universe-wide feature before
wiring this — `momentum.py` was confirmed to use `mom_12m` as of the J5 doc, but verify
against the live `feature_store` rows (`SELECT DISTINCT feature_name FROM feature_store`)
rather than trusting the doc, per this project's own repeated lesson about not trusting
a spec at face value without checking the code it describes.

Wire into the `/ticker/<ticker>` route the same way as the earnings badge:

```python
momentum_comparison = _get_momentum_comparison(ticker)
```

### Frontend

Add to the existing "ML Signal" panel in `ticker_detail.html`, or a small standalone
panel right below it:

```html
{% if momentum_comparison %}
<div class="panel" style="margin-top:14px">
  <div class="panel-header">
    <span class="panel-title">MOMENTUM — UNIVERSE VS. SECTOR</span>
    {% if momentum_comparison.flag %}
      <span class="panel-badge" style="color:var(--accent2)">⚠ DIVERGENCE</span>
    {% endif %}
  </div>
  <div class="panel-body">
    <table class="tbl">
      <tbody>
        <tr><td style="color:var(--muted)">Universe momentum rank</td><td>{{ '%.2f'|format(momentum_comparison.universe_rank) }}</td></tr>
        <tr><td style="color:var(--muted)">Sector momentum rank</td><td>{{ '%.2f'|format(momentum_comparison.sector_rank) }}</td></tr>
      </tbody>
    </table>
    {% if momentum_comparison.flag %}
      <div class="alert alert-warn" style="margin-top:10px">
        {% if momentum_comparison.divergence > 0 %}
          Strong within-sector leader, weak vs. whole market — possible sector rotation candidate.
        {% else %}
          Weak within its sector despite decent universe-wide rank — a laggard inside a strong group.
        {% endif %}
      </div>
    {% endif %}
  </div>
</div>
{% endif %}
```

Wording follows the exact framing from `J5-sector-relative-momentum.md` Step 4's own
example (`NVDA` illustration), since that's already the vocabulary this project uses
for the concept.

---

## Tuning notes

- `within_days=3` for the earnings badge matches the existing throttle window in
  `order_manager.py` (`EARNINGS_THROTTLE_DAYS`) — keep these in sync; if one changes,
  check whether the other should too, since showing "reports soon" on the UI while the
  throttle window disagrees would be confusing.
- `flag: abs(divergence) >= 0.35` is a starting threshold, not tuned against real data —
  pull a week of live `sector_mom_12m`/`mom_12m` pairs after this ships and eyeball the
  distribution before trusting the flag to mean something (same calibration caveat as
  `NEW-ticker-liquidity-tiering.md`'s thresholds).

## Explicitly out of scope for this doc

- No new alpha signal, no change to `SectorMomentumAlpha` or the earnings throttle —
  display only, against data both models already consume.
- Does not include a dashboard-wide "upcoming earnings this week" summary tile (that
  was J4 Step 5's other suggestion, for the Health page) — worth a follow-up if wanted,
  but kept out of this doc to stay a small, single-sitting wiring task like 2.1–2.4.
- No historical divergence chart — current-value display only, matching the "single
  ticker detail page" scope everywhere else in this doc.
