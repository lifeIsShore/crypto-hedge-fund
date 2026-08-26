# NEW — Briefing Tab: LLM-Generated Specific Trade Levels (buy limit / sell / stop-loss)

**Status:** BRAINSTORM ONLY — not scoped, not speced. Captures a chat
brainstorm session. Next step: turn into a proper spec doc under
`before-go-live/` once open questions below are answered, per project
convention (audit-first / spec-before-implementation).
**Created:** 2026-08-26 (Claude, via Filesystem MCP, brainstorm session with Ahmet)
**Related:** builds on `todos/NEW-briefing-tab-TODO.md` §4 (decision-support
report) and §6 (on-prem LLM integration) — this file is a deep-dive on one
specific sub-feature of that page: turning picks into *specific actionable
price levels*, not just conviction scores.

---

## 1. The core idea

Right now the decision-support half of the Briefing tab (per the other TODO)
surfaces *which* tickers look interesting (must-check, risk/reward tier,
gamble tier). This extends that: feed the LLM a curated bundle of data per
ticker — some pulled live from Yahoo Finance, some derived from our own
model/DB — and have it output **specific, structured trade levels**, e.g.:

- Buy limit price (i.e. "place a buy limit order at X")
- Take-profit / sell target price
- Stop-loss price *and* stop-loss expressed as a max EUR loss amount
- Position sizing hint (ties into existing `kelly_half` if available)

This is explicitly a decision-support / research-copilot workflow, not an
auto-trading workflow: the human reads the structured output, does their own
independent verification (web search, chart check, news check — a manual
"RAG" step where the LLM's output is the seed/hypothesis, not the final
word), and manually places the order themselves.

## 2. Data feeding the LLM (two sources)

1. **Yahoo Finance (live/external)** — price, volume, recent range,
   volatility, maybe options chain / implied vol if available, earnings
   date proximity, analyst targets if exposed via the API.
2. **Our own model (internal)** — whatever's already in `price_targets` /
   `signals` / `model_outputs` (risk_reward_ratio, up_proba, kelly_half,
   vol_ann), regime_history, override_log hit-rate — i.e. reuse of the same
   tables the other Briefing TODO already maps out in §4, rather than
   inventing a new data pipeline.

Both sources should be exposed to the LLM through **APIs or an MCP server**
(the user's phrasing) rather than dumped as raw DB rows into the prompt —
this keeps the prompt-construction layer swappable and testable
independently of the LLM step itself, and matches the on-prem LLM
architecture question already open in the other TODO (§6, open question 4).

## 3. Prompting requirements — this is the part that needs real care

The user was explicit that this needs unusually careful prompt engineering,
for two reasons:

- **Consistency of structure.** Every ticker's output should land in the
  *same* field layout every time (same labels, same order, same units) so
  that scanning the Briefing tab daily becomes pattern-recognition, not
  re-reading prose. A fixed schema (e.g. JSON with defined keys, rendered
  into a fixed-layout card) is likely the right approach, not free-text
  narrative for this section specifically — contrast with the operational
  digest narrative panel in the other TODO, which *is* meant to be prose.
- **Mandatory, structurally-enforced disclaimer.** Every single one of these
  cards must visibly carry a "this is not investment advice" notice — not
  as something the LLM might remember to say, but as something the render
  layer always appends regardless of what the model outputs, plus a
  reinforcing instruction in the prompt itself as a second layer of
  defense.

Suggested draft schema (to refine later, not final):

```
ticker, as_of_timestamp
  current_price
  buy_limit_price        (+ rationale, 1 short line)
  sell_target_price       (+ rationale, 1 short line)
  stop_loss_price
  stop_loss_amount_eur    (derived from position size input, if known)
  confidence / conviction (reuse existing up_proba / kelly_half framing)
  key_risk_flag           (earnings proximity, high vol, low liquidity, etc.)
  disclaimer              (fixed, always rendered, not model-generated)
```

## 4. Brainstorm: ways to enhance the underlying model (not just the prompt)

Captured as raw ideas, unfiltered, for later triage:

- Feed the LLM the model's own **historical hit-rate** for similar setups
  (from `override_log.outcome_correct` / `alpha_ic_results.csv`) so its
  narrative can be calibrated by *this specific model's* track record, not
  generic reasoning — e.g. "past similar risk/reward-tier picks hit target
  in N% of cases."
- Regime-aware level-setting: same ticker/signal should produce different
  stop-loss tightness depending on `regime_history` (trending vs choppy vs
  high-vol regime) rather than a flat ATR multiple.
- Earnings-proximity gating: auto-flag or auto-widen stops when
  `earnings_calendar` shows a print inside the likely holding window.
- Cross-check layer: before finalizing a level, have the LLM (or a rule)
  sanity-check the buy-limit price against recent realized volatility so it
  can't propose a limit price that's statistically unlikely to fill.
- Idea worth testing later: two-pass generation — first pass produces raw
  candidate levels, second pass is a "red team" prompt that argues against
  the first pass's numbers, and only the surviving/reconciled version is
  shown. Costs more inference but could catch overconfident outputs.
- Portfolio-context awareness: don't generate a fresh buy-limit level in
  isolation — cross-reference `positions_history` so the tab doesn't
  recommend piling into a name/sector that's already overweight.
- Feedback loop: log every LLM-generated level next to what actually
  happened (did price touch the buy limit? did the stop get hit first or
  the target?) so hit-rate on *this specific sub-feature* becomes its own
  tracked metric over time, separate from the underlying alpha model's
  hit-rate.

## 4b. Brainstorm round 2: order mechanics, guardrails, evaluation

More raw ideas, second pass:

**Order mechanics** — the schema in §3 is too thin; a single price per
level may not be enough:
- Specify *order type* per level, not just a price — buy limit vs. buy
  stop-limit vs. limit-on-open behave very differently, especially around
  gaps.
- Support trailing stops, not just a fixed stop-loss — e.g. "fixed stop
  until +X%, then trail by Y%."
- Support partial profit-taking — `sell_target_1` (e.g. sell 50%) and
  `sell_target_2` (let the rest ride), rather than one single sell price.
  Often more realistic than an all-or-nothing target.

**Guardrail layer (post-generation, rule-based, not LLM-trusted)** —
catches hallucination-class failures cheaply, before a bad number ever
reaches the tab:
- Reject/flag any `buy_limit_price` that's more than X% from current price
  (catches stray decimals, stale prices, unit errors).
- Reject/flag any stop-loss implying a loss bigger than the user's
  configured max-risk-per-trade.
- FX sanity note: EUR account + USD-denominated ticker means the EUR
  stop-loss amount carries FX risk too — flag rather than treat as 1:1.

**Scenario framing instead of false precision**
- Consider a base-case / bull-case / bear-case triplet for the sell target
  rather than a single number — communicates uncertainty honestly.
- Explicit plain-language "invalidation condition" (e.g. "thesis breaks if
  price closes below the 50-day MA") alongside the numeric stop — often
  more useful for manual verification than the price alone.

**Event-awareness beyond earnings**
- Extend the earnings-proximity gating idea (§4) to the macro calendar
  (FOMC, CPI, jobs reports) — a stop that's fine on a normal day may be too
  tight the day before a major macro print.
- Recent-news gate: if there's been a sudden headline in the last ~24h,
  either down-weight confidence or explicitly flag "recent news — verify
  before acting" instead of generating a clean number as if nothing
  happened.

**Evaluation / trust-building infrastructure**
- Version every prompt; log which prompt version produced each card, so
  prompt tweaks can be compared by hit-rate instead of one blurred
  aggregate metric over time.
- Lightweight thumbs up/down per card, logged next to eventual outcome —
  cheap signal that compounds.

**UX nuance**
- Staleness indicator on each card — "generated at 08:15, price has moved
  +2.3% since" — so a pre-market-generated buy-limit price isn't acted on
  as if it's still fresh mid-day.

## 4c. Brainstorm round 3: plain-language event advisory (earnings and beyond)

User framing: this should work for someone who trades but isn't technical —
not just "earnings in 2 days" as a data point, but a reasoned sentence like
"don't do X before earnings, or do Y instead, not advised to do Z, because
...". The translation from raw event data into plain-language consequence +
recommendation *is* the feature here, not the event flag itself.

**Scenario types to template (not freeform per-card reasoning):**
- Already holding a position + earnings approaching → hold-through vs.
  trim-before, with the volatility-crush / gap-risk tradeoff spelled out in
  plain language.
- Considering a new buy + earnings approaching → wait-until-after vs.
  size-down-if-buying-now, with the reason stated.
- Stop-loss placed + earnings approaching → explicit warning that an
  earnings gap can jump straight past a stop price without filling there —
  arguably the single most important thing a non-technical trader needs to
  understand, since a stop-loss order is not a guaranteed exit price.

**Why templated over freeform:** "explain why" is exactly where an LLM is
most likely to sound confident while being subtly wrong about mechanics
(options behavior, margin rules, order-type guarantees) it was never given
correct structured data for. Constrain the reasoning to fill-in-the-blank
around known, verified mechanisms rather than letting the model free-write
the explanation from scratch each time.

**Generalizes beyond earnings** — same event → plain-language-consequence →
recommended-action-and-reason pattern applies to: dividend ex-date, major
macro print (FOMC/CPI/jobs — ties into §4b's macro-event gating), and
unusually high short interest heading into a squeeze-prone period. Earnings
is just the first instance to build; the pattern itself is the reusable
part.

## 4d. Brainstorm round 4: performance / inference-cost considerations

User flagged this explicitly: with several new prompt types (level-setting,
event-advisory, plus the existing operational-digest and decision-support
prompts from the other TODO) potentially running per-ticker across full
coverage (126+ tickers), naive implementation could be very inference-heavy
on an on-prem model. Ideas to keep this sustainable:

- **Gate the expensive path behind the shortlist, not full coverage.** Only
  run levels/event-advisory generation for tickers that already clear the
  must-check / risk-reward-tier bar in the existing decision-support
  section — raw data table can still show everything, narrative layer only
  runs for the tickers that earned attention. Turns O(all tickers) into
  O(shortlist), likely 5-15 names on a normal day instead of 126+.
- **Cache keyed on input-bundle hash, not wall-clock schedule.** Hash the
  data bundle feeding each ticker's prompt (price, vol, signals, earnings
  date, etc.); if unchanged since last generation, serve the cached card
  instead of re-inferring. Most of a ticker's inputs don't move meaningfully
  intraday. Bonus: this hash/cache-age also gives the staleness indicator
  from §4b for free.
- **Split templated logic from real LLM reasoning.** The event-advisory
  piece (§4c) is mostly a small decision table (earnings-in-N-days +
  holding-or-not → which canned scenario) — can likely be pure rule-based
  templating with zero LLM call, reserving inference for parts that need
  actual judgment (level-setting rationale, scenario framing). Also
  reinforces §4c's guardrail point: templated mechanics text is easier to
  manually-verify once than to trust an LLM to regenerate correctly per
  card.
- **Batch multiple tickers per call where the schema allows it**, rather
  than one call per ticker — amortizes model load/warm-up overhead, often
  the dominant on-prem cost, not raw token count. Requires a strict
  JSON-array-of-cards output schema (ties into §6 open question 1/7).
- **Route by task weight, not one model for everything.** Smaller/faster
  local model for templated/low-judgment output; reserve the larger model
  for level-setting rationale or a future red-team pass (§4).
- **Respect resource contention with the rest of the pipeline.** This runs
  on the same machine as backtests/training presumably — should sit behind
  the same "tied to pipeline run completion, not per-page-load" pattern
  already decided in the other Briefing TODO (§6), and likely needs its own
  queue/priority so it doesn't compete with a backtest for GPU/CPU at a bad
  moment.
- **Log cost, not just output quality.** Track latency + token count per
  prompt type (operational digest / decision-support / levels /
  event-advisory) so budget-cutting decisions are based on where cost
  actually concentrates, not a guess.
- **Surface LLM KPIs and cost in the Pipeline Health tab.** Don't just log the metrics silently — display a dedicated section in the existing `/health` dashboard showing daily/weekly token usage, average latency per card, and estimated cost. This keeps operational dev/ops metrics (cost, latency) out of the trader's Briefing tab while building transparency into how much the "copilot" is actually costing the system.

## 4e. Brainstorm round 5: the filter/surfacing stage itself

Clarified by user: the LLM is never run per-raw-stock. It's already fed a
curated bundle of core statistical/ML results, and only for a filtered
subset that surfaces to the top — not full coverage. This confirms the
shortlist-gating idea in §4d as existing practice, not a new proposal; what
needs thought now is the filter/surfacing step itself, since it's the real
gatekeeper for cost, quality, and trust in everything downstream.

- **Fixed-N vs. threshold-based surfacing behave very differently.**
  Fixed-N ("always the top 10") gives a predictable LLM budget but force-
  feeds mediocre picks on a quiet day and can silently drop a genuinely
  strong pick beyond the cutoff on a noisy day. Threshold-based (e.g.
  `risk_reward_ratio > X` and `up_proba > Y`) scales with how much is
  actually happening but makes inference cost unpredictable day to day.
  Likely right answer: threshold-based with a hard ceiling as a cost safety
  valve (everything clearing the bar, capped at N, sorted by score if it
  overflows).
- **De-duplication / correlation check before the LLM sees anything.** If
  several filtered tickers are the same sector/factor bet (e.g. five
  correlated semiconductor names), the LLM burns budget writing five cards
  that all say the same thing. Same problem as the combo-trade correlation
  check already flagged in the other Briefing TODO (§4) — just needs to
  happen one step earlier, at the filter stage, not just at combo-trade
  construction.
- **Anti-flicker / hysteresis on the cutoff.** A ticker whose score sits
  right at the threshold will bounce in and out of the shortlist as it
  crosses the line repeatedly, triggering repeated LLM calls for something
  that hasn't meaningfully changed. Use a wider exit threshold than entry
  threshold (enter at score 8, only drop below score 6) so borderline names
  don't churn.
- **Carry forward *why* a ticker surfaced, as structured data.** E.g.
  "surfaced because risk_reward_ratio=3.2 and up_proba=0.71" — not just for
  the LLM prompt, but so the filter itself can be evaluated later,
  separately from the LLM's card quality. Two different failure modes:
  filter surfaces bad candidates, or filter surfaces good candidates but
  the LLM writes a bad card about them — need to be able to tell which is
  happening.
- **Filter needs its own feedback loop, distinct from card feedback.** If
  thumbs-downs cluster on tickers that technically passed the filter,
  that's a filter-tuning signal, not a prompt-tuning signal. Keep the two
  feedback streams separate so tuning effort goes to the right layer.

## 5. Workflow this is meant to support

Not "trust and click." The intended loop is:
1. Briefing tab shows the structured card per ticker (fixed fields, always
   labeled "not investment advice").
2. User treats the card as a **hypothesis/starting point** — a seed for
   their own manual research (news search, chart check, sanity read).
3. User manually decides and manually places the order (Trade Republic or
   wherever) — no auto-execution implied by this feature.

This keeps it consistent with the existing project principle already
recorded in the other Briefing TODO (§5): advisory-only until/unless real
execution capability is deliberately built and confirmed.

## 6. Open questions to resolve before writing a full spec

1. Fixed JSON schema per ticker vs. semi-structured — how rigid should the
   render layer enforce this vs. trusting the prompt alone?
2. Should stop-loss-in-EUR require a per-user position-size input, or can
   it be estimated from a configurable default account risk-per-trade %?
3. Yahoo Finance access — direct API call from the backend, or via an MCP
   server so the LLM can pull data on demand rather than everything being
   pre-fetched into the prompt?
4. Where does this live relative to the rest of the decision-support
   section in the other Briefing TODO — same LLM call/prompt, or a
   dedicated third prompt (operational digest / decision-support picks /
   this level-setting sub-feature = three prompts, not two)?
5. How is "not investment advice" enforced — UI-only (always rendered
   regardless of model output), prompt-only, or both (recommended)?
6. Two-pass "red team" generation (§4) — worth the extra inference cost, or
   v1 should ship single-pass and revisit later based on observed error
   rate?
7. Single sell target vs. partial-profit two-target structure (§4b) — how
   much schema complexity is worth it for v1?
8. Where does the rule-based guardrail layer (§4b) live — same service as
   the prompt-construction layer, or a separate validation step the app
   always runs regardless of which LLM/prompt produced the card?
9. Single point estimate vs. bull/base/bear scenario triplet (§4b) for
   sell targets — more honest about uncertainty, but is it more useful or
   just more to read at a glance?
10. Event-advisory templates (§4c) — how many scenario templates for v1
    (earnings-only, or earnings + macro + dividend from day one)? And who
    verifies the underlying mechanics text (e.g. "stops don't guarantee
    fill price on a gap") is accurate before it ships as a template the
    LLM fills in — this is the one piece where a wrong explanation could
    actively mislead a non-technical user, so it probably deserves a
    manual review pass rather than trusting the LLM to get the mechanics
    right unsupervised.
11. Shortlist-gating threshold (§4d) — reuse the existing must-check /
    risk-reward-tier cutoff as-is, or does this feature need its own
    (possibly tighter) cutoff given the extra inference cost per card?
12. Batching feasibility (§4d) — does the chosen local model/runtime
    actually support reliable structured batch output (array-of-JSON) at
    the context lengths this needs, or does hardware/runtime reality force
    one-call-per-ticker regardless of the cost argument for batching?
13. Filter mechanics (§4e) — what does the existing filter/surfacing logic
    actually look like today (which fields, what thresholds)? This file
    speculates; needs to be checked against whatever's already implemented
    before assuming a fixed-N vs. threshold-based redesign is even needed.
14. Filter evaluation (§4e) — worth a formal precision/recall-style metric
    on the filter itself (does it consistently surface tickers that later
    perform well), separate from the LLM card-quality metric, or is that
    over-engineering for v1?

---
*This file documents a brainstorm session only. No code, schema, or prompt
implementation has been done. Next step: fold into a full spec once §6's
open questions are answered.*
