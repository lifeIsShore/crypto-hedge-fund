# I5: Benchmark Equity Curve Overlay
**Improvement (post go-live) | File: `flask_app.py`, `templates/analytics.html`**

---

## Overview

The analytics page shows your portfolio equity curve. It does not show a
benchmark overlay. This means you cannot tell whether your returns are
genuine alpha or just beta — you might be up 12% while the MSCI World
is up 18%, which is actually significant underperformance.

Your `improvements.md` flags this as "Closet Indexing" risk:
> "Plot the fund's equity curve against a primary benchmark (SPY or QQQ).
> Calculate Active Share to ensure the portfolio is sufficiently unique."

The `performance_history` table already has a `benchmark_value_eur` column
that is written during `step_performance_log()` — but it is never populated.

---

## Fix — Step 1: Populate benchmark in `step_performance_log()`

In `engine/scheduler.py`, in `step_performance_log()`, add benchmark tracking:

```python
from portfolio.src.config import BENCHMARK_TICKER

# Get benchmark (EUNL.DE) current price and yesterday's price
bench_today = session.execute(text("""
    SELECT adj_close FROM prices
    WHERE ticker = :b
    ORDER BY date DESC LIMIT 1
"""), {'b': BENCHMARK_TICKER}).fetchone()

bench_prev = session.execute(text("""
    SELECT adj_close FROM prices
    WHERE ticker = :b AND date < (SELECT MAX(date) FROM prices WHERE ticker = :b)
    ORDER BY date DESC LIMIT 1
"""), {'b': BENCHMARK_TICKER}).fetchone()

# Reconstruct benchmark equity curve from first portfolio deposit
# Get or initialize benchmark tracking value
bench_row = session.execute(text("""
    SELECT benchmark_value_eur FROM performance_history
    WHERE date < :d AND benchmark_value_eur IS NOT NULL
    ORDER BY date DESC LIMIT 1
"""), {'d': TODAY}).fetchone()

bench_val = None
if bench_today and bench_prev and bench_prev[0] and bench_prev[0] > 0:
    bench_ret = (float(bench_today[0]) - float(bench_prev[0])) / float(bench_prev[0])
    if bench_row and bench_row[0]:
        bench_val = round(float(bench_row[0]) * (1 + bench_ret), 2)
    else:
        # Initialize benchmark to same starting value as portfolio
        first_deposit = session.execute(text("""
            SELECT SUM(value_eur) FROM trades
            WHERE action = 'DEPOSIT'
        """)).fetchone()
        if first_deposit and first_deposit[0]:
            bench_val = round(float(first_deposit[0]), 2)

# Update the INSERT to include benchmark_value_eur
session.execute(text("""
    INSERT INTO performance_history (date, portfolio_value_eur, daily_return_pct, benchmark_value_eur)
    VALUES (:d, :v, :r, :b)
    ON CONFLICT(date) DO UPDATE SET
        portfolio_value_eur   = excluded.portfolio_value_eur,
        daily_return_pct      = excluded.daily_return_pct,
        benchmark_value_eur   = excluded.benchmark_value_eur
"""), {
    'd': TODAY,
    'v': round(total_val, 2),
    'r': round(daily_ret * 100, 4),
    'b': bench_val,
})
```

---

## Fix — Step 2: Include benchmark in `/api/performance` response

In `flask_app.py`, `api_performance()`, the `perf_rows` query already selects
`benchmark_value_eur`. Update the equity series builder to include it:

```python
equity_series = []
benchmark_series = []

if perf_rows:
    for row in perf_rows:
        v = row.get("portfolio_value_eur")
        b = row.get("benchmark_value_eur")
        if v is not None:
            equity_series.append({"date": row["date"], "value": float(v)})
        if b is not None:
            benchmark_series.append({"date": row["date"], "value": float(b)})
```

Add to the response:
```python
return jsonify({
    "kpis":             kpis,
    "daily_returns":    daily_returns,
    "equity_series":    equity_series,
    "benchmark_series": benchmark_series,   # NEW
    "ledger":           trades_rows,
    "generated_at":     datetime.now().isoformat(),
})
```

---

## Fix — Step 3: Add benchmark line to equity curve chart

In `analytics.html`, in the Chart.js equity curve configuration, add a
second dataset:

```javascript
datasets: [
    {
        label: 'Portfolio',
        data: equityData,
        borderColor: 'var(--accent)',
        backgroundColor: 'rgba(0,229,160,0.05)',
        fill: true,
        tension: 0.3,
    },
    {
        label: 'MSCI World (EUNL.DE)',
        data: benchmarkData,
        borderColor: 'rgba(245,166,35,0.8)',
        backgroundColor: 'transparent',
        borderDash: [5, 3],
        fill: false,
        tension: 0.3,
    }
]
```

---

## Fix — Step 4: Active Share KPI

Add to the KPIs section in `api_performance()`:

```python
# Active Share = 0.5 * sum(|portfolio_weight - benchmark_weight|)
# For EUNL.DE (MSCI World), approximate benchmark weights using ASSET_UNIVERSE
# A simple proxy: % of portfolio in non-ETF positions vs market-cap weighted index
etf_weight = sum(p["weight"] or 0 for p in positions if p["ticker"] in ETF_TICKERS)
active_share = round((1 - etf_weight) * 100, 1)   # rough proxy

kpis["active_share_pct"] = active_share
kpis["benchmark_ticker"] = BENCHMARK_TICKER
```

Display on the analytics dashboard with a tooltip:
> "Active Share: what % of your portfolio differs from the benchmark.
> Below 60% = closet indexer. Above 80% = high-conviction active."

---

## Result

The analytics page will show two lines on the equity curve:
- **Green solid**: Your portfolio value (normalized to deposit)
- **Yellow dashed**: MSCI World ETF (same starting value)

And a new KPI card: `Active Share: 74%` — confirming you are running a
genuinely active portfolio, not paying yourself to track an index.
