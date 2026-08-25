# 03 - Digital Exhaust (Alternative Web Data)

## Concept
Company fundamentals are reported every 3 months. Digital exhaust happens every day in real-time. By tracking a company's web traffic, app downloads, and job postings, we can predict their quarterly earnings before they are officially announced.

## Data Sources
- **Career Pages:** Scraping Greenhouse, Lever, or direct corporate career portals.
- **Web Proxies:** SimilarWeb data (via proxy scraping) for web traffic estimates.
- **App Stores:** Scraping iOS/Android app store ranking histories.

## Core Features to Extract

### 1. Job Postings Momentum
- **Mechanism:** Scrape the total number of open engineering and sales roles for each company in your universe every week.
- **Logic:** A sudden drop in job postings is a massive leading indicator of a hiring freeze, margin contraction, or an upcoming earnings miss. A surge in postings signals high conviction growth.
- **Output:** `job_postings_30d_momentum` (Float).

### 2. Consumer Demand Proxy (Traffic/Downloads)
- **Mechanism:** For consumer and SaaS companies, track their website traffic or mobile app store rankings.
- **Logic:** If an e-commerce company's web traffic drops 20% in Q3 compared to Q2, you know their top-line revenue will likely miss estimates before the earnings call even happens.
- **Output:** `digital_traffic_momentum` (Float).

## Architecture Pipeline
1. **Weekly Scraper:** A Python `scrapy` or `playwright` agent that runs weekly to ping the career pages and app stores of the universe.
2. **Delta Calculation:** It calculates the rolling 30-day and 90-day momentum of these metrics.
3. **Feature Builder:** The raw momentum metrics are fed directly into the ML feature matrix as highly predictive leading indicators.
