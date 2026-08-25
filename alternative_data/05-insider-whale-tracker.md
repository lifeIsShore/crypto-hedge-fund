# 05 - The "Insider & Whale" Tracker

## Concept
Following the "smart money" mathematically. While retail sentiment can be noisy, when corporate executives or politicians buy stock with their own cash, it is a highly reliable leading indicator of future outperformance.

## Data Sources
- **SEC EDGAR:** Specifically Form 4 filings (Statement of Changes in Beneficial Ownership).
- **Public Disclosures:** Congressional trading disclosure databases.

## Core Features to Extract

### 1. Cluster Insider Buying
- **Mechanism:** Executives get stock options, so insider selling is normal and mostly noise. But insider *buying* with their own cash is rare. A script parses SEC Form 4s for open-market purchases by C-suite executives or board members.
- **Logic:** If 3 or more executives buy open-market shares in the same week, it is classified as "Cluster Buying". This indicates massive internal confidence.
- **Output:** `cluster_insider_buy_30d` (Boolean). 

### 2. Congressional Trade Tracking
- **Mechanism:** Scrape the disclosures of US Senators, Representatives, and committee members.
- **Logic:** If multiple politicians sitting on the Defense Committee suddenly buy defense stocks, or politicians heavily buy semiconductor stocks, it often precedes massive government contracts, subsidies, or favorable legislation.
- **Output:** `abnormal_political_buying` (Boolean).

## Architecture Pipeline
1. **Daily SEC Poller:** A script that polls the SEC EDGAR RSS feed for new Form 4 filings.
2. **Parsing Logic:** It filters out automated sales (10b5-1 plans) and option exercises, isolating only open-market cash purchases.
3. **Aggregation:** It aggregates the purchases by ticker. If the threshold (e.g., >3 insiders, or >$1M total) is met within a rolling 30-day window, the flag is flipped to True in the ML feature matrix.
