# J6 — Fundamental Data Source Decision
# Decision memo, not code — read and pick one before building
# `NEW-alpha-earnings-revision.md` / `NEW-alpha-quality-factor.md` / `J4-earnings-calendar.md`

---

## Why this blocks other work

Both un-archived alpha docs (`NEW-alpha-earnings-revision.md`,
`NEW-alpha-quality-factor.md`) depend on a `fundamental_data` table that
doesn't exist yet, populated by a `fundamental_ingestion.py` that also
doesn't exist yet. Both docs already picked **yfinance `.info`** as the
source in their code. This memo exists because that choice has a real
consequence you should make consciously rather than by default: the same
`yfinance` ToS issue flagged in `how-to-make-money.md` and carried forward
into PROJECT-STATE.md §7a applies here too, even for personal use, and
matters more if the SaaS pivot ever actually ships.

---

## The three real options

### Option A — yfinance `.info` (what both alpha docs already assume)
- **Cost:** Free
- **Coverage:** Good for US large-caps. Weak/inconsistent for `.DE`/`.PA`
  tickers — expect `roe`, `debt_to_equity` etc. to be `NaN` for a meaningful
  chunk of your European names (same caveat your own docs already note for
  options data on `.DE` tickers).
- **Reliability:** Undocumented, unofficial API surface — yfinance scrapes
  Yahoo's internal endpoints. Fields get renamed or dropped without notice;
  this has happened before and will happen again.
- **ToS:** Explicitly against Yahoo's terms for anything beyond personal,
  non-commercial use. For your current single-account personal setup, this
  is a real but low-consequence risk (Yahoo is very unlikely to notice or
  care about one retail account). **If the SaaS pivot in PROJECT-STATE §2
  ever actually ships, this becomes a hard blocker for every tenant
  instance simultaneously** — not a "some risk," a guaranteed ToS violation
  at commercial scale.

### Option B — Financial Modeling Prep (FMP)
- **Cost:** ~€15-20/month for a tier covering 250+ tickers with fundamentals
- **Coverage:** Includes European stocks, which yfinance handles poorly.
  Gives EPS surprise history, revenue growth, debt ratios — directly the
  fields both alpha docs need.
- **Reliability:** Documented, versioned REST API. Won't silently break.
- **ToS:** Commercial-use tier exists and is affordable at your scale —
  this is the option that survives a SaaS pivot without a re-architecture.

### Option C — Twelve Data (you already have a key)
- **Cost:** Free tier you're already using for price/FX data — check if your
  current tier includes fundamentals or requires an upgrade
- **Coverage:** Decent but thinner fundamentals coverage than FMP
  specifically
- **Reliability:** Documented API, same provider you already trust for price
  data — one less vendor relationship to manage

---

## Recommendation

**Start with Option A (yfinance) to build and validate the two alpha models
cheaply, but treat it explicitly as a placeholder, not a final decision.**
Both `NEW-alpha-*.md` docs are already written against yfinance's `.info`
dict, so this is the zero-cost path to actually see whether these two alpha
models produce a usable IC before spending money on a paid feed. If either
model's IC comes back near zero or negative after a few weeks of live
tracking, you've saved yourself a subscription on a model that wasn't going
to work anyway.

**Switch to Option B (FMP) before either of two triggers:**
1. You decide the SaaS pivot (PROJECT-STATE §2) is actually happening — at
   that point this is no longer optional, per the existing §7a note.
2. The yfinance-sourced version of either alpha model shows a real IC and
   you want to extend its European coverage (which yfinance can't give you
   reliably).

**Why not Option C as the fundamental source:** keep price/FX and
fundamentals on separate providers rather than consolidating onto Twelve
Data — if fundamentals ingestion breaks, you don't want it taking down price
ingestion too (this mirrors your existing multi-source FX fallback design
philosophy already praised in `00-PRODUCTION-READINESS-VERDICT.md`: don't
let one provider be a single point of failure for two different data types).

---

## What to actually change in the two alpha docs if you go this route

Nothing yet. Both `NEW-alpha-earnings-revision.md` and
`NEW-alpha-quality-factor.md` are already written against yfinance `.info` —
build them as-is first. If/when you later migrate to FMP, the only file that
needs to change is `fundamental_ingestion.py`'s fetch function — the
`fundamental_data` table schema and both alpha models' `generate_signals()`
read from the DB, not from the provider directly, so the migration is
contained to one file. This is the same "swap the source, keep the
interface" pattern your `ingestion.py` already uses for price data
(`primary provider + fallback provider`, per `improvements.md` Phase 3
item 4) — worth deliberately building `fundamental_ingestion.py` with the
same swappable-provider shape from day one so this migration is cheap later
even if you start with yfinance now.
