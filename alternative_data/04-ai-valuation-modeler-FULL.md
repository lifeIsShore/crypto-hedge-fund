# 04 — The "AI Valuation Modeler & Strategic Reader"

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `feature_builder.py`, `04` should sit alongside `01` (both consume filings) — consider sharing the fetch/clean layer

---

## 1. Concept & Hypothesis

This is a fundamentally different kind of feature from the others: instead of a sentiment/momentum score, it's a deterministic valuation anchor (DCF fair value) plus categorical strategic flags. The point is to give the short-horizon ML model (21-day) a long-horizon fundamental "gravity" — a stock trading well below LLM-assisted DCF fair value has a structural tailwind independent of near-term momentum.

**Hypothesis:** Combining a bottom-up DCF anchor with tactical ML signals produces better risk-adjusted returns than either alone — the DCF filters out momentum trades in fundamentally overvalued names, and momentum avoids "value trap" DCF longs with no near-term catalyst.

**Why this is different from the rest of the alt-data set:** Everything else in this folder is a *feature* feeding a black-box model. This one has a deterministic, auditable core (the DCF math) with LLM used only for extracting inputs, not for the calculation itself. This distinction is important — keep it that way (see §4).

**Key risk to the thesis:** DCF fair value is extremely sensitive to the growth-rate and discount-rate assumptions — a small error in the LLM-extracted growth rate can swing fair value by 30%+. This is the single biggest risk in this whole document and needs explicit handling (see §4.2, §8).

---

## 2. Data Sources

| Source | Data | Access Method | Cost |
|---|---|---|---|
| SEC EDGAR | 10-K/10-Q financial statements (FCF, debt, cash, shares outstanding) | Free API, ideally via XBRL structured data (not raw PDF parsing) — EDGAR provides `companyfacts` API with pre-tagged structured financials | Free |
| Investor Relations sites | Investor presentations (supplementary guidance) | Manual/scraping, lower priority | Free but unstructured |
| Treasury yield APIs | Risk-free rate for WACC | FRED API (Federal Reserve Economic Data) — free, reliable, official | Free |

**Important correction to the original plan:** Use SEC EDGAR's **structured XBRL `companyfacts` API** (`data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`) for FCF, debt, cash, and shares outstanding rather than PDF-parsing raw filings with PyPDF2/Unstructured.io. The structured API gives you machine-readable, pre-tagged numbers directly from the company's own XBRL tagging — far more reliable than PDF table extraction, and removes an entire class of parsing bugs. Reserve PDF/text parsing only for the qualitative guidance extraction (growth rate commentary, strategic language), where structured data doesn't exist.

---

## 3. Core Features

### 3.1 Automated DCF Fair Value
- **Deterministic inputs (from XBRL):** FCF, shares outstanding, total debt, cash & equivalents.
- **LLM-extracted input:** Forward growth rate guidance from MD&A/investor commentary (this is the *only* LLM-derived numeric input feeding the math — everything else is structured data).
- **Deterministic math (`DCFModeler` class, pure Python, no LLM):** WACC calculation, 5-year FCF projection, terminal value, discount to present.
- **Output:** `dcf_fair_value_price`, `dcf_upside_pct`

### 3.2 Strategic Verbal Signals
- **LLM task:** Classify strategic pivot / heavy capex cycle / buyback pause from forward-looking statements.
- **Output:** `strategic_pivot` (bool), `heavy_capex_cycle` (bool), `buyback_paused` (bool)

---

## 4. Architecture

### 4.1 Pipeline

```
┌───────────────┐   ┌──────────────────┐   ┌────────────────┐   ┌─────────────────┐   ┌──────────────────┐
│ Quarterly     │──▶│ XBRL structured  │──▶│ LLM: extract    │──▶│ DCFModeler       │──▶│ ai_valuation_scores│
│ trigger (new  │   │ fetch (deterministic)│  growth rate +  │   │ (pure Python,    │   │ → feature_builder │
│ 10-Q/10-K)    │   │                  │   │ strategic flags │   │ deterministic)   │   │                  │
└───────────────┘   └──────────────────┘   └────────────────┘   └─────────────────┘   └──────────────────┘
```

### 4.2 Components

1. **Trigger (`filing_watcher.py`):** Shares the EDGAR polling logic with doc `01` if possible — avoid duplicating filing-detection code across the two agents.
2. **Structured fetcher (`xbrl_fetcher.py`):** Pulls FCF, debt, cash, shares outstanding from the `companyfacts` XBRL API. Handles the reality that XBRL tag names aren't perfectly standardized across companies (e.g., some tag "NetCashProvidedByUsedInOperatingActivities" differently) — build a tag-mapping table with fallbacks, and log/flag any ticker where expected tags aren't found rather than silently defaulting to zero.
3. **Growth rate extractor (`growth_extractor.py`):** LLM reads MD&A/guidance text, extracts a **range** (not a single point estimate) for forward growth — e.g., "8–12%" rather than forcing a single number. This directly addresses the sensitivity risk in §1.
4. **`DCFModeler` (pure Python, deterministic, unit-tested):**
   - Computes WACC using: cost of equity (CAPM with a beta source — need to decide: calculated vs. a data vendor's beta), cost of debt (from interest expense / total debt), risk-free rate (FRED), market risk premium (a fixed, documented assumption — state it in code comments, review periodically).
   - Projects FCF for 5 years using the **midpoint and both bounds** of the extracted growth range, producing three DCF outputs (bear/base/bull), not just one point estimate.
   - Applies a terminal value (Gordon Growth or exit multiple — pick one, document why).
   - Discounts to present value.
5. **Sensitivity output:** Store `dcf_fair_value_bear`, `dcf_fair_value_base`, `dcf_fair_value_bull` — this is a meaningfully better design than the original single-point plan, since it lets `feature_builder.py` (and you) see how much the "high conviction" flag depends on aggressive assumptions.

### 4.3 Database Schema

```sql
CREATE TABLE ai_valuation_scores (
    id                      BIGSERIAL PRIMARY KEY,
    ticker                  VARCHAR(10) NOT NULL,
    period_end_date         DATE NOT NULL,
    filing_date             DATE NOT NULL,
    fcf                     NUMERIC,
    total_debt              NUMERIC,
    cash_and_equiv          NUMERIC,
    shares_outstanding      NUMERIC,
    wacc                    FLOAT,
    growth_rate_low         FLOAT,
    growth_rate_high        FLOAT,
    dcf_fair_value_bear     FLOAT,
    dcf_fair_value_base     FLOAT,
    dcf_fair_value_bull     FLOAT,
    dcf_upside_pct_base     FLOAT,
    strategic_pivot         BOOLEAN,
    heavy_capex_cycle       BOOLEAN,
    buyback_paused          BOOLEAN,
    raw_llm_output          JSONB,
    model_used              VARCHAR(50),
    prompt_version          VARCHAR(20),
    dcf_model_version       VARCHAR(20),     -- version the deterministic model itself too
    UNIQUE(ticker, period_end_date)
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| SEC EDGAR XBRL API | **Low** | Free, public, explicitly designed for this |
| FRED (Treasury yields) | **Low** | Free, official Federal Reserve data, built for API access |
| Investor Relations sites | **Low-Medium** | Most IR sites intend presentations to be publicly downloaded; still, respect robots.txt and avoid aggressive polling |

This is the lowest-legal-risk document in the whole set — everything can be sourced from official, free, API-friendly government/institutional data.

---

## 6. Cost Estimate

| Item | Estimate |
|---|---|
| SEC EDGAR + FRED | Free |
| LLM (growth rate + strategic flags, ~126 tickers × 4 filings/year, ~10K tokens each) | **~$1–3/year** (trivial) |
| Compute | Negligible |
| **Total** | **Near-zero — cheapest agent in the set** |

---

## 7. Backtesting & Validation Plan

1. **Sanity-check the DCF math independently first:** Before any backtest, unit-test `DCFModeler` against 3–5 well-known companies' publicly available analyst DCF estimates (e.g., compare your output to a published sell-side DCF for the same period) to confirm the math isn't systematically biased.
2. **Historical backfill:** XBRL data goes back years and is straightforward to backfill; growth-rate extraction needs the historical filing text too (also available via EDGAR).
3. **Upside-vs-forward-return backtest:** Bucket by `dcf_upside_pct_base` quintile, measure forward 6/12-month returns — DCF-based value signals typically play out over longer horizons than the news/sentiment features, so don't judge this on 30-day returns.
4. **Bear/base/bull spread as a confidence measure:** Test whether a *narrow* bear-bull spread (i.e., growth estimate is well-constrained) predicts a more reliable signal than a wide spread — this is a natural way to use the three-scenario design from §4.2 rather than just picking the base case blindly.
5. **Strategic flags validation:** Backtest `strategic_pivot`/`heavy_capex_cycle` flags separately — these are more experimental and need their own evidence before being trusted as conviction boosters.

---

## 8. Failure Modes & Edge Cases

- **Growth rate extraction sensitivity (the big one):** an LLM misreading "we expect growth to moderate" as a hard number is the single largest source of error in this whole feature. Mitigations: (a) always extract a range, never force a point estimate, (b) cap the extracted growth rate at a sane ceiling (e.g., no company sustains >30% FCF growth for 5 years — reject/flag outputs beyond a hard-coded sanity bound), (c) periodically spot-check extracted rates against consensus analyst estimates if available.
- **XBRL tag inconsistency:** different companies/years tag the same concept differently — build the fallback tag-mapping mentioned in §4.2, and explicitly flag/exclude tickers where core inputs can't be reliably extracted rather than silently computing a DCF on wrong numbers.
- **Negative FCF companies:** DCF breaks down or becomes meaningless for companies with structurally negative FCF (early-stage growth names) — decide explicitly how to handle this (e.g., skip DCF scoring entirely for names with negative trailing FCF, flag as `dcf_not_applicable`).
- **Terminal value dominance:** a large share of DCF output is typically the terminal value, which is highly sensitive to the terminal growth/exit multiple assumption — document this assumption clearly and consider stress-testing it as a 4th "conservative terminal value" scenario if this feature gets heavy weight in the model.
- **WACC/beta source instability:** if beta is pulled from a data vendor rather than calculated in-house, changes in the vendor's beta calculation methodology can cause discontinuous jumps in fair value quarter to quarter — pick one approach and be consistent.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — DCFModeler standalone build + unit tests** | Pure Python, tested against 3–5 known real-world DCF comparisons, no LLM/pipeline yet | 3–5 days |
| **Phase 1 — XBRL fetcher** | Structured data extraction with tag-mapping fallbacks | 3–4 days |
| **Phase 2 — Growth rate + strategic flag extraction** | LLM extraction with range output, sanity bounds | 2–3 days |
| **Phase 3 — Integration** | Wire fetcher → DCFModeler → DB, share filing-trigger logic with doc `01` if feasible | 2 days |
| **Phase 4 — Validation** | DCF math sanity checks + upside-vs-return backtest (§7) | 4–5 days |
| **Phase 5 — Production integration** | `feature_builder.py` integration | 1–2 days |

---

## 10. Integration Contract with `feature_builder.py`

```python
SELECT ticker, dcf_upside_pct_base,
       dcf_fair_value_bear, dcf_fair_value_base, dcf_fair_value_bull,
       (dcf_fair_value_bull - dcf_fair_value_bear) / NULLIF(dcf_fair_value_base, 0) AS dcf_uncertainty_spread,
       strategic_pivot, heavy_capex_cycle, buyback_paused
FROM ai_valuation_scores
WHERE ticker = %(ticker)s AND filing_date <= %(as_of_date)s
ORDER BY filing_date DESC
LIMIT 1;
```
`dcf_uncertainty_spread` is a derived confidence feature worth exposing separately to the model, not just the base-case upside.

---

## 11. Success Metrics

- `DCFModeler` output matches published third-party DCF estimates within a reasonable tolerance band (e.g., ±15%) on the validation sample — confirms the math engine itself is sound before trusting the pipeline.
- Quintile spread on `dcf_upside_pct_base` shows meaningful 6–12 month forward return separation.
- `dcf_uncertainty_spread` is inversely related to the reliability of the signal (narrower spread ⇒ more reliable), confirmed empirically not just assumed.
- Coverage: DCF is computable (not `dcf_not_applicable`) for the large majority of the universe — flag and report the exceptions.

---

## Open Questions

- Beta source: calculate in-house from price history, or pull from a data vendor? (Affects WACC stability.)
- Terminal value method: Gordon Growth or exit multiple — and what's the documented, defensible assumption?
- How should `strategic_pivot`/`heavy_capex_cycle` actually be *used* downstream — as standalone features, or as multipliers/filters on the DCF conviction signal?
