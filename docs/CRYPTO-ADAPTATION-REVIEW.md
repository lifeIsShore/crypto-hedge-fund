# Control Tower → Crypto: Architecture Review & Adaptation Plan

> **Scope:** Full-system review of Control Tower (EU-equities engine) with a concrete plan for adapting it to crypto markets, plus alt-data and ML recommendations specific to crypto.
> **Date:** 2026-08-30
> **Author:** Claude, via Filesystem MCP
> **Status:** Advisory — no code changed this session, read-only review.

---

## 0. TL;DR

You have a genuinely more sophisticated architecture than most retail quant setups — Black-Litterman with Ledoit-Wolf shrinkage, IC-gated alpha models, walk-forward backtesting with a proper run registry, regime detection, circuit breakers. That part transfers to crypto largely as-is; portfolio construction math doesn't care what the ticker is.

What does **not** transfer cleanly, and is where most of your adaptation work needs to go:
1. **The data layer** — yfinance/FRED/Finnhub assume equity market structure (single exchange, closing prices, T+2 settlement, earnings calendars). Crypto has none of that.
2. **The alpha models** — PEAD, earnings-calendar throttling, and sector-relative momentum (as currently defined) are equity-specific concepts that need either replacement or a crypto-native reinterpretation.
3. **The risk engine assumptions** — VaR/CVaR and drawdown thresholds calibrated for equity vol (15-20% annualized) will be far too loose for crypto (60-120%+ annualized is normal). Circuit breaker thresholds (-15% stock) will trigger constantly if reused unchanged.
4. **Known bugs in `engine/` (see `engine/ENGINE_REVIEW.md`)** should be fixed **before** porting, not after — several are the kind of silent-failure bug that's much easier to introduce with new terminology (crypto tickers, new tables) than to debug once mixed in.

Also — separate from crypto specifically — the ML side of this project has a real finding you should sit with: **every documented Gate 2 test on the equities side failed** (feature families and target refinement all failed the +0.003 AUC bar). That's not a failure of your process — the process caught it, which is the point — but it means the honest baseline going into crypto is "the current alpha signal, on this asset class, has not yet been shown to beat noise once methodology was tightened." Crypto microstructure is noisier than equities, not less, so this bar gets harder, not easier.

---

## 1. Architecture Quality Review

### 1.1 What's genuinely well-built

- **IC-gated feature promotion (Gate 0→1→2→3).** The 5-gate process — baseline → holdout lock → per-family IC test → live observation → holdout validation — is a real defense against the single biggest failure mode in retail quant: shipping a feature that looks good because of multiple-comparisons luck. Most people don't build this. Keep it, and use the exact same gate structure for every new crypto-specific feature (on-chain flows, funding rate, etc.) rather than skipping the ceremony because "crypto is different."
- **Immutable backtest run registry** (`backtests/runs/<run_id>/` with `strategy_config.json` + `run_meta.json` git-commit snapshot). This is the kind of reproducibility hygiene that separates "I think this works" from "I can prove this worked, on this exact code, on this exact date." Directly reusable for crypto backtests unchanged.
- **Multi-seed variance estimation.** Fixed-seed AUC deltas that looked like signal turned out to be indistinguishable from seed-to-seed noise once actually measured — and you caught your own methodology bug here. This habit (always ask "is this delta bigger than seed-to-seed variance?") matters even more in crypto, where regime shifts (a single BTC halving cycle, a single exchange collapse) can dominate a whole backtest window.
- **Explicit conflict-tracking in project docs.** Most projects lose track of which of several competing specs is canonical. You've built a habit of flagging it in writing. Keep doing this as you fork equity-only docs into crypto-only docs — you're about to create a new source of exactly this kind of drift (e.g., two `feature_store.py` variants, one per asset class).

### 1.2 Confirmed bugs to fix before porting to crypto (from `engine/ENGINE_REVIEW.md`)

Worth confirming current status before the port, since some may already be fixed in later work. Flagging the ones most dangerous to carry into a new asset class:

| Issue | Why it matters *more* for crypto |
|---|---|
| `INTERVAL ':days days'` SQLite syntax crash in `compute_rolling_ic()` | If this still throws, every IC computation silently breaks — and crypto is exactly where you need IC discipline most, given noisier signals. |
| `is_live_approved()` uses AUC (`confidence`) instead of true IC | Same bug, but crypto's higher noise floor makes the AUC/IC gap larger — a model could clear an AUC-based gate while having genuinely poor IC. |
| IC floor `max(0.01, ic)` hides negative IC | In equities this masks a weak model. In crypto, momentum/mean-reversion signals can flip sign entirely across a bull/bear regime — silently floor-clamping a negative IC during a regime flip means you keep trusting a model that's actively wrong. |
| `execution/order_manager.py::confirm_order()` hardcodes `ticker = "UNKNOWN"` | Crypto trading is 24/7 — if any part of crypto execution is semi-automated (vs. the current manual-approval equities model), a silent `UNKNOWN` ticker in the trade log becomes a real reconciliation nightmare fast, since there's no market close to catch it before the next session. |
| `DISTINCT ON` (Postgres-only) in `reconciliation/state_reconciler.py` | Crashes on SQLite regardless of asset class, but crypto's 24/7 cadence means reconciliation runs more often, so this fails more often. |
| `execution/` and `reconciliation/` modules never wired into `scheduler.py` at all | This is the big one. Per `ENGINE_REVIEW.md` §15, **the full signal→weights→orders→risk loop is not actually connected to the daily pipeline today**. The system produces signals and BL weights, but nothing turns them into logged orders with real risk checks. Don't build a crypto-specific execution path on top of a loop that isn't wired for equities either — wire it once, correctly, then extend. |

**Recommendation:** treat this as a pre-req, not parallel work. Porting alpha/data logic onto an execution loop with a hardcoded `UNKNOWN` ticker bug means your first real crypto paper trades will be unreconcilable, which defeats the purpose of a sandbox phase.

### 1.3 Architectural decisions that need to be made explicitly for crypto (not inherited from equities)

- **Market structure model.** Equities: single primary exchange (Xetra for your `.DE` tickers), one official close, T+2 settlement, market hours. Crypto: dozens of exchanges with different prices for the same asset, 24/7 continuous trading, no "close." Your `prices` table schema (`date, ticker, adj_close`) implicitly assumes one row per ticker per day. For crypto you need to decide: which exchange(s) is canonical per asset, whether you store OHLCV at daily or intraday granularity, and how you define "today's price" for a Black-Litterman run when the market never closes. This is a schema-level decision, not a data-source swap — plan for it before writing ingestion code, not after.
- **Rebalance cadence.** Daily equity rebalancing made sense against a single close. In crypto, "daily at what UTC hour" is an arbitrary choice you need to make and document, since there's no natural anchor.
- **Universe definition & survivorship bias.** `TICKER_SECTORS`/`ASSET_UNIVERSE` for equities is relatively stable. Crypto universes churn constantly (delistings, rugs, new listings) — your walk-forward backtest needs a point-in-time universe snapshot per date, or you'll get survivorship-biased backtest results (testing only on coins that are still around today). This is a common, serious crypto-quant mistake — worth an explicit check in your backtest engine.
- **"Sector" doesn't map cleanly.** `TICKER_SECTORS` (GICS-style) has no crypto equivalent. You'll want a crypto-native categorization (L1 / L2 / DeFi / infra / meme / stablecoin-adjacent) for the correlation-cluster and concentration-cap logic to mean anything. Naively leaving `sector_map` empty would silently disable your 30% sector cap and sector-relative-momentum feature — worth flagging explicitly rather than discovering it later.
- **Position/sector caps calibrated for equity vol.** Your 10-15% single-position cap and 30% sector cap were sized for equity volatility and correlation structure. Crypto's higher pairwise correlation (most alts move with BTC) means a naively-reused 25% correlation-cluster cap could still leave you effectively concentrated in "crypto beta" even while nominally diversified across 10 tickers.

---

## 2. ML Model Critique

### 2.1 Current state (equities side) — the honest read

Per the project's own Gate 2 results log:
- `db_regime`, `pead`, `earnings` features: +0.0008 to +0.0009 AUC delta — below the +0.003 bar, and once multi-seed variance was actually measured, this delta turned out to be *smaller than the seed-to-seed noise floor*. Inconclusive at best, not a pass.
- `crosssectional` and `acceleration` feature families: failed outright (-0.0054, -0.0063).
- `target_refinement` (predicting alpha instead of absolute return): failed clearly (-0.023).
- Base model: XGBoost/LightGBM ensemble, mean AUC ≈ 0.633 on 126 tickers, with an admittedly thin `n_obs=6` for IC (explicitly flagged in your own docs as too small to trust).

This means: as of today, **the feature-expansion program on the equities side has not produced a single confirmed win**, and the baseline model itself has a very thin IC sample. This isn't a criticism of the process — the gating caught all of it, which is exactly what it's for — but it's the correct baseline expectation to carry into crypto: don't assume the current alpha stack is a proven edge that just needs a new data source bolted on. Treat crypto as a fresh Gate-0 baseline, not an extension of a working equities edge.

### 2.2 Model architecture observations

- **XGBoost/LightGBM ensemble + LSTM** is a reasonable choice for tabular financial features, but AUC ≈ 0.63 with high seed-to-seed variance on equities suggests the current feature set may be near its information ceiling for this model class — more feature engineering on the *same* feature families is unlikely to move the needle much further (consistent with the Gate 2 results). For crypto, this argues for **new information sources** (§3 below) over re-running the same technique on new tickers.
- **AUC as the sole gating metric has a known blind spot**: `is_live_approved()` uses `confidence` (which for ML models is AUC-derived) as a proxy for IC, but these measure different things — AUC measures classification separability, IC measures rank correlation with actual forward returns, which is what actually feeds Black-Litterman's expected-return inputs. Fix this before crypto: either populate the unused `ic_21d`/`ic_63d` columns, or have the gate call `compute_rolling_ic()` directly.
- **The IC floor `max(0.01, ic)` hiding negative IC** (§1.2 above) is worth fixing as an ML-quality issue too, not just a bug: a model with genuinely negative IC on crypto during a regime flip (e.g., a momentum model during a sharp reversal) should be excluded or inverted, not silently floored to a small positive weight.
- **Confirm a defined retrain cadence** (e.g., monthly with expanding or rolling window) rather than a single static fit, since crypto regime half-life is shorter than equities (a model trained pre-halving is less useful post-halving than an equity model trained pre/post a normal earnings cycle).

### 2.3 Crypto-specific ML considerations

- **Non-stationarity is worse.** Crypto return distributions shift faster than equities (new narrative cycles, leverage cascades, regulatory shocks). Favor models and features that degrade gracefully (rolling/expanding windows, regime-conditional models) over anything trained once on a long static history.
- **Funding rate and open interest carry real predictive information that has no equity analogue** — this is likely a better first crypto-specific feature to Gate-2-test than reusing PEAD/earnings-style features, since it doesn't require forcing an equity concept onto a market structure that doesn't have earnings.
- **Watch for feature leakage via exchange-reported data revisions** — similar in spirit to bugs you've already caught in this codebase (an FX inversion bug, and a PEAD feature-builder audit that caught forward-return columns almost entering the training set as features). On-chain and exchange data sources sometimes backfill/restate (e.g., reorg-adjusted on-chain metrics); apply the same "1-day-lag / no-lookahead" discipline you already use in `feature_builder.py`.
- **Sample size will initially be *worse*, not better, than equities**, despite crypto having more raw price history for majors — because your universe will likely start smaller (a few dozen liquid pairs vs. 126 equities) and cross-sectional IC testing needs breadth. Consider whether your Gate 2 methodology (designed for 126-name breadth) needs adjustment for an initially-narrower crypto universe, or whether you delay cross-sectional features until the universe grows.

---

## 3. Alternative Data — Crypto-Specific Recommendations

Organized by how directly it plugs into your existing `feature_store.py` pattern (per-ticker, portfolio-level, or regime-level) and by how mature/accessible the data source is.

### 3.1 On-chain data (no equity equivalent — likely your highest-value new signal category)

| Data | What it captures | Source ideas | Fits into |
|---|---|---|---|
| Exchange net flows (inflow − outflow) | Selling/accumulation pressure — large net inflows to exchanges historically precede sell pressure | Glassnode, CryptoQuant, Nansen | Per-ticker feature, similar slot to your momentum features |
| Active addresses / new addresses | Network usage growth, adoption proxy | Glassnode, IntoTheBlock, on-chain RPC + your own indexer | Per-ticker |
| Whale wallet concentration / large transaction count | Concentration risk, smart-money positioning | Nansen, Arkham, Whale Alert | Per-ticker or portfolio-level regime input |
| Stablecoin supply changes (USDT/USDC mint/burn, exchange stablecoin reserves) | Dry powder proxy for the whole market | Glassnode, on-chain directly (cheap — public contracts) | Portfolio/regime-level, analogous to your macro regime block |
| Realized cap / MVRV (market value to realized value) | Cycle-position / over-under-valuation proxy for majors | Glassnode | Portfolio-level regime feature |

**Practical note:** several of these are the closest crypto equivalent to your existing "macro regime" block (`compute_macro_regime_features()`) — a stablecoin-supply/MVRV-based "crypto macro regime" one-hot feature set would map cleanly onto the same pattern you already use for VIX/yield-curve/Fed-funds, feeding the same slot in Black-Litterman.

### 3.2 Derivatives market data (mature, cheap, high signal-to-noise for crypto specifically)

| Data | What it captures | Source | Fits into |
|---|---|---|---|
| Perpetual funding rate | Crowd positioning skew (persistent positive funding = crowded long) | Binance/Bybit/OKX public APIs, Coinglass aggregator | Per-ticker feature — likely your best first crypto-specific alpha candidate |
| Open interest (and OI-weighted funding) | Leverage buildup, liquidation cascade risk | Same exchanges, Coinglass | Per-ticker + risk-engine input |
| Options put/call skew, implied vol term structure | Forward-looking sentiment, tail-risk pricing | Deribit (dominant crypto options venue) | Per-ticker for majors (BTC/ETH have liquid options; alts mostly don't) |
| Liquidation levels/heatmaps | Where cascades are likely to trigger | Coinglass, exchange APIs | Risk-engine input, not alpha — useful for your circuit-breaker/drawdown logic to anticipate cascade risk rather than just react to realized drawdown |

**Practical note:** funding rate is the single most commonly cited crypto-native edge in public research and is cheap/free to obtain — a strong first candidate to run through your existing Gate 0→2 process rather than something exotic.

### 3.3 Sentiment / social / narrative data

| Data | What it captures | Source | Caveat |
|---|---|---|---|
| Social volume/sentiment (mentions, sentiment score) | Retail attention, narrative momentum | LunarCrush, Santiment | Historically noisy and prone to overfitting in backtests — treat with the same skepticism your Gate 2 process already applies, don't assume it works just because it's "alt data" |
| Google Trends | Retail interest proxy, lagging but free | Google Trends API | Free but low-frequency (daily at best) and lagging — better as a regime input than a timing signal |
| Developer activity (GitHub commits, contributor count) | Long-horizon fundamental proxy for L1/L2 projects | Santiment, GitHub API directly (free) | Slow-moving — more relevant to a monthly/quarterly rebalance factor than a daily signal |

**Caveat worth stating plainly:** sentiment data is the most commonly *oversold* category of crypto alt-data. It shows up in a lot of vendor marketing and very little of it survives out-of-sample IC testing once transaction costs are included. Gate it exactly as skeptically as your worst-performing equity feature families were gated — expect it to fail Gate 2 more often than it passes, and don't lower your bar because it's "crypto-native."

### 3.4 Macro / cross-asset (extends your existing macro regime block, doesn't replace it)

Your existing `macro_vix`, `macro_yield_spread`, `macro_hy_spread`, `macro_fed_funds` block is **not obsolete for crypto** — crypto has become increasingly correlated with risk assets generally (especially post-2022), so keeping traditional macro regime features alongside crypto-native ones is likely additive, not redundant. Consider adding:
- **DXY (dollar index)** — crypto (especially BTC) has shown a persistent inverse relationship with dollar strength in recent cycles.
- **Nasdaq/QQQ correlation regime** — crypto's correlation to tech equities is itself regime-dependent (high during risk-off, lower during crypto-specific narrative rallies) — worth its own rolling-correlation feature rather than assumed constant.

### 3.5 Data provider / infrastructure notes

- The same commercial-use ToS due diligence you've already applied to `yfinance` for equities applies equally here: Glassnode, Nansen, CryptoQuant, Coinglass, Santiment all have separate free/paid tiers with materially different rate limits and, for some, redistribution restrictions if this becomes a paid product per your SaaS plans. Resolve this as an explicit decision, not a default.
- For price/OHLCV itself: exchange-native APIs (Binance, Coinbase, Kraken) are free and don't have the same commercial-use ambiguity yfinance does for equities — likely your cleanest primary price source, with a data-aggregator (CCXT library) to normalize across exchanges if you want multi-exchange coverage.

---

## 4. Risk Engine Recalibration for Crypto

Not alt-data, but adjacent enough to flag here since it directly affects whether your existing risk code is safe to reuse as-is:

- **Circuit breaker thresholds** (-15% stock / -12% ETF) will fire almost constantly if reused unchanged for crypto — daily moves of this size are unremarkable for mid/small-cap alts. Needs asset-class-specific (or volatility-normalized, e.g. ATR-based) thresholds, not a blanket equity number.
- **Portfolio drawdown protocol** (a three-tier -10%/-15%/-20% alert/halve/pause structure) — same recalibration need. Consider whether the tiers should be in vol-adjusted terms (e.g., "X standard deviations of realized portfolio vol") rather than fixed percentages, so the same policy logic works across both equity and crypto sleeves if you ever run them side by side.
- **VaR/CVaR and Monte Carlo sims** — the underlying math is asset-class-agnostic, but your existing MC seed-fix and covariance shrinkage (Ledoit-Wolf) both become *more* important in crypto, not less, because raw sample covariance is even noisier with crypto's fat tails and shorter reliable history per asset.
- **Kelly sizing** (`kelly_half`) — half-Kelly was likely chosen as conservative-enough for equity vol. Given crypto's higher realized vol, worth reconsidering whether even quarter-Kelly is appropriate, since Kelly sizing formulas are highly sensitive to vol/edge estimation error, and your edge estimates (IC) are — per §2.1 — not yet confirmed robust for this asset class.

---

## 5. Suggested Sequencing

1. **Fix the pre-existing bugs in `engine/ENGINE_REVIEW.md`** that affect the shared (asset-class-agnostic) engine code — especially the unwired execution/reconciliation loop (§15) and the IC/AUC conflation. Do this on the equities side first since it's already running; don't debug it for the first time on top of new crypto terminology.
2. **Make the explicit architecture decisions in §1.3** (market structure model, rebalance cadence, universe/survivorship handling, crypto-native sector taxonomy) *before* writing crypto ingestion code — these are schema-level, expensive to retrofit.
3. **Stand up crypto price/OHLCV ingestion first, alone** (exchange APIs via CCXT or similar) and get a crypto Gate-0 baseline using your *existing* momentum/vol/RSI features, unchanged — this tells you whether your current feature set has any edge at all on crypto before you add anything crypto-native. Cheap experiment, high information value.
4. **Layer in funding rate as the first crypto-native feature family**, run it through the same Gate 0→2 process. It's cheap, liquid-market-covered, and has the most public precedent as a real signal — good first test of whether your gating process works as well on crypto noise as it did on equities.
5. **Recalibrate risk engine thresholds (§4)** before any paper trading — don't inherit equity circuit-breaker/drawdown numbers by default.
6. **Only then** layer in on-chain and sentiment data, gated with the same skepticism, expecting a similar hit rate to what you saw on the equities feature-expansion program (i.e., expect most experiments to fail Gate 2 — that's the process working, not a sign to loosen the bar).

---

## 6. Open Questions for You

- Are you running crypto as a **separate sleeve/instance** (own DB, own scheduler run) or **integrated into the same portfolio** as the EU equities? This materially changes the schema decision in §1.3 — a separate sleeve is much less invasive to your current, working equities pipeline.
- Do you have a target initial universe (majors only — BTC/ETH/SOL-tier — vs. a broader 50-100 name universe)? This affects whether cross-sectional features are viable at all initially (§2.3).
- Is any part of crypto execution intended to be automated (exchange API), unlike the current manual-approval equities model? If so, the unwired execution loop (§1.2, §15 of `ENGINE_REVIEW.md`) becomes a hard blocker, not a nice-to-have fix, given crypto's 24/7 cadence removes the "human checks it before market open" safety net equities implicitly has.
