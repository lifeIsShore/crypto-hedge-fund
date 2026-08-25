# 01 — The "AI Analyst" Agent (Earnings & SEC Filings)

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py`, ticker universe config (126 tickers)

---

## 1. Concept & Hypothesis

Traditional fundamental data (EPS, revenue, margins) is backward-looking and identical for every market participant the moment it's released — there's no edge in reading a number everyone else can read. The edge is in the *unstructured text surrounding the numbers*: filings and earnings calls are written/spoken by people who know more than the numbers show, and their language leaks that information before it shows up in guidance cuts or the next quarter's print.

**Hypothesis:** Tone shifts in scripted corporate text (MD&A) and behavioral shifts in unscripted speech (Q&A evasiveness) are leading indicators of fundamental deterioration or improvement that price has not yet fully incorporated, because most market participants skim or ignore this text rather than systematically scoring it.

**Why this edge might still exist:** Reading 126 tickers' worth of filings and call transcripts every quarter, consistently and unemotionally, is tedious and expensive for a human team. It's exactly the kind of repetitive-but-nuanced task LLMs are well suited to, and most retail and even many small funds don't do it systematically.

**Why it might NOT exist / risks to the thesis:**
- Academic literature (e.g., Loughran-McDonald sentiment work, "obfuscation hypothesis" papers on earnings calls) already documents these effects — some of this may already be priced in by funds using similar NLP techniques.
- Sell-side analysts already probe evasive answers live on the call; the info may already be in the stock by the time you score it, unless you're faster.

---

## 2. Data Sources

| Source | Data | Access Method | Cost |
|---|---|---|---|
| SEC EDGAR | 10-K, 10-Q full text | Free public API (`https://www.sec.gov/cgi-bin/browse-edgar`, EDGAR full-text search API) | Free |
| SeekingAlpha / Motley Fool | Earnings call transcripts | Scraping (ToS risk, see §5) or paid transcript API (AlphaSense, Quartr, Discountingcashflows.com) | $0–$500+/mo depending on provider |
| Transcript APIs (alt.) | Same, cleaner | Quartr API, Finnhub, or Polygon.io transcripts endpoint | ~$50–$250/mo |

**Recommendation:** Start with SEC EDGAR (free, ToS-clean) for MD&A, and a paid transcript API (Finnhub or Polygon) for calls rather than scraping SeekingAlpha directly — avoids ToS violations and is more stable long-term (see Legal & Compliance below).

---

## 3. Core Features

### 3.1 MD&A Sentiment Shift
- **Input:** Current quarter MD&A section vs. prior quarter MD&A section (10-Q/10-K).
- **LLM task:** Diff-style comparison; score tone shift -1.0 to +1.0; extract added/removed hedge-language phrases (e.g. "macroeconomic headwinds," "supply chain uncertainty").
- **Output:** `mda_sentiment_delta` (float, -1.0 to 1.0)
- **Prior evidence:** Directionally supported by academic literature on 10-K tone and future returns (Loughran-McDonald word lists, Cohen/Malloy/Nguyen "text similarity" work on filing changes).

### 3.2 Earnings Call Evasiveness Score
- **Input:** Q&A section of earnings call transcript only (not prepared remarks).
- **LLM task:** Score CEO/CFO response directness, hedging, and answer length relative to question complexity, 0–1.
- **Output:** `management_evasiveness_score` (float, 0–1)
- **Prior evidence:** Consistent with academic work on "linguistic obfuscation" in earnings calls (e.g., Larcker & Zakolyukina).

---

## 4. Architecture

### 4.1 Pipeline (detailed)

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐    ┌────────────────┐
│ Cron (weekly)│───▶│ EDGAR/API poll│───▶│ Text cleaner  │───▶│ LLM scorer   │───▶│ SQL: ai_fundamental_scores │
│ APScheduler  │    │ per ticker    │    │ (strip HTML/  │    │ (JSON schema │    │  → feature_builder.py     │
└─────────────┘    └──────────────┘    │ XBRL tags,    │    │  enforced)   │    └────────────────┘
                                        │ isolate MD&A  │    └───────────────┘
                                        │ / Q&A section)│
                                        └──────────────┘
```

### 4.2 Components

1. **Scheduler:** `APScheduler` or a simple cron entry, weekly run checking for new filings/transcripts for the 126-ticker universe.
2. **Fetcher service (`edgar_fetcher.py`):**
   - Uses SEC EDGAR full-text search + submissions API to detect new 10-Q/10-K per CIK.
   - Rate-limit compliant: SEC requires a `User-Agent` header with contact info and caps at 10 req/sec — build in a token-bucket limiter regardless, target ~2 req/sec to be safe.
   - Downloads raw filing, extracts MD&A section via regex/heading detection (Item 7 for 10-K, Item 2 for 10-Q) — filings are inconsistent, so this needs a fallback: if section headers aren't found via regex, fall back to LLM-based section extraction (more expensive but robust).
3. **Transcript fetcher (`transcript_fetcher.py`):** Pulls from chosen transcript API, isolates the Q&A portion (usually clearly delimited by "Question-and-Answer Session" heading).
4. **Cleaner (`text_cleaner.py`):** Strips HTML/XBRL tags, footnotes, tables (tables handled separately if needed later), normalizes whitespace.
5. **LLM microservice (`llm_scorer.py`):**
   - Model choice: cheap/fast tier for this — Gemini Flash, Claude Haiku, or a locally hosted Llama 3 8B if volume gets high enough to justify self-hosting economics.
   - **Strict JSON schema enforcement** — use function calling / tool-use mode where the API supports it, not prompt-and-hope. Validate output against a Pydantic model; reject and retry (max 2 retries) on schema violation.
   - **Determinism:** set `temperature=0` for scoring consistency across runs; log raw model output alongside parsed score for auditability.
6. **Database writer:** Writes to `ai_fundamental_scores` (schema below).

### 4.3 Database Schema

```sql
CREATE TABLE ai_fundamental_scores (
    id                          BIGSERIAL PRIMARY KEY,
    ticker                      VARCHAR(10) NOT NULL,
    filing_type                 VARCHAR(10) NOT NULL,        -- '10-K', '10-Q', 'CALL'
    filing_date                 DATE NOT NULL,
    period_end_date             DATE NOT NULL,
    mda_sentiment_delta         FLOAT,
    mda_hedge_phrases_added     TEXT[],
    mda_hedge_phrases_removed   TEXT[],
    management_evasiveness_score FLOAT,
    raw_llm_output              JSONB,                       -- full response, for audit/debug
    model_used                  VARCHAR(50),
    prompt_version              VARCHAR(20),                 -- track prompt iterations
    created_at                  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(ticker, filing_type, period_end_date)
);
CREATE INDEX idx_afs_ticker_date ON ai_fundamental_scores(ticker, period_end_date);
```

`prompt_version` matters more than it looks — when you tweak the prompt, historical scores become non-comparable to new ones unless you either version them or backfill. Decide this now, not later.

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| SEC EDGAR | **Low** | Public data, explicit API, just follow rate-limit/User-Agent rules |
| Paid transcript API (Finnhub/Polygon/Quartr) | **Low** | Licensed data, ToS covers programmatic use — confirm the specific plan allows automated/algorithmic use, not just display |
| Scraping SeekingAlpha/Motley Fool directly | **Medium-High** | Both have ToS clauses restricting scraping/automated access; SeekingAlpha has pursued legal action against scrapers before. Recommend avoiding for a production system — use a licensed API instead |

**Action item:** Before building, read the ToS of whichever transcript provider you pick, specifically the clause on "automated access" / "data mining" — some free tiers explicitly prohibit programmatic use even if the site is technically scrapable.

---

## 6. Cost Estimate

Assume 126 tickers, quarterly filings (4x/year) + quarterly calls (4x/year) = ~8 LLM scoring events/ticker/year ≈ 1,008 events/year.

| Item | Estimate |
|---|---|
| LLM API (Gemini Flash / Claude Haiku, ~15K input tokens/doc avg) | ~1,008 calls × 15K tokens × ~$0.15/1M tokens ≈ **$2–5/year** (trivially cheap at this tier) |
| Transcript API subscription | **$50–250/month** depending on provider |
| SEC EDGAR | Free |
| Compute (scheduler/cleaner, can run on existing infra) | Negligible if self-hosted |
| **Total** | **~$600–3,000/year**, dominated by the transcript subscription, not the LLM calls |

Cost is not the constraint here — data licensing and engineering time are.

---

## 7. Backtesting & Validation Plan

Before this feeds live capital allocation:

1. **Historical backfill:** Run the pipeline against 3–5 years of historical filings/transcripts for the universe (EDGAR has full history; transcript API history varies — check depth of paid plan).
2. **Standalone signal test:** Before folding into the ML model, test `mda_sentiment_delta` and `management_evasiveness_score` in isolation — bucket tickers into quintiles by score, measure forward 30/60/90-day returns. Confirm the sign and magnitude match the hypothesis (negative delta → underperformance).
3. **Decay/overlap check:** Confirm the signal isn't just re-deriving existing price momentum (correlate with existing momentum features; if correlation is very high, it's redundant, not incremental).
4. **Feature importance in the ML model:** Once integrated, check SHAP/feature-importance rankings in the existing model rather than assuming it's additive.
5. **Out-of-sample walk-forward test:** Standard walk-forward validation consistent with however the rest of the model is validated (avoid look-ahead bias — the filing/transcript must be timestamped to when it was *actually available*, not the period-end date).

---

## 8. Failure Modes & Edge Cases

- **Filing section headers vary by company** (some skip "MD&A" naming conventions, foreign private issuers file 20-F/6-K instead of 10-K/10-Q) — build a fallback extraction path, and explicitly exclude or flag tickers that file non-standard forms.
- **LLM hallucination on scores:** mitigate with `temperature=0`, schema validation, and periodic spot-checking of raw model output against source text (sample 5–10% monthly).
- **Transcript API downtime/gaps:** build a "missing data" flag rather than silently skipping — a gap should not be interpreted as a neutral score by the downstream model.
- **Prompt drift:** any prompt change should bump `prompt_version` and ideally be re-validated against a fixed historical sample before rollout.
- **Small/thinly covered tickers:** may not have transcript coverage on cheaper API tiers — decide the fallback (skip scoring vs. flag as null vs. upgrade plan).

---

## 9. Build Timeline (suggested phases)

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Spike** | Manually pull 5 tickers' filings, hand-test the prompt in a notebook, sanity-check scores against known outcomes | 1–2 days |
| **Phase 1 — MVP** | EDGAR fetcher + MD&A extraction + LLM scorer for 10-Qs only, write to DB, no transcripts yet | 3–5 days |
| **Phase 2 — Transcripts** | Add transcript API integration + evasiveness scoring | 2–3 days |
| **Phase 3 — Validation** | Historical backfill + standalone signal backtest (§7) | 3–5 days |
| **Phase 4 — Integration** | Wire into `feature_builder.py`, add to production cron | 1–2 days |
| **Phase 5 — Monitoring** | Add alerting for pipeline failures, missing data, and periodic raw-output spot checks | 1–2 days |

---

## 10. Integration Contract with `feature_builder.py`

`feature_builder.py` should read the **latest available** row per ticker as of the feature computation date (point-in-time correct — join on `filing_date <= as_of_date`, not `period_end_date`, to avoid look-ahead bias). Suggested join:

```python
SELECT DISTINCT ON (ticker) *
FROM ai_fundamental_scores
WHERE ticker = %(ticker)s AND filing_date <= %(as_of_date)s
ORDER BY ticker, filing_date DESC;
```

---

## 11. Success Metrics (how you'll know this is working)

- Standalone quintile spread (top vs. bottom `mda_sentiment_delta` bucket) shows statistically meaningful forward-return separation in backtest.
- Feature shows up with non-trivial importance in the trained model (not just noise the model ignores).
- Pipeline uptime: >95% successful weekly runs without manual intervention.
- Spot-check agreement rate: human review of raw LLM output vs. score agrees >90% of the time on a monthly sample.

---

## Open Questions (to resolve before building)

- Which transcript API — Finnhub, Polygon, or Quartr? (Affects cost, coverage of your 126 tickers, and history depth.)
- Self-host Llama 3 8B or just use Haiku/Flash API given the cost is trivial either way?
- Where does `ai_fundamental_scores` live — existing project DB or a new schema?
