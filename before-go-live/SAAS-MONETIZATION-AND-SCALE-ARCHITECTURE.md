# SaaS Monetization & Scale Architecture
Status: DECISION MEMO — brainstorm, not yet implemented. Read, decide, then
this becomes the source-of-truth spec the way J1-J7 are for their topics.

Written in response to a specific brief: $9.99/mo flat pricing, promotional
first-month-free, a referral program, and an architecture that starts small
but doesn't need a rewrite to reach 1,000 -> 10,000 -> 100,000 users.

See also: `LEGAL-DOCS-CHECKLIST.md` (companion doc — what legal pages/policies
this pivot requires before the first non-friend paying customer).

---

## 0. The thing to resolve before any of the rest of this matters

**Regulatory exposure.** This app generates specific BUY/SELL suggestions
with position sizes, computed by an ML pipeline, for money, at consumer
scale. That is close to the legal definition of investment advice in most
jurisdictions (SEC "investment adviser" test in the US; BaFin/MiFID II
equivalent in Germany/EU). `how-to-make-money.md` already flagged the
"market as Analytics & Decision Support, never as Investment Advice"
framing — at hobby scale with a few friends using it, that's a reasonable
informal position. At $9.99/mo with strangers signing up with a credit
card, it needs to become:

- Actual Terms of Service + a disclaimer users affirmatively click through
  before they can see a single trade suggestion.
- A real conversation with a lawyer in whichever jurisdiction you
  incorporate/sell from, before the first paying non-friend customer.
- A decision on whether the product **only ever suggests trades for the
  user to manually execute** (current design — much safer, keep it this
  way) vs. anything that touches live order execution (do not do this
  without the above legal conversation happening first).

See `LEGAL-DOCS-CHECKLIST.md` for the concrete list of pages/policies this
implies. This document does not resolve the regulatory question — it just
flags it as the highest-priority open item, ahead of every pricing or infra
decision below, because it's the one category of risk that isn't fixed by
better code.

**Data provider ToS.** `J6-fundamental-data-source-decision.md` already
covers this for fundamentals; the same logic applies to price data. yfinance
is free but against Yahoo's ToS for commercial use. This stops being a
"someday" problem the moment the first non-friend, non-free customer signs
up — not at some future scale trigger. Budget for a paid provider (Polygon,
FMP, Twelve Data's paid tier) before charging anyone money for it.

---

## 1. Pricing

**$9.99/month flat. No tiers.** This is the right call for the target
market (amateur / semi-amateur investors) — a single number is easy to
understand and doesn't require the user to evaluate "which plan do I need,"
which fights the same simplicity goal driving the UI decisions elsewhere in
this repo. Resist tiering even when it's tempting later ("Pro" with more
tickers, "Plus" with more alpha models) — every tier is a decision the user
has to make, and decisions are the thing you're trying to remove for this
audience.

**Promotions, run as time-limited campaigns, not permanent price cuts:**
- First month free (standard trial, requires card on file — see §2).
- Occasional seasonal promos (e.g. "first month free" runs as a campaign,
  not baked into the default flow forever) — keeps the option to tighten it
  later without it feeling like a price increase.

---

## 2. Referral program — concrete design

| Parameter | Value | Why |
|---|---|---|
| Referrer reward | 1 free month per friend who completes their first **paid** month | Ties the reward to real revenue, not signups |
| Referred friend | Standard first-month-free (no separate reward needed) | Keeps the pitch to one sentence |
| Annual cap | 12 free months/year per referrer | Bounds worst-case cost; still lets a power referrer get a full free year |
| Credit trigger | Fires when the friend's card is successfully charged for month 2 (i.e. month 1 free + month 2 paid = referral confirmed) | Prevents farming free-trial-only signups for credit |
| Trial requires card | Yes, from day one | Without this, "first month free" + referral stacking becomes a way to run the service for $0 indefinitely on burner emails |

Keep the mechanic to one sentence in the UI: *"Refer a friend, get a free
month once they've been a subscriber for a month. Up to 12 free months a
year."* Anything more complex (tiered rewards, different reward for 5th
referral vs 1st) adds decision-complexity for the user without adding much
lift — skip it.

**Fraud/abuse notes to build in from day one, not bolt on later:**
- One referral code per account, generated from a real paid account only
  (not available during a free trial).
- Rate-limit: flag (don't auto-block) accounts with >20 successful referrals
  in a month for manual review — that volume is unusual for organic
  word-of-mouth in this niche.
- Self-referral prevention: block referral credit if the referred card's
  fingerprint (Stripe Radar / card fingerprint) matches an existing account.

---

## 3. Architecture — the core redecision

### The problem with the currently-confirmed model

`PROJECT-STATE.md` §2 confirms: "hosted, isolated, single-tenant per
customer... each subscriber gets their own container/instance... own
separate SQLite file." That's a completely reasonable decision for the
first 10-50 customers — it's simple, and privacy-via-isolation is an easy
story to tell. **It does not survive to 10,000 users economically**, for
one specific reason: this app's most expensive work — market data
ingestion, feature computation, ML training/inference, regime detection —
is currently designed to run **once per customer container**, but none of
that work is actually customer-specific. Every customer's LSTM is trying to
predict the same NVDA. Paying to compute that 10,000 times instead of once
is the single biggest inefficiency in the current design, and it's a
compute cost that scales linearly with users while your revenue also scales
linearly with users — meaning your margin never improves as you grow,
which is the opposite of how SaaS unit economics are supposed to work.

### The fix: separate the shared engine from the personal layer

Split the system into two halves that already exist conceptually in the
codebase, just not architecturally separated:

**A. Shared signal engine (runs once, for all users):**
- Market data ingestion (prices, FX, fundamentals, earnings calendar)
- Feature store computation
- Alpha model inference (momentum, mean-reversion, PEAD, ML ensemble, LSTM,
  quality factor, earnings revision, etc.)
- Regime detection
- Correlation clustering

None of this reads or writes anything user-specific. It runs once a day
(or on whatever cadence) against one shared universe of tickers, for
everyone, regardless of whether you have 10 users or 100,000.

**B. Per-tenant portfolio layer (runs per user, but is cheap):**
- Black-Litterman optimization using the shared signals + this user's own
  current holdings, risk tolerance, tax jurisdiction, position caps
- Order queue generation
- Trade ledger, override log, watchlist, signal queue — genuinely personal
  data
- Circuit breakers, tolerance bands — evaluated per user's actual positions

This layer is cheap per user (it's a constrained optimization over ~100-200
tickers, not a data pipeline) — this is the part that's allowed to scale
per-user, because it actually is per-user work, and it's computationally
light.

**Isolation without isolated infrastructure:** every tenant's row in every
personal table (trades, positions, watchlist, override_log, tax_settings)
carries a `tenant_id`. Application-level checks (and Postgres row-level
security as a second layer) ensure a query for tenant A's data can
physically never return tenant B's rows. This gives you the privacy
guarantee "confirmed architecture" was trying to buy with full container
isolation, without paying for full container isolation.

### Phased rollout — build for the end state, launch the first phase

| Phase | Scale | Infra | What changes from today |
|---|---|---|---|
| **Phase 0 (now)** | You + a handful of friends | Current setup, unchanged | Nothing — don't rearchitect for a scale you don't have yet |
| **Phase 1 (launch)** | 0-1,000 paying users | One shared Postgres (not SQLite — see note below), one background worker running the shared signal engine on a schedule, Flask app served from 1-2 small instances behind a load balancer | Migrate SQLite -> Postgres (needed for concurrent multi-tenant writes regardless of scale — SQLite's single-writer model won't hold up even at a few hundred concurrent users). Split scheduler into "shared engine" job + "per-tenant" job. |
| **Phase 2** | 1,000-10,000 | Add a job queue (e.g. Redis + a worker pool) for per-tenant portfolio construction so 10,000 users' BL optimizations run in parallel across workers instead of one process serially; read replica for the dashboard's read-heavy queries; Postgres connection pooling (pgbouncer) | No architecture change, just horizontal scaling of the same shape — add workers, add a read replica. This is the payoff of doing the Phase 1 split correctly: scaling from here is "add more of the same," not "redesign." |
| **Phase 3** | 10,000-100,000+ | Consider splitting the shared signal engine into its own service (separate deploy cadence from the per-tenant web app); CDN for static dashboard assets; evaluate whether a single Postgres instance still holds up or needs read/write splitting or partitioning by tenant_id | Only cross this bridge if/when you're actually approaching this scale — premature infrastructure at this level for a few hundred users is wasted engineering time you could spend on the product |

**Why Postgres over SQLite starting at Phase 1, specifically:** SQLite
allows one writer at a time. At even a few hundred concurrent users
hitting `/api/log_trade` or the pipeline writing feature_store rows,
write contention becomes a real, user-visible latency problem — this
isn't a "someday at 100k users" concern, it's a "the day you have 200
concurrent users" concern. This is the one piece of the Phase 1->Phase 2
jump that's worth doing early rather than deferring, because migrating a
live multi-tenant database engine later is much more disruptive than
choosing the right one at the start.

---

## 4. What this means for the codebase specifically

Concretely, this reframes several existing docs in this folder:

- **`how-desktop.md` — do not build; moved to `archive-outdated/`.** It's a
  single-user desktop packaging guide, a different distribution model
  entirely from a hosted SaaS. Kept for reference only, per
  `PROJECT-STATE.md` §7a's existing note — this document reinforces that
  call rather than reversing it.
- **`how-to-make-money.md` Path 1's "migrate to PostgreSQL, add
  multi-tenancy" recommendation is directionally correct** — this doc just
  makes the *how* concrete (shared engine + tenant_id rows, not a fully
  separate schema-per-tenant or container-per-tenant). Kept in the main
  folder — still useful context, not fully superseded.
- **J1-J7 and the alpha-model docs (NEW-alpha-*) become shared-engine
  work**, computed once for the whole platform, not per customer. This is
  good news — it means finishing those docs pays off more at scale, not
  less, since the cost of computing a correlation cluster or a quality
  factor score is now amortized across every subscriber instead of paid
  once per customer.
- **Tax-aware selling (J2)'s jurisdiction settings become genuinely
  per-tenant** — this is exactly the kind of setting that belongs in the
  cheap per-tenant layer, not the shared engine. Good fit either way this
  goes.
- **SOS-button.md's halt flag** needs to become per-tenant (a user should
  be able to halt their own pipeline output without halting everyone
  else's) rather than the current single global `system_halt` row design
  — flag this before building it.

---

## 5. Other things worth deciding now, not later

- **Support burden at $9.99/mo.** Margins are thin at this price point —
  you cannot staff 1:1 support at scale. Budget for this from day one: a
  genuinely good FAQ/docs site, an in-app "what does this mean" tooltip
  system (this pairs naturally with I2's signal-explainability work, which
  already exists to answer "why is it suggesting this"), and a support
  email with a realistic response-time expectation set up-front, not a
  live-chat promise you can't keep at scale.
- **Onboarding for amateur users.** This is a genuinely sophisticated tool
  (Black-Litterman, regime detection, PEAD) being sold to people who may
  not know what those words mean. A short onboarding flow that sets
  expectations ("this suggests trades, you decide, nothing executes
  automatically") matters as much as any pricing decision for retention — a
  confused user churns in week one regardless of how good the signals are.
- **Churn and free-trial conversion tracking** — decide up front which
  metrics actually matter (trial -> paid conversion rate, month-2
  retention, referral-driven vs. organic signups) so you're not
  retrofitting analytics after launch.
- **GDPR, if selling into the EU** (which "amateur/semi-amateur investors"
  likely includes, given the existing German tax-jurisdiction work already
  in this repo) — data export/delete rights, a real privacy policy, and
  where the database physically lives all become relevant the moment you
  have EU customers, not just German ones. See `LEGAL-DOCS-CHECKLIST.md`.
- **Payment processing** — Stripe Billing handles subscriptions, trials,
  and can model the referral credit as a coupon/balance credit mechanism; a
  failed-payment grace period (a few days, with an email before
  hard-cutting access) is standard practice and worth deciding now rather
  than mid-incident.
- **Backups/disaster recovery** for a shared multi-tenant Postgres instance
  are a much bigger deal than for a personal SQLite file — one outage now
  affects every paying customer simultaneously, not just you. Automated
  daily backups + a tested restore process should exist before the first
  non-friend customer, not after the first incident.

---

## 6. Recommended sequencing

1. Resolve §0 (regulatory posture + data provider) — blocks everything
   else. See `LEGAL-DOCS-CHECKLIST.md`.
2. Decide referral mechanics from §2 (or amend them) — cheap to decide now,
   expensive to change after users have already earned credits under
   different rules.
3. Migrate SQLite -> Postgres and split the scheduler into shared-engine
   vs. per-tenant jobs (§3, Phase 1) — this is the one piece of
   re-architecture worth doing *before* the first paying non-friend
   customer, since doing it after real user data exists is much more
   disruptive.
4. Launch Phase 1 at small scale, instrument the metrics from §5, and only
   move to Phase 2 infrastructure when the numbers say you actually need it
   — not preemptively.
