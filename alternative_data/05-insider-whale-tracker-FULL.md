# 05 — The "Insider & Whale" Tracker

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py`

---

## 1. Concept & Hypothesis

This is the most "classical" alt-data signal in the set — insider open-market buying and congressional trading are widely studied and have documented (if modest and shrinking) historical alpha. The value-add here isn't the idea itself (well known) but building a clean, well-filtered, low-latency pipeline that isolates genuinely informative signal (cash purchases, clustering) from noise (routine option exercises, 10b5-1 scheduled sales).

**Hypothesis:** Clustered open-market insider buying, and to a lesser extent congressional trading clusters, are statistically associated with modest forward outperformance — small in magnitude but real, and worth including as a low-cost, low-maintenance feature given how cheap and reliable the data source is.

**Why this edge might still exist (though smaller than it used to be):** Academic literature (Lakonishok & Lee, Seyhun) documents insider-buying alpha going back decades; more recent work suggests the effect has weakened as the information has become more widely followed (e.g., via free "insider tracking" sites and apps), but a residual effect, especially in cluster-buying and smaller-cap names, is still commonly found.

**Why it might be weaker than expected:** This is one of the most commoditized alt-data signals — numerous free apps (OpenInsider, Quiver Quantitative, Unusual Whales) already surface this same data to retail. Congressional-trading alpha specifically is a very crowded narrative (heavily discussed on social media) and disclosure lags (up to 45 days under the STOCK Act) blunt the "before the market knows" premise significantly — by the time a congressional trade is disclosed, it's often already old news.

---

## 2. Data Sources

| Source | Data | Access Method | Cost |
|---|---|---|---|
| SEC EDGAR | Form 4 (insider transactions) | Free API/RSS feed | Free |
| Congressional disclosure databases | Senate/House stock trade disclosures | Senate eFD system, House Clerk disclosures, or aggregator APIs (Quiver Quantitative offers a free/paid API that pre-cleans this data) | Free (raw) or ~$30–100/mo (cleaned aggregator API) |

**Recommendation:** For congressional trades specifically, strongly consider using an aggregator API (e.g., Quiver Quantitative) rather than parsing raw House/Senate PDF disclosure forms yourself — those raw disclosures are notoriously messy (scanned PDFs, inconsistent formats) and a well-maintained aggregator will save significant engineering time for a modest fee.

---

## 3. Core Features

### 3.1 Cluster Insider Buying
- **Filter:** Open-market cash purchases only — explicitly exclude option exercises and any transaction coded as part of a 10b5-1 pre-scheduled plan.
- **Logic:** ≥3 distinct insiders (C-suite/board) buying in the same rolling 7-day (not necessarily calendar "week") window ⇒ cluster flag.
- **Output:** `cluster_insider_buy_30d` (boolean) — consider also emitting a continuous version (`insider_buy_dollar_volume_30d`) since a boolean throws away magnitude information the ML model could use.

### 3.2 Congressional Trade Tracking
- **Filter:** Focus specifically on trades by members sitting on relevant oversight/committee positions where a conflict-of-interest signal is plausible (e.g., Armed Services Committee members buying defense stocks), not just "any politician buys any stock."
- **Output:** `abnormal_political_buying` (boolean)
- **Caveat given disclosure lag:** treat this feature as lower-conviction than insider buying and consider down-weighting it, or excluding it if the backtest (§7) doesn't show it clears the noise bar once the 45-day disclosure lag is properly accounted for.

---

## 4. Architecture

### 4.1 Pipeline

```
┌────────────────┐    ┌───────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Daily SEC Form 4│──▶│ Filter (cash  │──▶│ Cluster aggregation│──▶│ insider_whale_scores│
│ + congressional │   │ purchases only,│   │ (rolling 7d/30d   │   │ → feature_builder │
│ disclosure poll │   │ exclude 10b5-1)│   │ window)           │   │                  │
└────────────────┘    └───────────────┘    └──────────────────┘    └─────────────────┘
```
No LLM is strictly required for this agent — Form 4 and congressional disclosures are structured/semi-structured data. This is a rules-based pipeline, not an NLP one, which makes it cheaper and more deterministic than the rest of the set. Worth noting explicitly since it changes the engineering profile (less about prompt design, more about clean parsing/filtering logic).

### 4.2 Components

1. **Form 4 poller (`form4_poller.py`):** Polls SEC EDGAR's Form 4 RSS/full-text feed daily. Parses XML for transaction code — critically, filters on **Transaction Code "P"** (open market purchase) and explicitly checks the "10b5-1" indicator flag now required on Form 4s, excluding any pre-scheduled plan transactions.
2. **Congressional disclosure poller (`congress_poller.py`):** Either parses Quiver Quantitative's API (recommended) or raw Senate/House disclosure feeds if going the free route. Maps trades to committee membership (needs a maintained mapping of legislator → committee, which changes with each Congress — this mapping needs periodic manual refresh, it's not a "build once" static table).
3. **Cluster aggregator (`cluster_aggregator.py`):** Rolling window aggregation by ticker — counts distinct insiders, sums dollar value, flags clusters.
4. **Ticker mapper:** CIK-to-ticker mapping for Form 4s (SEC uses CIK, not ticker, as primary key) — maintain a mapping table, refreshed periodically since tickers can change (e.g., after M&A, rebranding).

### 4.3 Database Schema

```sql
CREATE TABLE insider_transactions (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              VARCHAR(10) NOT NULL,
    cik                 VARCHAR(20) NOT NULL,
    insider_name        VARCHAR(200),
    insider_title       VARCHAR(200),
    transaction_date    DATE NOT NULL,
    transaction_code    CHAR(1),            -- 'P' = purchase, etc.
    is_10b5_1_plan      BOOLEAN,
    shares               NUMERIC,
    price_per_share      NUMERIC,
    total_value          NUMERIC,
    filed_at            TIMESTAMPTZ,
    UNIQUE(cik, insider_name, transaction_date, shares)
);
CREATE INDEX idx_insider_ticker_date ON insider_transactions(ticker, transaction_date);

CREATE TABLE congressional_trades (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              VARCHAR(10) NOT NULL,
    legislator_name     VARCHAR(200),
    committee_relevant  BOOLEAN,             -- flagged if legislator sits on a plausibly relevant committee
    transaction_date    DATE NOT NULL,
    disclosed_date      DATE NOT NULL,       -- distinct from transaction_date, given STOCK Act lag
    transaction_type    VARCHAR(20),         -- 'buy'/'sell'
    amount_range_low    NUMERIC,             -- disclosures are typically ranges, not exact amounts
    amount_range_high   NUMERIC,
    source              VARCHAR(30)
);

CREATE TABLE insider_whale_scores (
    ticker                      VARCHAR(10) NOT NULL,
    as_of_date                  DATE NOT NULL,
    cluster_insider_buy_30d     BOOLEAN,
    insider_buy_dollar_volume_30d NUMERIC,
    distinct_insider_buyers_30d INT,
    abnormal_political_buying   BOOLEAN,
    political_buy_dollar_volume_30d NUMERIC,
    PRIMARY KEY (ticker, as_of_date)
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| SEC EDGAR Form 4 | **Low** | Fully public, free, explicitly disclosure data meant for public consumption |
| Raw Senate/House disclosure filings | **Low** | Public record under the STOCK Act, but format quality is poor (often scanned PDFs) |
| Quiver Quantitative (or similar aggregator) API | **Low** | Licensed commercial product built specifically for this use case |

Lowest-risk document in the set alongside `04` — all core data is public disclosure data, not scraped from a commercial platform's own site.

---

## 6. Cost Estimate

| Item | Estimate |
|---|---|
| SEC EDGAR Form 4 | Free |
| Raw congressional disclosures | Free but high parsing effort |
| Quiver Quantitative API (recommended) | **~$30–100/month** depending on tier |
| Compute | Negligible — no LLM required |
| **Total** | **~$30–100/month**, cheapest and least LLM-dependent agent in the set |

---

## 7. Backtesting & Validation Plan

1. **Historical backfill:** Both Form 4 and congressional disclosure history are available going back years via EDGAR/Quiver — full historical backtest is very feasible here, more so than the news/digital-exhaust agents.
2. **Insider cluster backtest:** Bucket by `cluster_insider_buy_30d` flag, measure forward 30/60/90-day returns vs. a matched control group (not just the whole universe — control for sector/size to avoid conflating this with a general small-cap or sector effect).
3. **Congressional trade backtest, disclosure-lag-aware:** Critically, backtest using `disclosed_date` (when the trade info became *available to you*) not `transaction_date` (when the legislator actually traded) — using the wrong date here would badly overstate the signal's real-world value through look-ahead bias. This is the most important methodological point in this whole document.
4. **Committee-relevance conditioning:** Test whether `committee_relevant=True` congressional trades outperform generic congressional trades — if not, the committee-mapping effort in §4.2 isn't earning its keep and the feature can be simplified.
5. **Decay test:** Given documented weakening of the classic insider-buying effect, test on a recent-years-only sample (e.g., last 3–5 years) rather than assuming a decades-old academic result still holds at full strength today.

---

## 8. Failure Modes & Edge Cases

- **10b5-1 misclassification:** the 10b5-1 indicator on Form 4s was only made mandatory relatively recently (SEC rule effective 2023) — for full historical backfill, older filings may not reliably indicate plan-vs-discretionary purchases; document this data-quality caveat rather than assuming perfect historical filtering.
- **CIK-ticker mapping drift:** tickers change (rebrands, spinoffs, M&A) — a stale mapping silently misattributes insider activity to the wrong or a delisted ticker. Refresh the mapping table on a defined cadence (e.g., monthly).
- **Committee mapping staleness:** committee assignments change with each new Congress (every 2 years) and mid-session reshuffles — this table needs an owner and a refresh trigger, not a "set once" assumption.
- **Disclosure amount ranges:** congressional disclosures report dollar amounts as broad ranges (e.g., "$15,001–$50,000"), not exact figures — decide a consistent convention (midpoint? lower bound? keep both bounds and let the model use both) rather than arbitrarily picking one number.
- **Small-sample noise for smaller tickers:** cluster buying (≥3 insiders) may simply never trigger for companies with very few executives/board members — consider whether the threshold should scale with company size/board size rather than being a fixed "3" for every ticker in the universe.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Spike** | Pull a sample of Form 4s, validate transaction-code filtering logic by hand | 1 day |
| **Phase 1 — MVP (insider only)** | Form 4 poller + cluster aggregator + DB, no congressional data yet | 3–4 days |
| **Phase 2 — Congressional data** | Aggregator API integration (or raw parsing) + committee mapping | 3–5 days |
| **Phase 3 — Validation** | Disclosure-lag-aware backtest (§7) — this is the phase to not rush | 4–6 days |
| **Phase 4 — Integration** | `feature_builder.py` wiring | 1–2 days |

---

## 10. Integration Contract with `feature_builder.py`

```python
SELECT ticker, cluster_insider_buy_30d, insider_buy_dollar_volume_30d,
       abnormal_political_buying, political_buy_dollar_volume_30d
FROM insider_whale_scores
WHERE ticker = %(ticker)s AND as_of_date <= %(as_of_date)s
ORDER BY as_of_date DESC
LIMIT 1;
```
As with all other agents: point-in-time correctness matters here specifically because `disclosed_date` (not `transaction_date`) must be what drives `as_of_date` availability for the congressional feature — re-confirm this is enforced upstream in `cluster_aggregator.py`, not just left to the read query.

---

## 11. Success Metrics

- Insider cluster-buy backtest shows statistically meaningful forward-return separation vs. a sector/size-matched control group, using recent-years data.
- Congressional trade backtest, properly disclosure-lag-adjusted, shows a real (even if modest) effect — if it doesn't clear this bar, deprioritize or drop `abnormal_political_buying` rather than keeping a feature with no demonstrated edge.
- Pipeline runs daily with <1% missed days.
- Mapping tables (CIK↔ticker, committee membership) have a documented refresh owner/cadence.

---

## Open Questions

- Build congressional parsing in-house (free, but high effort/lower quality) or pay for Quiver Quantitative (recommended)?
- Should the insider cluster threshold scale with company/board size rather than a fixed count of 3?
- Given the disclosure-lag issue, is `abnormal_political_buying` worth keeping in the model at all, or should it wait until backtest results (§7.3) come back?
