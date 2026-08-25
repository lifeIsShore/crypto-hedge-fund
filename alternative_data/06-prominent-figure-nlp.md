# 06 - Prominent Figure Macro NLP

## Concept
Markets are heavily driven by the narratives and rhetoric of key individuals (Central Bankers, Politicians, influential Economists). This agent tracks what they say *as they say it*, providing real-time macro-regime indicators before official economic data is even published.

## Target Figures
- **Central Bankers:** Jerome Powell, Christine Lagarde, regional Fed Presidents.
- **Politicians:** President Trump, President Biden, key cabinet members.
- **Macro Economists/Investors:** Ray Dalio, Paul Krugman, Stanley Druckenmiller.

## Core Features to Extract

### 1. Real-Time Speech-to-Text Narrative Extraction
- **Mechanism:** The agent monitors live video streams (e.g., FOMC press conferences on YouTube) or podcast RSS feeds.
- **Processing:** Uses OpenAI's Whisper (or a fast local equivalent) to transcribe the audio into text with extremely low latency.
- **LLM Task:** The live transcript is streamed to an LLM in chunks. "Analyze this transcript segment from Jerome Powell. Extract any macroeconomic signals regarding inflation, interest rates, or quantitative tightening. Count the frequency of the word 'disinflationary'."
- **Output:** `dovish_fed_rhetoric` (Boolean), `hawkish_fed_rhetoric` (Boolean).

### 2. Social Media & Micro-Blogging Parsing
- **Mechanism:** Monitor X (Twitter) or Truth Social feeds of key figures.
- **LLM Task:** "Analyze this post. Does it indicate a shift towards protectionist trade policies, tariffs, or fiscal stimulus?"
- **Output:** `protectionist_policy_risk` (Boolean), `fiscal_stimulus_expected` (Boolean).

## The ML Synergy
Traditional quant models rely on trailing economic data (e.g., last month's CPI report). By extracting these narrative shifts, your ML model gains a massive leading indicator. If the agent flips `dovish_fed_rhetoric=True`, the ML model can immediately adjust its weighting towards growth/tech stocks before the actual rate cut happens.

## Architecture Pipeline
1. **Audio Ingestion:** `yt-dlp` or similar tools to capture live audio streams.
2. **Transcription:** `faster-whisper` running locally for real-time speech-to-text.
3. **LLM Engine:** Streams the text to a fast LLM (e.g., Llama 3 8B) for classification.
4. **State Update:** The resulting macro flags are written to `shared/state/macro_regime.json` where `feature_builder.py` picks them up as global features for all tickers.
