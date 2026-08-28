# 08: Options Flow, Gamma Exposure (GEX), & Dark Pools

## 1. The Concept
Institutional whales rarely buy equities directly on the lit market when they want to build massive positions; they use dark pools to hide their footprint, or they use options to gain leveraged exposure. Furthermore, Market Makers delta-hedge their options books, which creates "Dealer Gamma Exposure" (GEX). When GEX is highly positive, market makers suppress volatility. When GEX is highly negative, market makers are forced to buy/sell in the same direction as the trend, causing explosive volatility and gamma squeezes.

By tracking unusual options activity (sweeps/blocks), put/call ratios, and dark pool prints, the ML model gains a massive predictive edge on institutional positioning before the broader market reacts.

## 2. Target Data Sources
- **Options Data & GEX**: 
  - `polygon.io` (Options API for real-time flow and Greeks).
  - `yfinance` (Free alternative for basic option chains, though less reliable for intraday sweeps).
  - `unusualwhales` or `CBOE` datashop (Paid APIs for exact institutional sweep detection).
- **Dark Pool Prints**:
  - FINRA TRF (Trade Reporting Facility) daily files.
  - `chartexchange.com` (Web scraping source for dark pool volume).

## 3. Feature Engineering
The data pipeline will aggregate this raw flow into daily ticker-level features for `feature_store.py`:
- `opt_put_call_ratio`: Total put volume / total call volume.
- `opt_gamma_exposure`: Estimated dealer gamma (Net Call Gamma - Net Put Gamma).
- `opt_sweep_volume_call`: Dollar volume of aggressive "sweep" orders on calls.
- `opt_iv_rank_30d`: Implied Volatility Rank (where current IV sits relative to the last 30 days).
- `dp_volume_ratio`: Dark Pool Volume / Total Lit Volume. High dark pool ratio on a down day implies institutional accumulation (buying the dip).

## 4. Pipeline Architecture
1. **Extraction**: A new module `engine/data/options_fetcher.py` runs daily after market close. It pulls the option chains and FINRA TRF files.
2. **Processing**: Calculates the net dealer gamma and aggregates dark pool volume.
3. **Storage**: Saves to a new database table `options_data`.
4. **Feature Store**: `feature_store.py` reads from `options_data` and merges `opt_*` and `dp_*` columns into the main ML feature set. Missing data gracefully degrades (columns dropped for that ticker, as implemented in Phase 1).

## 5. Implementation Roadmap
- **Phase 1 (Basic Options)**: Use `yfinance` to scrape the nearest 2 expiration dates for the 10 most liquid tickers. Calculate basic Put/Call ratios and Implied Volatility.
- **Phase 2 (Dark Pools)**: Write a scraper for FINRA TRF CSVs to calculate daily `dp_volume_ratio`.
- **Phase 3 (GEX & Sweeps)**: Integrate a paid API (Polygon or Unusual Whales) to calculate exact Dealer Gamma Exposure and track multi-exchange sweep orders.

## 6. Risks & Mitigation
- **Sparsity**: Mid-cap stocks have highly illiquid options chains. 
  - *Mitigation*: Only calculate options features for the most liquid large-cap universe. Use the graceful degradation logic in `ml_alpha.py` to drop the `opt_` columns for illiquid tickers.
- **Data Cost**: High-quality options flow data is notoriously expensive.
  - *Mitigation*: Start with end-of-day summary data rather than a real-time firehose. EOD options data is significantly cheaper and sufficient for a swing-trading pipeline.
