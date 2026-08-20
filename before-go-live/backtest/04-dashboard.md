> **STATUS: NOT IMPLEMENTED.**
> Depends on: `01-engine.md` (backtest_results.csv) and `02-alpha-ic-evaluation.md`
> (alpha_ic_results.csv) must exist before this page shows real data.
> The page already has a stub at `templates/backtests.html` — REPLACE it entirely.
> A Flask route `/backtests` already exists pointing at that stub — keep the route,
> only the template changes.

# Backtest Dashboard — UI Design & Implementation
# `templates/backtests.html` — REPLACE existing stub
# `flask_app.py` — update `/backtests` route
# Estimated time: 0.5 day

---

## Design principles for this page

The users of this dashboard are **not quants**. They know what a return is,
they know what a loss feels like, but they don't know what Sortino ratio means.

Rules for this page:

1. **Every number has a plain-English label and an info box.** No naked jargon.
   Sharpe becomes "Sharpe Ratio — how much return you get per unit of risk."
   IC becomes "Prediction Accuracy — did the model's ranking actually predict winners?"
2. **Visual hierarchy: verdict first, then detail.** The page opens with a 3-word
   verdict (e.g. "STRATEGY IS VALID") before any numbers. Users decide with that
   then scroll for detail.
3. **Color is data, not decoration.** Green = outperforms benchmark. Red = doesn't.
   Amber = marginal. No blue gradient headers, no purple cards. The system's
   existing CSS variables (`--accent` green, `--accent2` red, `--accent3` amber)
   handle this already.
4. **"Why does this matter?" tooltips.** Every metric card has an `info-point`
   with a one-sentence explanation. Use the existing `.info-point` tooltip system
   from `base.html` — no new CSS needed.
5. **No generic layout.** The existing `divergence.html` and `health.html` pages
   are reference quality — use the same `panel`, `kpi`, `tbl`, `grid` classes.
   Do not introduce new CSS that isn't in `base.html`.

---

## Page layout — section by section

### Section 0: Status bar (top of page, above KPIs)

A single-line strip that shows whether backtest results are loaded or not:

```
[ BACKTEST RESULTS LOADED · 2023-01-23 → 2026-08-19 · 880 trading days ]
                                              ← from backtest_metrics.csv
```

If `backtest_results.csv` doesn't exist yet:
```
[ NO RESULTS YET · Run: python backtests/walk_forward.py ]
```

This is the ONLY place the user is told to run a script — once, clearly.
Not buried in a table row.

---

### Section 1: Verdict strip (3 KPI cards, full width)

```
┌─────────────────┬─────────────────┬─────────────────┐
│ STRATEGY VERDICT│ VS BENCHMARK    │ RISK LEVEL      │
│                 │                 │                 │
│  ● VALID        │  +4.2%          │  MODERATE       │
│                 │  annual excess  │  β 0.91         │
└─────────────────┴─────────────────┴─────────────────┘
```

**STRATEGY VERDICT** logic:
- `VALID` (green) if: Sharpe > 0.4 AND Info Ratio > 0.3 AND Calmar > 0.3
- `MARGINAL` (amber) if: Sharpe 0.2–0.4 OR Info Ratio 0.15–0.3
- `INCONCLUSIVE` (amber) if backtest window < 1.5 years
- `NEEDS WORK` (red) if: Sharpe < 0.2 OR max drawdown > -35%

**Important:** the verdict KPI has a prominent info-point tooltip:
```
"This verdict is based on simulated historical data from 2023–2026.
 Past performance does not guarantee future results.
 The 2022 bear market is not included — treat this as a bull-market stress test only."
```

**VS BENCHMARK** = annual excess return (CAGR_port − CAGR_bench).
If positive: green. Negative: red.
Info: "Annual excess return vs iShares MSCI World (EUNL.DE).
      This tells you whether the strategy added value above simply buying the market."

**RISK LEVEL**: based on beta:
- β < 0.7 → `LOW RISK` (green)
- β 0.7–1.1 → `MODERATE` (amber)
- β > 1.1 → `HIGH RISK` / `LEVERED` (red)
Info: "Beta measures how much this portfolio moves when the market moves.
      Beta = 1.0 means it tracks the market. Beta > 1.0 means it amplifies moves."

---

### Section 2: Equity curve chart (left 60%) + Return comparison table (right 40%)

```
┌──────────────────────────────────┬───────────────────────────────┐
│ EQUITY CURVE                     │ ANNUAL RETURN COMPARISON      │
│ [Chart.js line chart]            │                               │
│ — portfolio (green)              │ YEAR   PORTFOLIO   MSCI WORLD │
│ — benchmark (muted)              │ 2023     +12.4%     +18.1%   │
│ [x-axis: date]                   │ 2024     +21.3%     +16.2%   │
│ [y-axis: portfolio value €]      │ 2025     +8.1%      +4.4%    │
│                                  │ 2026 YTD +5.2%      +3.1%    │
└──────────────────────────────────┴───────────────────────────────┘
```

**Chart details:**
- Y-axis starts at initial capital (€10,000), NOT at 0. Starting at 0 compresses
  the visual — this is a standard finance chart convention.
- Two datasets: portfolio (var(--accent) green, 1.5px), benchmark (muted, 1px dashed)
- No fill under lines — fill is visually misleading for multi-year comparisons
- Tooltips show: Date | Portfolio: €X,XXX | Benchmark: €X,XXX | Excess: +/-X.X%
- X-axis: monthly ticks, labeled YYYY-MM
- Data comes from `/api/backtest/equity` → reads `backtest_results.csv`

**Annual return table:**
- Each row: Year | Portfolio return | Benchmark return | Excess (colored)
- Excess > 0 → green tag; < 0 → red tag; within ±1% → amber "flat"
- Last row is "YTD" automatically if current year is in the data
- Info strip above table:
  > "Year where portfolio > benchmark = ✓. Target: outperform in at least 3 of 4 years."

---

### Section 3: Risk metrics (4 cards, full width)

```
┌────────────┬────────────┬────────────┬────────────┐
│ SHARPE     │ MAX LOSS   │ RECOVERY   │ CONSISTENCY│
│            │            │            │            │
│  0.71  ⓘ  │  -18.3% ⓘ │  CALMAR    │  HIT RATE  │
│  vs 0.54   │  vs -22.1% │  0.52  ⓘ  │  54%    ⓘ  │
│  benchmark │  benchmark │  vs 0.31   │  of days   │
└────────────┴────────────┴────────────┴────────────┘
```

**Tooltip text for each (non-technical language):**

`SHARPE RATIO ⓘ`
> "How much return you get for each unit of risk you take.
>  1.0 = excellent. 0.5–1.0 = good. Below 0.3 = the risk isn't worth it.
>  Your number vs the benchmark: if yours is higher, your strategy manages
>  risk better than just owning MSCI World."

`MAX LOSS ⓘ` (Max Drawdown)
> "The worst peak-to-trough drop this strategy experienced in the test period.
>  -18.3% means at its worst, €10,000 fell to €8,170 before recovering.
>  Compare to benchmark: if yours is smaller, the strategy protects better
>  in downturns."

`CALMAR ⓘ`
> "Annual return divided by the worst loss. Tells you if the gains
>  were worth the pain of the drawdowns.
>  Above 0.5 = acceptable. Below 0.2 = the drawdowns are too large
>  relative to what the strategy earns."

`HIT RATE ⓘ`
> "How often the portfolio outperformed the benchmark on a given day.
>  54% means it beat the benchmark on just over half of all trading days.
>  You don't need 70%+ — even 52-54% compounds into meaningful outperformance
>  over time."

**Color logic per card:**
- Sharpe: good (green) if > 0.6, warn (amber) if 0.3–0.6, danger (red) if < 0.3
- Max drawdown: good if > -20%, warn if -20% to -35%, danger if < -35%
- Calmar: good if > 0.5, warn if 0.2–0.5, danger if < 0.2
- Hit rate: good if > 55%, neutral (text only, no color) if 50–55%, danger if < 50%

---

### Section 4: Alpha model prediction accuracy table

```
┌─────────────────────────────────────────────────────────────────┐
│ SIGNAL QUALITY — How well did each model predict actual returns? │
│                                                  ⓘ info strip    │
├──────────────────────────┬────────────┬───────────┬─────────────┤
│ MODEL                    │ ACCURACY   │ STABILITY │ VERDICT     │
│                          │ (IC 21d)   │ (ICIR)    │             │
├──────────────────────────┼────────────┼───────────┼─────────────┤
│ Momentum                 │ 0.048      │ 0.62      │ ✓ USEFUL    │
│ Sector Momentum          │ 0.031      │ 0.44      │ ~ MARGINAL  │
│ Mean Reversion           │ 0.021      │ 0.29      │ ✗ WEAK      │
│ Vol Timing               │ 0.038      │ 0.51      │ ✓ USEFUL    │
│ ML Alpha                 │ 0.062      │ 0.71      │ ✓ STRONG    │
└──────────────────────────┴────────────┴───────────┴─────────────┘
```

**Column headers have info-point tooltips — this is critical for non-technical users:**

`ACCURACY (IC 21d) ⓘ`
> "Information Coefficient: how well the model's ranking of stocks matched
>  which stocks actually went up 21 days later. Ranges from -1 (perfectly wrong)
>  to +1 (perfectly right). In practice:
>  > 0.05 is strong.  0.02–0.05 is useful.  Below 0.02 is noise."

`STABILITY (ICIR) ⓘ`
> "Consistency of accuracy over time. A model that is sometimes great and
>  sometimes terrible is less useful than one that is reliably decent.
>  Above 0.5 = reliably consistent. Below 0.3 = hot/cold, unreliable."

`VERDICT` logic (computed client-side from IC and ICIR values):
- IC > 0.04 AND ICIR > 0.5 → `✓ STRONG` (green tag)
- IC > 0.02 AND ICIR > 0.35 → `✓ USEFUL` (green tag)
- IC > 0.015 AND ICIR > 0.25 → `~ MARGINAL` (amber tag)
- Else → `✗ WEAK` (red tag)

**Info strip above the table** (plain-language explanation of the whole section):
> "These numbers show how well each model predicted which stocks would go up.
>  The strategy combines all models together — even a 'MARGINAL' model
>  can still add value when blended with stronger ones.
>  A 'WEAK' model is not harmful — the system automatically reduces its
>  influence when its accuracy is low."

---

### Section 5: Disclaimer strip (bottom, always visible)

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠  SIMULATION ONLY — These results are based on historical       │
│    simulation, not real trading. The test period (2023–2026)     │
│    was primarily a bull market. Results in a sustained bear       │
│    market may differ significantly. Not financial advice.        │
└──────────────────────────────────────────────────────────────────┘
```

Use `alert alert-warn` styling (amber border) — same pattern as other pages.
This is NOT optional. It must be visible without scrolling on a 1080p screen.

---

## Flask route update — `flask_app.py`

Replace the current minimal `/backtests` route with:

```python
@app.route('/backtests')
def backtests():
    import csv, os

    def _load_csv(filename):
        path = os.path.join(os.path.dirname(__file__), 'backtests', filename)
        if not os.path.exists(path):
            return None
        with open(path, newline='') as f:
            return list(csv.DictReader(f))

    metrics  = _load_csv('backtest_metrics.csv')    # from 03-portfolio-metrics.md
    ic_table = _load_csv('alpha_ic_results.csv')    # from 02-alpha-ic-evaluation.md
    # equity curve is loaded client-side via /api/backtest/equity
    # (too large to pass through Jinja — can be 500-900 rows)

    return render_template('backtests.html',
        page='backtests',
        metrics=metrics,         # list of {value: ..., ...} rows
        ic_table=ic_table,       # list of {model, horizon, mean_ic, icir, ...}
        has_results=metrics is not None,
    )


@app.route('/api/backtest/equity')
def api_backtest_equity():
    """Serves equity curve data for the Chart.js chart."""
    import csv, os
    path = os.path.join(os.path.dirname(__file__), 'backtests', 'backtest_results.csv')
    if not os.path.exists(path):
        return jsonify({'dates': [], 'portfolio': [], 'benchmark': []})

    dates, port, bench = [], [], []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            dates.append(row['date'][:10])
            port.append(float(row['portfolio_value']))
            bench.append(float(row.get('benchmark_value', 0) or 0))

    return jsonify({'dates': dates, 'portfolio': port, 'benchmark': bench})
```

Note: both CSV files are read server-side at request time (not cached). The files
are small enough that this is fine — no DB interaction needed for this page.

---

## What NOT to put on this page

- ❌ No "run backtest" button. The backtest is a CLI script, not a UI action.
  Triggering a 600-step simulation from a button press would block the Flask
  process for minutes. Document the CLI command; don't put it in the UI.
- ❌ No raw data tables showing every daily row — that's what the CSV is for.
- ❌ No per-ticker breakdown — the backtest tracks portfolio-level equity, not
  per-stock attribution. Attribution analysis is a separate project.
- ❌ No interactive "what-if" parameters (change Sharpe threshold, etc.) —
  this is a results page, not a simulation tool.
