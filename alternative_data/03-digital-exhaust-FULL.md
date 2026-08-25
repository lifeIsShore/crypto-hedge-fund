# 03 — Digital Exhaust (Alternative Web Data)

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py`, ticker universe config (126 tickers)

---

## 1. Concept & Hypothesis

Fundamentals are reported quarterly; a company's real-world operating activity — hiring, web traffic, app usage — happens continuously and leaves a digital trail well before it shows up in an earnings release. This is the classic "alternative data" thesis that funds like Two Sigma and hedge funds using SimilarWeb/Thinknum-style data have pursued for years.

**Hypothesis:** Weekly changes in hiring velocity and consumer digital engagement are leading indicators of the next quarter's revenue/margin trajectory, with enough lead time (weeks to a couple months) to be actionable ahead of the print.

**Why this edge might still exist:** True for a custom-built system tracking your specific 126-ticker universe with tailored logic, cheaper than paying for a full commercial alt-data subscription (Thinknum, Yipit, etc. can run tens of thousands of dollars/year).

**Why it might NOT exist / risks to the thesis:**
- This is one of the most well-known and heavily commercialized alt-data categories — job postings and web traffic data have been sold by vendors (Thinknum, Revelio Labs, SimilarWeb) to institutional funds for years; a lot of the easy edge here is arguably already priced in for large, heavily-covered names.
- Correlation between job postings/web traffic and actual reported revenue is noisy and industry-dependent (much stronger for e-commerce/consumer than for, say, industrials or financials) — this will not be a universal signal across all 126 tickers.

---

## 2. Data Sources

| Source | Data | Access Method | Cost / Risk |
|---|---|---|---|
| Company career pages / Greenhouse / Lever | Open job listings | Scraping (Greenhouse/Lever have semi-public JSON endpoints that are more stable to scrape than raw HTML) | Free, but **ToS risk — see §5** |
| SimilarWeb | Web traffic estimates | Official SimilarWeb API (not scraping) | Paid — plans typically start ~$200+/mo for API access |
| App store rankings | iOS/Android category rankings | App Store/Play Store are technically scrapable for *public* ranking pages, or use a ranking-tracking API (App Annie/data.ai, Sensor Tower) | Free (basic scraping) to paid (proper API) |

**Recommendation:** For job postings, prefer Greenhouse/Lever's documented public JSON board endpoints (`boards-api.greenhouse.io`) over raw HTML scraping of corporate career pages — more stable, less brittle to redesigns, and less legally ambiguous since these are intentionally public job-board APIs. For web traffic, budget for the official SimilarWeb API rather than scraping their site directly (their ToS explicitly prohibits scraping their own platform).

---

## 3. Core Features

### 3.1 Job Postings Momentum
- **Input:** Weekly count of open engineering + sales roles per company.
- **Logic:** Sharp drop ⇒ hiring freeze / margin contraction signal; surge ⇒ growth conviction.
- **Output:** `job_postings_30d_momentum` (float, % change)

### 3.2 Consumer Demand Proxy (Traffic/Downloads)
- **Input:** Web traffic estimate or app store category rank, weekly.
- **Logic:** QoQ traffic decline for consumer/e-commerce names predicts revenue miss.
- **Output:** `digital_traffic_momentum` (float)
- **Caveat:** Only apply this feature to relevant sectors (consumer, e-commerce, consumer SaaS) — forcing it onto industrials/financials/utilities in the 126-ticker universe will just add noise. Build a sector applicability flag.

---

## 4. Architecture

### 4.1 Pipeline

```
┌───────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│ Weekly scraper│───▶│ Raw storage  │───▶│ Delta/momentum   │───▶│ feature_builder.py│
│ (playwright/  │    │ (snapshot per│    │ calculation      │    │                  │
│ scrapy + API  │    │ week)        │    │ (30d/90d rolling)│    │                  │
│ calls)        │    └──────────────┘    └─────────────────┘    └──────────────────┘
└───────────────┘
```

### 4.2 Components

1. **Job postings collector (`job_postings_collector.py`):** Weekly hit against each company's Greenhouse/Lever board API (or fallback scraper for companies not on those ATSs — many use Workday, custom sites, etc., which are harder and higher-risk to scrape; build a coverage map of which of the 126 tickers are even reachable this way before assuming full coverage).
2. **Web traffic collector (`traffic_collector.py`):** Weekly SimilarWeb API pull for domains mapped to each ticker.
3. **App ranking collector (`app_rank_collector.py`):** Weekly pull of category rank for mapped app IDs (only relevant for tickers with consumer apps).
4. **Snapshot storage:** Store raw weekly snapshots (not just deltas) — you need history to compute rolling momentum, and raw snapshots let you recompute if the momentum formula changes later.
5. **Delta calculator (`digital_exhaust_momentum.py`):** Computes 30d/90d rolling % change from snapshots.

### 4.3 Database Schema

```sql
CREATE TABLE digital_exhaust_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    metric_type     VARCHAR(30) NOT NULL,   -- 'job_postings_eng', 'job_postings_sales', 'web_traffic', 'app_rank_ios', 'app_rank_android'
    snapshot_date   DATE NOT NULL,
    raw_value       FLOAT,
    source          VARCHAR(30),
    UNIQUE(ticker, metric_type, snapshot_date)
);
CREATE INDEX idx_des_ticker_metric_date ON digital_exhaust_snapshots(ticker, metric_type, snapshot_date);

CREATE TABLE digital_exhaust_momentum (
    ticker                      VARCHAR(10) NOT NULL,
    as_of_date                  DATE NOT NULL,
    job_postings_30d_momentum   FLOAT,
    digital_traffic_momentum    FLOAT,
    sector_applicable           BOOLEAN,     -- whether traffic proxy is meaningful for this sector
    PRIMARY KEY (ticker, as_of_date)
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| Greenhouse/Lever board APIs | **Low** | These are intentionally public job-board endpoints designed for external consumption (embeddable widgets) — lowest-risk scraping target in this whole plan |
| Direct corporate career page scraping (non-ATS) | **Medium** | Subject to each company's own ToS/robots.txt; higher maintenance burden too (every site is different) |
| SimilarWeb (official API) | **Low** | Licensed, built for this |
| SimilarWeb (scraping the website itself) | **High — avoid.** | Explicitly against their ToS; use the official API instead, budget accordingly |
| App Store / Play Store ranking pages | **Low-Medium** | Public ranking pages are commonly scraped in practice, but check current ToS; consider a licensed ranking API (Sensor Tower, data.ai) for reliability if this becomes a core signal |

**General principle for this whole doc:** anywhere "scraping a commercial data vendor's own website" appears (SimilarWeb, app ranking sites), prefer their official paid API instead — scraping the product of a company whose business *is* data licensing is the highest-risk category here, both legally and in terms of getting blocked.

---

## 6. Cost Estimate

| Item | Estimate |
|---|---|
| Greenhouse/Lever scraping | Free (self-hosted scraper, minimal compute) |
| SimilarWeb API | **~$200–500+/month** depending on plan/domain volume |
| App ranking API (if licensed, optional) | **$0–300/month** (skip initially, use free public rank pages first) |
| Compute/hosting | Negligible, existing infra |
| **Total (MVP)** | **~$0–50/month** (job postings only, skip SimilarWeb initially) |
| **Total (full)** | **~$200–800/month** |

**Suggestion:** Ship job postings momentum first (near-zero cost, low legal risk, stable data source) and treat SimilarWeb as a Phase 2 spend once the job-postings signal is validated — don't commit to the recurring SimilarWeb cost before proving the concept.

---

## 7. Backtesting & Validation Plan

1. **Coverage audit first:** Before backtesting, determine what % of the 126-ticker universe actually has usable data (Greenhouse/Lever coverage, mapped web domains, mapped apps) — this feature may only be meaningful for a subset of the universe, and that subset should be defined explicitly.
2. **Historical backfill:** Job postings and web traffic history are hard to get retroactively (most scrapers only capture from when you start running them) — you likely need to accumulate 6–12 months of your own snapshots before a robust backtest is possible, or pay for a vendor with historical archives (e.g., Revelio Labs has historical job postings data).
3. **Lead-time test:** For the subset with usable history, measure how many days/weeks the digital-exhaust signal leads the actual earnings surprise (beat/miss), not just correlation — you specifically care about the temporal lead.
4. **Sector-conditioned backtest:** Test `digital_traffic_momentum` separately for consumer/e-commerce tickers vs. the rest of the universe — expect it to be much stronger in the former and near-noise in the latter, confirming (or disproving) the applicability flag logic in §3.2.

---

## 8. Failure Modes & Edge Cases

- **ATS coverage gaps:** companies not using Greenhouse/Lever require custom scrapers per company — high maintenance burden; decide up front whether to build custom scrapers for every ticker or accept partial universe coverage.
- **Site redesigns break scrapers silently:** build a "last successful scrape" freshness check per source/ticker and alert if a scraper hasn't produced data in >2x its expected cadence.
- **Seasonal hiring patterns:** raw job-posting counts have strong seasonality (less hiring in Dec, surges in Jan) — momentum should probably be computed YoY or seasonally adjusted, not just naive 30-day delta, or you'll get false signals every December/January.
- **Domain mapping errors:** multi-brand companies (e.g., a parent company with several consumer brands) need explicit domain-to-ticker mapping maintained manually — don't assume 1 company = 1 domain.
- **App ranking volatility:** app store category ranks are noisy day-to-day (promotions, algorithm changes) — smooth with a rolling average before computing momentum, not raw daily values.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Coverage audit** | Map which of the 126 tickers have Greenhouse/Lever boards, mapped domains, mapped apps | 2–3 days |
| **Phase 1 — MVP (jobs only)** | Job postings collector + snapshot storage + momentum calc for covered tickers | 3–4 days |
| **Phase 2 — Web traffic** | SimilarWeb API integration (after budget approval) | 2–3 days |
| **Phase 3 — App rankings** | App ranking collector (only if consumer-app tickers are a meaningful chunk of the universe) | 2 days |
| **Phase 4 — Validation** | Lead-time + sector-conditioned backtest (§7) | 4–5 days (partly gated on accumulating history) |
| **Phase 5 — Integration** | Wire into `feature_builder.py` with sector-applicability logic | 1–2 days |

---

## 10. Integration Contract with `feature_builder.py`

```python
SELECT ticker, job_postings_30d_momentum,
       CASE WHEN sector_applicable THEN digital_traffic_momentum ELSE NULL END AS digital_traffic_momentum
FROM digital_exhaust_momentum
WHERE ticker = %(ticker)s AND as_of_date <= %(as_of_date)s
ORDER BY as_of_date DESC
LIMIT 1;
```
Note the explicit `NULL` for sector-inapplicable tickers — the model should be trained to handle nulls for this feature, not have it silently zero-filled (zero implies "no change," which is a different claim than "not applicable").

---

## 11. Success Metrics

- Coverage: >60% of the 126-ticker universe has usable job-postings data (adjust threshold based on audit results).
- Lead-time test shows the signal precedes earnings surprises by a measurable, non-trivial window (not just same-day correlation).
- Sector-conditioned backtest confirms `digital_traffic_momentum` is meaningfully predictive for its intended sector subset.
- Scraper uptime: <5% of weekly runs fail silently (measured via freshness checks).

---

## Open Questions

- What fraction of the 126 tickers are actually reachable via Greenhouse/Lever, vs. needing custom scrapers or being unreachable entirely?
- Is SimilarWeb worth the recurring cost, or is a cheaper/free traffic proxy (e.g., Google Trends for brand search volume) "good enough" for an MVP?
- Should job-posting momentum be YoY-adjusted by default given seasonality, rather than a raw 30-day delta?
