# 02 - Real-Time News & Narrative Sentiment

## Concept
Standard momentum models react to price changes; NLP models react to the *news* causing the price changes before the market fully digests it. This agent classifies breaking financial news specifically on how it impacts future margins or revenue, giving you a massive speed advantage.

## Data Sources
- **Yahoo Finance News / Finviz RSS:** Free, high-velocity feeds of ticker-specific news.
- **Social/Retail Feeds:** Reddit (r/wallstreetbets, r/investing) or X (Twitter) APIs for retail momentum tracking.

## Core Features to Extract

### 1. Fundamental News Impact Score
- **Mechanism:** As a news article drops for a ticker in your universe, the agent scrapes the body text.
- **LLM Task:** "You are a hedge fund analyst. Read this breaking news article about [Ticker]. Classify its expected impact on the company's future operating margins and top-line revenue on a scale of -1.0 to 1.0."
- **Output:** `news_margin_impact_score`, `news_revenue_impact_score`.

### 2. Retail Momentum Divergence
- **Mechanism:** Scrape ticker mentions on X and Reddit. Calculate the volume of mentions and the sentiment.
- **Logic:** High retail sentiment + high mention volume + low institutional buying = classic retail "pump". This often signals a short-term momentum burst followed by a harsh reversal.
- **Output:** `retail_euphoria_flag` (Boolean). Allows the ML model to learn to fade retail euphoria.

## Architecture Pipeline
1. **Streaming Ingestion:** A script constantly polls RSS feeds or WebSockets for breaking news on your 126 tickers.
2. **LLM Triage:** Fast, small models (like Llama 3 8B or Gemini Flash) are used to quickly triage and score the news within seconds.
3. **Decay Function:** News impact decays over time. The scores are written to the database but exponentially decayed over a 7-day half-life before being fed into `feature_builder.py`.
