# 02 — Real-Time News & Narrative Sentiment

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py`, ticker universe config (126 tickers)

---

## 1. Concept & Hypothesis

Price-based momentum models react *after* a move has already started. News-driven NLP tries to react to the *cause* — classifying what a breaking article means for margins/revenue before the market has fully repriced it. The edge is speed plus consistent, unemotional classification across every headline in the universe, all day.

**Hypothesis:** In the minutes-to-hours window after a news event, there is a lag between the information content of the article and full price discovery, especially for smaller-cap or less-covered names in the 126-ticker universe. An automated classifier that's faster and more consistent than a human desk can capture part of that lag.

**Why this edge might still exist:** Most systematic news-sentiment products (RavenPack, Bloomberg NLP, etc.) are expensive and tuned for large-cap liquid names; a custom, ticker-universe-specific model can plausibly do better in exactly the names those products under-serve.

**Why it might NOT exist / risks to the thesis:**
- High-frequency trading firms already do this at machine speed (sub-second) for liquid large caps — for those names, your latency will not compete.
- Headline-driven moves are often already efficient for widely-covered names within seconds; the edge, if any, is more likely in mid/small-cap or thinly-covered tickers where fewer algos are watching.
- Retail-momentum "fade the euphoria" logic (§3.2) is a crowded trade idea — its historical edge may have compressed.

---

## 2. Data Sources

| Source | Data | Access Method | Cost |
|---|---|---|---|
| Yahoo Finance / Finviz RSS | Ticker-specific news headlines + body links | Free RSS | Free |
| Benzinga / Polygon.io News API | Faster, cleaner structured news feed | Paid API | ~$30–200/mo |
| Reddit (r/wallstreetbets, r/investing) | Retail mention volume + sentiment | Official Reddit API (PRAW) | Free tier available, rate-limited |
| X (Twitter) API | Retail/influencer mention volume | Paid API (Basic/Pro tiers) | $100–5,000+/mo depending on tier — **this is the major cost driver of this whole module** |

**Recommendation:** Start with free RSS (Yahoo/Finviz) + Reddit's official API for an MVP. Treat X/Twitter as an optional Phase 2 add-on given its cost — validate the RSS+Reddit signal alone first before paying for X access.

---

## 3. Core Features

### 3.1 Fundamental News Impact Score
- **Input:** Full body text of a breaking article for a tracked ticker.
- **LLM task:** Classify expected impact on future operating margin and revenue, -1.0 to +1.0 each.
- **Output:** `news_margin_impact_score`, `news_revenue_impact_score` (floats)

### 3.2 Retail Momentum Divergence
- **Input:** Rolling count + sentiment of ticker mentions on Reddit/X.
- **Logic:** High mention volume + high sentiment + no confirming institutional flow ⇒ classic retail "pump," historically followed by reversion.
- **Output:** `retail_euphoria_flag` (boolean)
- **Caveat:** Needs an "institutional buying" proxy to compare against (e.g., dollar volume vs. average, or block trade prints) — otherwise this is just a retail-sentiment flag with an unverified label, not actually a divergence signal. Define that proxy explicitly before building.

---

## 4. Architecture

### 4.1 Pipeline

```
┌────────────────┐    ┌───────────────┐    ┌──────────────┐    ┌─────────────────┐
│ RSS/WebSocket  │───▶│ Dedup + queue │───▶│ LLM triage   │───▶│ Decay-weighted   │
│ poller (per    │    │ (avoid double │    │ (fast/cheap  │    │ write to DB      │
│ ticker, 24/7)  │    │ scoring same  │    │ model)       │    │ → feature_builder│
└────────────────┘    │ article)      │    └──────────────┘    └─────────────────┘
                       └───────────────┘
```

### 4.2 Components

1. **Streaming ingester (`news_poller.py`):** Polls RSS every 1–5 min per source, or uses a WebSocket feed if the paid provider offers one (Benzinga does). Maintain a `seen_article_hash` set (hash of URL + title) to avoid reprocessing.
2. **Dedup/queue:** Push new articles into a lightweight queue (Redis list, or just a DB "pending" table) — decouples ingestion speed from LLM throughput.
3. **LLM triage (`news_scorer.py`):** Small/fast model (Gemini Flash, Haiku), `temperature=0`, strict JSON schema. Target <5s per article end-to-end.
4. **Social scraper (`social_tracker.py`):** Separate cadence (e.g., every 15 min) — pulls mention counts/sentiment from Reddit API and, if enabled, X API.
5. **Decay engine:** Exponential decay, 7-day half-life, applied at read-time (via a `computed_at` timestamp and decay formula in the query) rather than physically overwriting stored scores — keeps raw history intact for backtesting while still giving `feature_builder.py` a decayed current value.

### 4.3 Database Schema

```sql
CREATE TABLE news_sentiment_scores (
    id                      BIGSERIAL PRIMARY KEY,
    ticker                  VARCHAR(10) NOT NULL,
    article_url             TEXT NOT NULL,
    article_hash            VARCHAR(64) NOT NULL UNIQUE,   -- dedup key
    published_at            TIMESTAMPTZ NOT NULL,
    scored_at               TIMESTAMPTZ DEFAULT now(),
    news_margin_impact_score FLOAT,
    news_revenue_impact_score FLOAT,
    source                  VARCHAR(50),
    model_used              VARCHAR(50),
    prompt_version          VARCHAR(20)
);
CREATE INDEX idx_news_ticker_time ON news_sentiment_scores(ticker, published_at);

CREATE TABLE retail_momentum_scores (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              VARCHAR(10) NOT NULL,
    window_start        TIMESTAMPTZ NOT NULL,
    window_end          TIMESTAMPTZ NOT NULL,
    mention_count       INT,
    mention_sentiment   FLOAT,
    institutional_proxy FLOAT,             -- e.g. relative dollar volume
    retail_euphoria_flag BOOLEAN,
    source_breakdown    JSONB               -- {reddit: n, twitter: n}
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| Yahoo Finance / Finviz RSS | **Low-Medium** | RSS feeds are generally intended for consumption, but check current ToS — Yahoo has tightened API access before; have a fallback source ready |
| Benzinga / Polygon News API | **Low** | Licensed, built for programmatic use |
| Reddit API (PRAW) | **Low** | Official API, follow rate limits (Reddit changed API pricing in 2023 — confirm current free-tier limits before relying on it) |
| X/Twitter API | **Low (if paid)** | Must use official paid API tier for programmatic access — scraping X directly is both against ToS and technically blocked in most cases |

**Action item:** Reddit and X have both changed API terms/pricing significantly in recent years — re-verify current pricing and rate limits at build time rather than trusting older documentation.

---

## 6. Cost Estimate

| Item | Estimate |
|---|---|
| LLM triage (assume ~500 articles/week across 126 tickers, ~2K tokens each) | ~500 × 2K × 4 weeks × ~$0.15/1M tokens ≈ **~$1–2/month** (trivial) |
| Benzinga/Polygon News API | **$30–200/month** |
| Reddit API | Free tier likely sufficient at this scale |
| X/Twitter API (optional, Phase 2) | **$100–5,000+/month** — validate signal without it first |
| **Total (MVP, no X)** | **~$50–250/month** |
| **Total (with X)** | **$150–5,000+/month** |

---

## 7. Backtesting & Validation Plan

1. **Historical backfill:** Harder than filing-based signals — RSS/news APIs often don't offer deep historical archives. Check what history your chosen news API provider actually offers before assuming you can backtest years back; you may need to run live for a period to accumulate your own history.
2. **Event study:** For a sample of scored articles, measure abnormal returns in the 1hr/1day/3day windows following `scored_at`, bucketed by score sign and magnitude.
3. **Cross-check against existing momentum features:** confirm this isn't redundant with price-based momentum already in the model.
4. **Retail euphoria flag validation:** Specifically backtest whether stocks flagged `retail_euphoria_flag=True` actually underperform in the following 5–10 days — this is the core testable claim in §3.2 and should not be assumed true without validation.

---

## 8. Failure Modes & Edge Cases

- **Duplicate/syndicated articles:** the same story often gets republished across outlets — dedup by title similarity, not just exact hash, or you'll multiply-count the same event.
- **Low-quality/clickbait headlines:** LLM may over-react to sensational framing not backed by real fundamental content — consider scoring the article body, not just the headline.
- **API rate-limit throttling during high-news-volume days** (e.g., broad market selloffs) — build a backpressure/queue system so the pipeline degrades gracefully (delayed scoring) rather than dropping articles.
- **Reddit/X policy changes:** both platforms have changed API terms abruptly before; design the social tracker with an interface that could swap providers (e.g., add StockTwits as a fallback) without a full rewrite.
- **Decay function edge cases:** make sure `feature_builder.py` handles the "no recent news" case (score decays to ~0) distinctly from "no data ever" (null) — these are semantically different.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Spike** | Hand-score ~50 headlines, validate the prompt against obvious cases | 1 day |
| **Phase 1 — MVP** | RSS poller + dedup + LLM triage + DB write, no social data | 3–4 days |
| **Phase 2 — Social** | Reddit mention tracking + euphoria flag logic | 2–3 days |
| **Phase 3 — Validation** | Event study backtest (§7) | 3–4 days |
| **Phase 4 — Integration** | Decay-weighted read query into `feature_builder.py` | 1–2 days |
| **Phase 5 (optional) — X/Twitter** | Only after Phase 3 shows the base signal has value | 2–3 days + ongoing subscription cost |

---

## 10. Integration Contract with `feature_builder.py`

```python
# Decayed score at query time — half-life 7 days
SELECT ticker,
       SUM(news_margin_impact_score * EXP(-LN(2) * EXTRACT(EPOCH FROM (%(as_of)s - published_at)) / (7*86400))) AS decayed_margin_score
FROM news_sentiment_scores
WHERE ticker = %(ticker)s AND published_at <= %(as_of)s
GROUP BY ticker;
```
Point-in-time correctness note: always filter on `published_at <= as_of_date` to prevent look-ahead bias in backtests.

---

## 11. Success Metrics

- Statistically significant abnormal-return separation in the event study (§7.2).
- `retail_euphoria_flag` shows measurable forward underperformance in backtest — if it doesn't, cut the feature rather than ship it on the concept's plausibility alone.
- Pipeline latency: median time from article publish to scored DB row < 2 minutes.
- Uptime >99% (this is a live/streaming component, higher bar than the weekly-batch agents).

---

## Open Questions

- Benzinga vs. Polygon vs. another provider — compare coverage of your specific 126 tickers, not just headline volume.
- What's the actual "institutional buying proxy" for the divergence signal — relative volume, options flow, or something else?
- Is X/Twitter worth the cost at all, or does Reddit + news alone capture most of the signal?
