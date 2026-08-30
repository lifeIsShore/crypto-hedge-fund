# Crypto Alternative Data Strategy

As we move past the V1 Crypto Hedge Fund pivot, we need to introduce crypto-native alternative data sources to gain an edge. Traditional alternative data (credit card receipts, satellite imagery) doesn't apply to crypto. Instead, we will focus on these three pillars:

## 1. On-Chain Metrics (The "Fundamentals")
Crypto ledgers are public. We can track the movement of capital in real-time.
- **Exchange Inflows/Outflows:** Large net inflows to exchanges usually precede selling pressure (whales depositing to dump). Outflows indicate accumulation.
- **Whale Wallet Tracking:** Monitoring known large holders or institutional wallets for sudden movements.
- **Network Activity & Adoption:** Active addresses, transaction counts, and gas fees/network revenue. Higher activity often precedes price appreciation (Metcalfe's Law).
- **MVRV Z-Score (Market Value to Realized Value):** Identifies periods where an asset is extremely overvalued or undervalued relative to its "fair value" based on when coins last moved.

*Potential Providers:* Glassnode, CryptoQuant, or direct RPC node extraction.

## 2. Market Microstructure & Derivatives (The "Liquidity")
The crypto market is heavily driven by leverage and derivatives.
- **Funding Rates (Perpetual Futures):** High positive funding rates indicate excessive long leverage (crowded trade, risk of long squeeze). Negative rates indicate excessive shorting (potential short squeeze).
- **Open Interest (OI):** Spikes in OI combined with price consolidation often precede explosive volatile moves.
- **Liquidations:** Real-time cascading liquidations act as momentum accelerators. We can build mean-reversion signals immediately following massive liquidation wicks.
- **Orderbook Imbalance (Depth):** Tracking the ratio of bids to asks within 2% of the current price across major exchanges (Binance, Coinbase, Kraken).

*Potential Providers:* Coinglass, Binance Futures API, CCXT Orderbook streams.

## 3. Social Sentiment & NLP (The "Crowd")
Crypto is highly reflexivity-driven by retail sentiment.
- **X (Twitter) & Telegram Sentiment:** Volume of mentions and NLP sentiment scoring for specific tickers. Extreme euphoria usually marks local tops; extreme fear marks bottoms.
- **Funding/VC Mentions:** Tracking smart money narrative shifts (e.g. tracking mentions of "AI", "RWA", "DePin").
- **Fear & Greed Index:** Broad market sentiment indicator.
- **Developer Activity:** GitHub commits, active developers, and pull requests for open-source crypto protocols as a proxy for long-term viability.

*Potential Providers:* LunarCrush, Santiment, GitHub API, OpenAI/LLM sentiment analysis on scraped news.

## Implementation Roadmap
1. **[x] Phase 1 (Easy Wins):** Integrate Funding Rates and Open Interest via CCXT. Added `fetch_funding_rates` via CCXT in `engine/data/funding_rates.py` and connected them into `feature_builder.py` as alternative ML features.
2. **[x] Phase 2 (On-Chain):** Integrated free DeFiLlama API for TVL and Stablecoin inflows. Added `onchain_metrics.py` ingestion and wired it into `feature_builder.py`.
3. **[x] Phase 3 (NLP/Social):** Built a scheduled scraper for Crypto RSS feeds in `sentiment_scraper.py`, parsed headlines using VADER with custom crypto lexicon, and generated a daily sentiment score for the pipeline.
