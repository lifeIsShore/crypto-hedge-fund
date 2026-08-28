# 11: ESG, Carbon, and "Green-Washing" Sentiment

## 1. The Concept
Environmental, Social, and Governance (ESG) mandates now govern trillions of dollars in institutional capital (e.g., BlackRock, Vanguard, State Street). If a company's ESG score is downgraded, or if they are caught in a major environmental scandal, institutional funds are often mandated by their own bylaws to sell the stock, regardless of the company's financial health. Conversely, upgrades to ESG inclusion lists can trigger massive, price-insensitive institutional buying. 

Tracking ESG ratings and real-time social sentiment regarding a company's environmental impact allows the ML model to predict these institutional capital flows.

## 2. Target Data Sources
- **Public ESG Ratings**:
  - MSCI ESG Ratings (Public search tool).
  - Sustainalytics (Yahoo Finance provides basic Sustainalytics Risk Scores via `yfinance`).
  - Refinitiv ESG scores.
- **Real-Time Sentiment (Green-Washing/Scandals)**:
  - Twitter / Reddit / LinkedIn NLP parsing for keywords like "pollution", "scandal", "greenwashing", "carbon", "boycott" associated with the ticker.
- **Regulatory Filings**:
  - SEC filings for environmental disclosures or EPA violation database.

## 3. Feature Engineering
The ML model requires slow-moving structural features (the ratings) and fast-moving sentiment features (the scandals):
- `esg_risk_score`: Raw ESG risk score (0-100) from Sustainalytics.
- `esg_score_delta`: Change in the ESG rating over the last 90 days.
- `env_scandal_spike`: A binary flag (0/1) indicating a 3-sigma spike in negative environmental/social keywords on social media over the last 48 hours.
- `esg_inclusion_flag`: Indicates if the stock was recently added to a major ESG index (ETF holdings proxy).

## 4. Pipeline Architecture
1. **Baseline Extraction**: `engine/data/esg_fetcher.py` runs monthly to pull updated ESG risk scores from Yahoo Finance/Sustainalytics for the entire universe.
2. **Real-Time Social Monitor**: The existing News/NLP pipeline is augmented with an ESG-specific dictionary. It scores daily news articles specifically for environmental or social governance risks.
3. **Feature Store Integration**: The structural `esg_*` features and the fast-moving `env_scandal_*` features are appended to the ML feature matrix.

## 5. Implementation Roadmap
- **Phase 1 (YFinance Baseline)**: Utilize the `yfinance` library (`ticker.sustainability`) to extract the baseline Sustainalytics ESG Risk Score, Environment Score, and Social Score. Add these as static/slow-moving features to the ML model.
- **Phase 2 (ETF Inclusion Tracker)**: Monitor the daily holdings of massive ESG ETFs (like ESGU or SUSA). If a ticker is added or dropped from these ETFs, flag it as a highly predictive feature for imminent institutional flow.
- **Phase 3 (NLP Scandal Detection)**: Integrate ESG-specific keyword tracking into the real-time news sentiment pipeline to catch fast-moving controversies before the rating agencies update their scores.

## 6. Risks & Mitigation
- **Slow-Moving Data**: Official ESG ratings update very slowly (often annually), meaning the raw score itself doesn't provide daily alpha.
  - *Mitigation*: The alpha is in the *change* (ETF inclusion/exclusion) and the *fast-moving sentiment* (scandals), rather than the static score.
- **Subjectivity**: ESG scores vary wildly between different rating agencies.
  - *Mitigation*: Stick to the most widely followed agencies (MSCI, Sustainalytics) as these are the ones that actually drive passive ETF flows.
