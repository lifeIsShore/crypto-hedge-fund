# 07 — Supply Chain & Macro NLP

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py` (sector-broadcast feature, similar pattern to `06`)

---

## 1. Concept & Hypothesis

For manufacturing, hardware, and retail names, COGS pressure from supply-chain disruption is a leading indicator of margin misses that shows up in earnings well after the disruption itself was newsworthy. Scanning shipping/logistics news systematically can flag sector-wide exposure before the market has connected a logistics headline to specific tickers' upcoming earnings.

**Hypothesis:** There's a lag between "port strike / shipping lane blockage reported in trade press" and "market has fully repriced the affected sector's margin risk," and that lag is wide enough (days to weeks, not seconds) to be tactically actionable — a meaningfully more realistic latency assumption than doc `06`'s FOMC scenario, since this isn't a live-market-moving event in the same way.

**Why this edge is plausible:** Supply-chain/logistics news is less universally watched by equity traders than macro/Fed news — it's genuinely a specialist beat (FreightWaves, trade press), so the audience overlap with people actively trading the affected equities is smaller, leaving more room for a systematic mapping-to-sector approach to add value.

**Key risk to the thesis:** The mapping from "disruption event" to "which specific companies in my 126-ticker universe are actually exposed" is the hard part — a generic "semiconductor shortage" flag is nearly useless without knowing which of your specific tickers source which specific inputs from which specific regions/ports. This mapping work is where most of the real effort in this agent should go, more so than the news-scanning itself.

---

## 2. Data Sources

| Source | Data | Access Method | Cost |
|---|---|---|---|
| FreightWaves | Shipping/logistics news | RSS or scraping (check ToS — trade publications sometimes gate premium content) | Free (headlines) to paid (full articles/premium) |
| Commodities news (general financial news APIs) | Lumber, copper, oil, etc. | Same news API as doc `02` (Benzinga/Polygon) — can likely reuse infrastructure | Shared cost with doc `02` if built together |
| Freightos Baltic Index (FBX) | Container freight pricing index | Freightos public index page / API | Free (public index) to paid (granular API) |
| Drewry / other freight indices | Alternative/supplementary freight pricing | Paid subscription | Varies |

**Recommendation:** Reuse the news ingestion infrastructure from doc `02` (same RSS/API polling pattern) rather than building a separate pipeline — this is largely the same kind of system pointed at a different set of feeds, and sharing the fetcher/dedup/LLM-triage components reduces both build time and maintenance burden.

---

## 3. Core Features

### 3.1 Commodity & Logistics Bottleneck Flag
- **Mechanism:** LLM scans shipping/logistics news, identifies disruptions, maps to affected industries.
- **Output:** `supply_chain_disruption_risk` (bool), broadcast to sector-mapped tickers.
- **Improvement on the original plan:** Rather than a single boolean, emit a **severity score** (e.g., 0–1) and an **estimated duration** category (transient/days, sustained/weeks, structural/months+) — a two-day minor port slowdown and a months-long canal blockage are very different in trading implications, and collapsing both into one boolean loses that distinction.

### 3.2 Input Cost Inflation Proxy
- **Mechanism:** Track freight index levels (FBX, Drewry) and commodity price moves.
- **Output:** `freight_cost_spike` (bool) — similarly, consider a continuous `freight_cost_zscore` (how many standard deviations above trailing average) rather than only a binary spike flag, giving the model magnitude information.

---

## 4. Architecture

### 4.1 Pipeline

```
┌────────────────┐   ┌───────────────┐   ┌──────────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ Logistics/     │──▶│ LLM: disruption│──▶│ Sector mapping    │──▶│ Broadcast to     │──▶│ supply_chain_scores    │
│ commodity news │   │ detection +   │   │ (industry → your  │   │ exposed tickers  │   │ → feature_builder      │
│ + freight index│   │ severity score│   │ 126-ticker map)   │   │ in universe      │   │                       │
│ poller         │   └──────────────┘   └──────────────────┘   └─────────────────┘   └──────────────────────┘
└────────────────┘
```

### 4.2 Components

1. **News poller (`logistics_news_poller.py`):** Shares architecture with `news_poller.py` from doc `02` — same dedup/queue pattern, different source list.
2. **Disruption classifier (`disruption_classifier.py`):** LLM extracts disruption type, affected industries (free-text from the model), severity, estimated duration category.
3. **Industry-to-ticker mapper (`sector_exposure_map.py`) — the critical, most labor-intensive component:** A maintained mapping table from generic industry categories (as the LLM will phrase them — "Automotive," "Consumer Electronics," etc.) to your specific 126 tickers, ideally with an **exposure weight**, not just a binary "exposed/not exposed" — e.g., a company that sources 80% of a key component from an affected region should be weighted differently from one with only marginal exposure. This mapping realistically needs to be built and maintained partly by hand (using 10-K supply-chain disclosure language as a starting point, which conveniently overlaps with doc `01`'s filing-reading infrastructure) rather than fully automated.
4. **Freight index tracker (`freight_index_tracker.py`):** Simple daily/weekly pull of FBX and any other subscribed indices, computes rolling z-score.
5. **Broadcast writer:** Applies the disruption flag/score to all tickers matching the affected industries per the exposure map, weighted by exposure weight.

### 4.3 Database Schema

```sql
CREATE TABLE supply_chain_events (
    id                      BIGSERIAL PRIMARY KEY,
    event_date              DATE NOT NULL,
    disruption_type         VARCHAR(100),        -- 'port_strike', 'canal_blockage', 'semiconductor_shortage', etc.
    affected_industries      TEXT[],
    severity_score          FLOAT,                -- 0-1
    duration_category       VARCHAR(20),          -- 'transient', 'sustained', 'structural'
    source_article_url      TEXT,
    raw_llm_output          JSONB,
    model_used              VARCHAR(50),
    prompt_version          VARCHAR(20)
);

CREATE TABLE sector_exposure_map (
    ticker                  VARCHAR(10) NOT NULL,
    industry_category       VARCHAR(100) NOT NULL,
    exposure_weight         FLOAT,                -- 0-1, how exposed this ticker is to this industry category's disruptions
    last_reviewed_date      DATE,                 -- manual maintenance tracking
    source_notes            TEXT,                 -- e.g. "per 10-K supply chain disclosure, FY2025"
    PRIMARY KEY (ticker, industry_category)
);

CREATE TABLE supply_chain_scores (
    ticker                       VARCHAR(10) NOT NULL,
    as_of_date                   DATE NOT NULL,
    supply_chain_disruption_risk FLOAT,           -- weighted severity, exposure-adjusted
    freight_cost_zscore          FLOAT,
    PRIMARY KEY (ticker, as_of_date)
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| FreightWaves RSS/free content | **Low** | Trade press RSS generally intended for syndication; check if premium content requires a subscription (scraping paywalled content would be higher risk) |
| General commodity news (shared with doc `02`'s provider) | **Low** | Already licensed if built on the same provider |
| Freightos Baltic Index | **Low** | Publicly published index, designed for reference/citation |
| Drewry or other paid freight indices | **Low** | Licensed subscription data |

Low overall risk — the main thing to watch is not scraping FreightWaves' paywalled premium content without a subscription.

---

## 6. Cost Estimate

| Item | Estimate |
|---|---|
| News ingestion | Shared cost with doc `02` if built together — marginal incremental cost is low |
| LLM classification | Similar trivial cost profile to other LLM-triage agents, **~$1–5/month** |
| Freight index API (if going beyond the free public FBX index) | **$0–200/month** |
| Manual exposure-mapping labor | Not a recurring cash cost, but budget real engineering/analyst time — this is the actual bottleneck, not compute or API spend |
| **Total (cash cost)** | **~$0–200/month**, low; **real cost is the mapping-table build/maintenance effort** |

---

## 7. Backtesting & Validation Plan

1. **Historical disruption event catalog:** Build a small hand-curated list of known historical supply-chain events (2021 Suez blockage, 2021-22 chip shortage, various port labor actions) with known dates and known affected sectors, and validate the classifier correctly identifies and categorizes these before trusting live output on novel events.
2. **Exposure-weighted backtest:** For historical disruption events, measure forward margin/earnings performance of exposure-mapped tickers (weighted by `exposure_weight`) vs. non-exposed tickers in the same broad sector — this directly tests whether the exposure mapping is doing real work versus a much simpler "just short the whole sector" approach.
3. **Freight index backtest:** Test whether `freight_cost_zscore` spikes historically preceded margin misses in freight-sensitive names (retail, consumer goods) with a plausible lag (one to two quarters, roughly matching typical inventory/shipping cycles).
4. **Duration-category validation:** Confirm that `duration_category` (transient/sustained/structural) meaningfully differentiates outcome magnitude — a structural disruption should show a larger and more persistent effect than a transient one; if the backtest doesn't show this differentiation, the category may need re-definition.

---

## 8. Failure Modes & Edge Cases

- **Exposure map staleness (the biggest risk):** supply chains change — a company's key suppliers/regions this year may differ from last year (diversification post-2021 chip shortage is a well-documented industry trend). The `last_reviewed_date` field exists specifically to force periodic review; without an enforced review cadence, this table will silently go stale and start generating false exposure signals.
- **LLM industry-category inconsistency:** the LLM may phrase the same underlying industry differently across different articles ("Auto," "Automotive," "Automobile Manufacturing") — normalize categories with a controlled vocabulary/enum passed in the prompt (a fixed list of allowed industry tags) rather than accepting free text, or the sector-exposure join will silently miss matches.
- **Over-broadcasting:** a disruption genuinely affecting one narrow sub-industry could get broadcast too broadly if `affected_industries` extraction is too coarse — favor a more granular, LLM-extracted specific list over generic top-level sector tags.
- **Freight index data gaps/methodology changes:** index providers occasionally revise methodology — a sudden jump in the z-score could reflect a methodology change rather than a real market move; spot-check unusual jumps against news before trusting them blindly.
- **Double counting with doc `02`:** if both this agent and the general news-sentiment agent (`02`) pick up the same underlying event (e.g., a supply chain story that's also just "bad news" in the general feed), the model could see correlated/redundant signal from two features describing the same event — worth checking for this overlap in the eventual feature-importance analysis.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Exposure mapping v1** | Hand-build initial sector_exposure_map from 10-K supply-chain disclosures for the 126-ticker universe — do this first, it's the real bottleneck | 5–8 days (analyst-heavy, not pure engineering) |
| **Phase 1 — News/classification pipeline** | Reuse doc `02` infra, point at logistics feeds, build disruption classifier with controlled industry vocabulary | 2–3 days (faster if `02` is already built) |
| **Phase 2 — Freight index tracker** | FBX/Drewry integration + z-score calc | 1–2 days |
| **Phase 3 — Broadcast logic** | Exposure-weighted score propagation to mapped tickers | 2 days |
| **Phase 4 — Validation** | Historical event catalog validation + exposure-weighted backtest (§7) | 4–5 days |
| **Phase 5 — Integration** | `feature_builder.py` wiring | 1 day |
| **Ongoing — Exposure map maintenance** | Quarterly review cadence tied to 10-K filing cycles | Recurring, ~1 day/quarter |

---

## 10. Integration Contract with `feature_builder.py`

```python
SELECT ticker, supply_chain_disruption_risk, freight_cost_zscore
FROM supply_chain_scores
WHERE ticker = %(ticker)s AND as_of_date <= %(as_of_date)s
ORDER BY as_of_date DESC
LIMIT 1;
```
Standard point-in-time-safe pattern, consistent with the rest of the feature set.

---

## 11. Success Metrics

- Classifier correctly identifies and categorizes the hand-curated historical disruption catalog (§7.1) — treat this as a pre-launch gate, not an ongoing metric.
- Exposure-weighted backtest shows meaningfully more predictive power than a naive "whole sector" approach — if it doesn't, the mapping effort (the most expensive part of this build) isn't earning its cost, and a simpler sector-level flag might be good enough.
- `sector_exposure_map` has a documented review completed within the last quarter for >90% of mapped tickers at any given time.
- Freight z-score backtest shows the hypothesized lagged relationship to margin outcomes in freight-sensitive sectors.

---

## Open Questions

- Should exposure mapping be entirely manual (higher quality, higher labor cost) or bootstrapped with LLM-assisted extraction from 10-K supply-chain disclosure text (faster, needs validation)? A hybrid — LLM drafts, analyst reviews — is probably the right MVP approach.
- Is there enough incremental value here over just building doc `02` (general news sentiment) well, or does supply-chain-specific mapping genuinely add distinguishable alpha? Worth validating with the exposure-weighted vs. naive-sector-flag backtest in §7.2 before over-investing in the mapping table.
- Freightos public FBX index vs. a paid granular alternative (Drewry, etc.) — is the free tier sufficient, or does the incremental cost buy meaningfully better signal?
