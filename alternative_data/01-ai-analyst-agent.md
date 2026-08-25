# 01 - The "AI Analyst" Agent (Earnings & SEC Filings)

## Concept
Instead of relying solely on quantitative fundamental data (like EPS or Revenue), this agent uses LLMs to read unstructured corporate text (SEC Filings, Earnings Call Transcripts) exactly like a human fundamental analyst would. It extracts sentiment, operational tone, and management evasiveness.

## Data Sources
- **SEC EDGAR:** For 10-K and 10-Q filings.
- **Transcript Aggregators:** SeekingAlpha, Motley Fool, or specialized transcription APIs for quarterly earnings calls.

## Core Features to Extract

### 1. MD&A Sentiment Shift
The "Management Discussion and Analysis" section of a 10-Q is highly scripted.
- **Mechanism:** The agent pulls the current quarter's MD&A and the previous quarter's MD&A.
- **LLM Task:** "Compare these two texts. Score the shift in management's tone on a scale of -1.0 to 1.0. Highlight specific additions of cautious vocabulary (e.g., 'macroeconomic headwinds', 'supply chain uncertainty') or optimistic vocabulary."
- **Output:** `mda_sentiment_delta` (Float). A negative delta strongly predicts future underperformance.

### 2. Earnings Call Evasiveness Score
CEOs are trained to answer analyst questions positively, but studies show that when fundamentals are deteriorating, CEOs use excessively complex language, long-winded answers, and "dodge" direct questions during the Q&A session.
- **Mechanism:** Parse the Q&A section of the earnings call transcript.
- **LLM Task:** "Analyze the CEO's responses to analyst questions. Score the level of evasiveness, complexity, and directness on a scale of 0 to 1."
- **Output:** `management_evasiveness_score` (Float). High evasiveness is a strong sell signal.

## Architecture Pipeline
1. **Cron Job:** Runs weekly to check for new filings/transcripts for the universe of 126 tickers.
2. **Scraper Service:** Downloads the raw HTML/PDF and cleans it into plain text.
3. **LLM Microservice:** Passes the text to a local LLM (e.g., Llama 3 8B) or cheap API (e.g., Gemini Flash / Claude 3 Haiku) enforcing a strict JSON output schema.
4. **Database:** Writes the resulting scores to a SQL table `ai_fundamental_scores`, which is then joined by `feature_builder.py` during ML training.
