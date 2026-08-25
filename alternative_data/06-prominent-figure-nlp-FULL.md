# 06 — Prominent Figure Macro NLP

**Status:** Planning
**Owner:** —
**Priority:** —
**Depends on:** `shared/state/macro_regime.json`, `feature_builder.py` (as a global/cross-ticker feature, not per-ticker)

---

## 1. Concept & Hypothesis

This is structurally different from the other agents: it produces **global macro-regime flags**, not ticker-specific features. The bet is that real-time transcription and classification of central banker/politician/prominent-investor rhetoric can shift the model's sector/factor tilt (e.g., growth vs. value) ahead of the market fully digesting a policy signal.

**Hypothesis:** There's a real (if short) window between when a Fed chair says something in a live press conference and when the market has fully repriced around it — real-time transcription + classification can capture part of that window faster than reading a next-day summary article.

**Why this edge is genuinely hard to capture:** FOMC press conferences move markets **during the conference itself** — professional traders are already watching live and reacting in seconds to minutes, often faster than a transcription + LLM classification pipeline can run end-to-end. Be realistic about the actual latency this system can achieve (see §6) versus the speed of the market participants you're competing with in this specific niche.

**Where the edge is more plausible:** Less-followed events — regional Fed president speeches, congressional testimony, second-tier officials, and non-scheduled remarks (interviews, podcasts) — are less universally monitored in real time than the marquee FOMC presser, and are a more realistic target for a smaller system to have a genuine speed/coverage edge.

---

## 2. Target Figures — Notes on Scope

- **Central bankers:** Fed Chair, regional Fed presidents, ECB President — high value, high competition (FOMC especially).
- **Politicians:** Scope should probably be need-based — track officials whose statements plausibly move your specific 126-ticker universe (e.g., relevant committee chairs, Treasury/Commerce officials for trade-exposed names) rather than tracking every political figure broadly, which adds noise and processing cost without clear signal value. Real-time political figures change with administrations — this list needs periodic review, not a hardcoded set of specific named individuals that may be out of office by the time this is built.
- **Macro economists/investors:** Lower urgency (their commentary is typically less market-moving in real time than official policymakers) — could reasonably be Phase 2/lower priority, sourced from podcast/interview transcripts rather than requiring live transcription infrastructure.

---

## 3. Core Features

### 3.1 Real-Time Speech-to-Text Narrative Extraction
- **Mechanism:** Live audio/video monitoring → low-latency transcription (Whisper/faster-whisper) → chunked LLM classification.
- **Output:** `dovish_fed_rhetoric` (bool), `hawkish_fed_rhetoric` (bool)
- **Better design than a single boolean pair:** consider a continuous `fed_hawkishness_score` (-1 to 1) rather than two competing booleans — avoids the ambiguous case where a speech is genuinely mixed/neutral and forces an artificial binary choice.

### 3.2 Social Media & Micro-Blogging Parsing
- **Mechanism:** Monitor official accounts of tracked figures.
- **Output:** `protectionist_policy_risk` (bool), `fiscal_stimulus_expected` (bool)

---

## 4. Architecture

### 4.1 Pipeline

```
┌───────────────┐   ┌────────────────┐   ┌─────────────────┐   ┌────────────────┐   ┌──────────────────────┐
│ Audio ingestion│──▶│ faster-whisper │──▶│ Chunked LLM     │──▶│ Regime state    │──▶│ macro_regime.json     │
│ (yt-dlp live)  │   │ (local, low    │   │ classification  │   │ aggregation     │   │ + macro_regime_events  │
│ + social poll  │   │ latency)       │   │ (streaming)     │   │ (with decay)    │   │ table (audit trail)   │
└───────────────┘   └────────────────┘   └─────────────────┘   └────────────────┘   └──────────────────────┘
```

### 4.2 Components

1. **Event scheduler (`fomc_calendar.py`):** Maintain a calendar of known scheduled events (FOMC dates are published well in advance) to pre-warm the audio-ingestion pipeline rather than relying on ad hoc detection of "is there a live stream right now."
2. **Audio ingester (`audio_ingester.py`):** `yt-dlp` for live YouTube streams of press conferences; for audio-only sources (podcasts), simpler RSS-based download.
3. **Transcription service (`transcriber.py`):** `faster-whisper` running locally (GPU strongly recommended for real-time performance — CPU-only transcription will likely not keep pace with a live stream, undermining the entire latency premise of this agent; budget for GPU infra explicitly, see §6).
4. **Streaming LLM classifier (`macro_classifier.py`):** Classifies rolling transcript chunks (e.g., 30-second windows with some overlap for context continuity), `temperature=0`, JSON schema output.
5. **Regime state manager (`regime_state.py`):** Aggregates chunk-level classifications into a session-level and then a rolling regime state, written to `shared/state/macro_regime.json` **and** persisted to a database table (the original plan's JSON-file-only approach loses history — add a DB audit trail alongside the JSON for backtesting and debugging).
6. **Social poller (`social_figure_tracker.py`):** Separate, lower-latency-requirement cadence (every few minutes is fine) for official account monitoring.

### 4.3 Database Schema

```sql
CREATE TABLE macro_regime_events (
    id                     BIGSERIAL PRIMARY KEY,
    figure_name            VARCHAR(100) NOT NULL,
    figure_role            VARCHAR(100),         -- 'Fed Chair', 'Regional Fed President', etc.
    event_type             VARCHAR(30),           -- 'live_speech', 'social_post', 'testimony'
    event_timestamp        TIMESTAMPTZ NOT NULL,
    transcript_chunk        TEXT,
    fed_hawkishness_score  FLOAT,                 -- -1 (dovish) to 1 (hawkish), null if not applicable
    protectionist_policy_risk BOOLEAN,
    fiscal_stimulus_expected  BOOLEAN,
    model_used             VARCHAR(50),
    prompt_version         VARCHAR(20)
);
CREATE INDEX idx_mre_figure_time ON macro_regime_events(figure_name, event_timestamp);

-- Current aggregated state, mirrors the JSON file
CREATE TABLE macro_regime_state (
    as_of_timestamp         TIMESTAMPTZ PRIMARY KEY,
    fed_hawkishness_score   FLOAT,
    protectionist_policy_risk BOOLEAN,
    fiscal_stimulus_expected  BOOLEAN,
    contributing_events_count INT
);
```

---

## 5. Legal & Compliance Risk

| Source | Risk Level | Notes |
|---|---|---|
| YouTube live streams (FOMC pressers, public hearings) | **Low-Medium** | `yt-dlp` downloading public livestreams for internal analytical use is common practice, but YouTube's ToS technically restricts downloading; this is a widely tolerated gray area rather than a clean "low risk" — acceptable for internal research use, but worth being aware it's not risk-free if ever scaled or made external-facing |
| Official government livestreams (Fed, congressional hearings) | **Low** | Government proceedings are generally public domain / intended for public dissemination |
| X/Twitter/Truth Social monitoring of public figures | **Low-Medium** | Public posts, but platform ToS on automated collection varies — official API access (where available, e.g., X API) is safer than scraping |
| Podcast RSS | **Low** | RSS feeds are intended for syndication/consumption |

**Action item:** Confirm current `yt-dlp`-against-YouTube practical/legal posture before building — this is the shakiest ground in the document, even though it's common practice for internal research tooling.

---

## 6. Cost Estimate — and a Reality Check on Latency

| Item | Estimate |
|---|---|
| GPU infra for real-time `faster-whisper` (if not already available) | Cloud GPU instance (e.g., a T4/A10-class instance run only during scheduled events) ≈ **$50–300/month** depending on usage pattern, or a one-time local GPU cost if self-hosting |
| LLM classification (streaming chunks, cheap/fast model) | Low volume, event-driven — **~$5–20/month** |
| Social API access | Free–$100/month depending on which platforms/tiers |
| **Total** | **~$100–400/month**, dominated by GPU infra if run cloud-based |

**Reality check:** Even with a well-optimized pipeline (local GPU Whisper + fast LLM), end-to-end latency from "words spoken" to "classified regime flag written" is realistically several seconds to low tens of seconds per chunk. For the marquee FOMC presser specifically, this will very likely still be slower than professional trading desks already reacting live. Treat FOMC real-time capture as valuable for **your own record-keeping and slower systematic reaction** (e.g., informing the next day's positioning) rather than as a genuine "beat the market in real time" edge — and put more relative weight/priority on the less-crowded targets (regional Fed presidents, podcasts, second-tier testimony) where the speed competition is much less brutal.

---

## 7. Backtesting & Validation Plan

1. **Historical calibration set:** Manually label a set of historical Fed speeches/statements (dovish/hawkish/neutral, using known market reactions as ground truth) and validate the classifier's `fed_hawkishness_score` against human/market-confirmed labels before trusting live output.
2. **Regime-shift backtest:** Test whether flipping `dovish_fed_rhetoric`/`hawkish_fed_rhetoric` (or crossing a threshold on the continuous score) historically preceded the kind of sector rotation the hypothesis assumes (growth outperforming value in dovish regimes, etc.) — this is testable using historical FOMC statement text + realized sector returns, independent of the live-transcription infrastructure.
3. **Latency-adjusted backtest:** Critically, backtest using the timestamp your pipeline would **actually have produced the flag**, not the moment the words were spoken — build in a realistic latency assumption (see §6) rather than assuming instant classification, or the backtest will overstate the edge.
4. **Second-tier figures validation:** Separately test whether regional Fed president / less-followed-figure signals show a return edge — this is the more novel, less-crowded claim in the document and deserves its own validation rather than riding on the (much more competitive) FOMC thesis.

---

## 8. Failure Modes & Edge Cases

- **Transcription errors on financial jargon:** Whisper can mis-transcribe specific terms (ticker names, obscure economic terms) — consider a custom vocabulary/prompt-biasing pass for known financial/Fed terminology if `faster-whisper` supports it, or at least monitor transcription quality on a sample.
- **Chunking context loss:** classifying 30-second windows independently can lose sentence-level context split across chunk boundaries — use overlapping windows and/or maintain a running context summary passed to each classification call.
- **False regime flips from Q&A hedging:** Fed chairs often give deliberately hedged, two-sided answers in Q&A — a naive classifier may flip-flop the regime flag chunk-to-chunk; the regime state manager should smooth/require sustained signal (e.g., a rolling majority over the last N chunks) before flipping the persisted state, not react to every single chunk.
- **Named-figure list staleness:** administrations, Fed leadership, and committee memberships change — this target list needs an explicit owner and periodic review, not a "set once" hardcoded list (this is a recurring theme across this whole document set and applies especially strongly here).
- **Livestream detection failures:** if `yt-dlp` fails to find/access a stream (platform changes, stream moved), the system should alert immediately given the time-sensitivity — a silent failure during an FOMC presser defeats the entire purpose of this agent.

---

## 9. Build Timeline

| Phase | Scope | Est. effort |
|---|---|---|
| **Phase 0 — Offline validation** | Build the classifier and validate against historical labeled Fed statements (§7.1) — no live infra yet | 3–4 days |
| **Phase 1 — Social/podcast MVP** | Lower-latency-requirement social + podcast monitoring (skip live audio initially) | 3–4 days |
| **Phase 2 — Live audio pipeline** | GPU-backed live transcription for scheduled events (FOMC calendar-driven) | 5–7 days |
| **Phase 3 — Regime smoothing logic** | Rolling-majority state management to avoid flip-flopping (§8) | 2 days |
| **Phase 4 — Validation** | Regime-shift backtest + latency-adjusted backtest (§7) | 4–5 days |
| **Phase 5 — Integration** | Wire `macro_regime.json`/table into `feature_builder.py` as a global feature | 1–2 days |

---

## 10. Integration Contract with `feature_builder.py`

Since this is a **global** feature (same value applied across all tickers, not ticker-specific), it should be joined differently from the other agents:

```python
SELECT fed_hawkishness_score, protectionist_policy_risk, fiscal_stimulus_expected
FROM macro_regime_state
WHERE as_of_timestamp <= %(as_of_date)s
ORDER BY as_of_timestamp DESC
LIMIT 1;
```
No `ticker` filter — this row gets broadcast to every ticker's feature vector for the given `as_of_date`, same as the original plan's intent, just now backed by both the JSON state file and a queryable/auditable DB table.

---

## 11. Success Metrics

- Classifier agreement with human-labeled historical calibration set (§7.1) exceeds a defined bar (e.g., >80% directional agreement) before going live.
- Regime-shift backtest shows the hypothesized sector-rotation effect historically, using latency-realistic timestamps.
- Live pipeline successfully captures and classifies >90% of scheduled FOMC/target events without missed/failed runs.
- Second-tier figure signal (regional Fed, etc.) shows its own measurable, non-redundant edge — not just riding on FOMC correlation.

---

## Open Questions

- Is live GPU-based real-time transcription actually worth the infra cost/complexity given the FOMC latency reality (§6), or should Phase 2 (live audio) be deprioritized in favor of doubling down on Phase 1 (social/podcast/second-tier figures)?
- Who owns and periodically refreshes the target-figure list as administrations/committees change?
- Should `fed_hawkishness_score` be continuous only, or is there still value in keeping the boolean flags for simpler downstream logic/interpretability?
