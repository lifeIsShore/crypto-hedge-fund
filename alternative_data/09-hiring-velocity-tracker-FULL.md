# 09: Job Postings, Hiring Velocity & Glassdoor Sentiment

## 1. The Concept
A company's hiring behavior is one of the strongest leading indicators of its future financial performance. A sudden freeze in engineering or sales hiring often precedes a revenue miss, margin compression, or restructuring announcement. Conversely, a massive spike in hiring for a new product division indicates strong capital backing and management confidence. Combining hiring velocity with employee sentiment (Glassdoor/Blind reviews) provides a 360-degree view of corporate health long before the quarterly earnings call.

## 2. Target Data Sources
- **Hiring Velocity (Job Postings)**:
  - LinkedIn Jobs (via automated Playwright scraper or unofficial APIs).
  - Indeed / Glassdoor Jobs.
  - Corporate careers pages (Workday, Greenhouse, Lever integrations).
- **Employee Sentiment**:
  - Glassdoor (Rating out of 5.0, CEO Approval rating).
  - Blind (Tech/Finance specific, highly correlated with internal turmoil).

## 3. Feature Engineering
The pipeline translates raw job counts and reviews into normalized ML features:
- `job_velocity_30d`: % change in open job requisitions over the last 30 days.
- `job_velocity_90d`: % change in open job requisitions over the last 90 days.
- `tech_hiring_ratio`: (Engineering & Product Jobs) / (Total Jobs). A rising ratio indicates R&D expansion.
- `emp_sentiment_delta`: 30-day change in average Glassdoor/Blind rating.
- `ceo_approval_score`: Normalized 0-100 score of CEO approval.

## 4. Pipeline Architecture
1. **Scraping Engine**: A scheduled Playwright script (`engine/data/hiring_scraper.py`) runs weekly on Sunday nights to scrape job boards for the tracked universe of tickers.
2. **NLP Sentiment**: Employee reviews are parsed through a lightweight local LLM or VADER sentiment analyzer to gauge the tone of the reviews.
3. **Database**: Pushed to the `alternative_data` database table, keyed by date and ticker.
4. **Feature Store**: `feature_store.py` calculates rolling 30d/90d velocity metrics and feeds them into the ML pipeline as `hr_*` prefixed features.

## 5. Implementation Roadmap
- **Phase 1 (Glassdoor Sentiment)**: Use an open-source Glassdoor scraper to pull the top-level corporate ratings (Overall Rating, CEO Approval, Recommend to a Friend) for the ticker universe once a month.
- **Phase 2 (Career Page Parsing)**: Target the APIs of major ATS (Applicant Tracking Systems) like Greenhouse and Lever, which are often publicly accessible via JSON endpoints on corporate websites, bypassing the need for complex LinkedIn scraping.
- **Phase 3 (LinkedIn/Indeed Automation)**: Implement stealth Playwright automation with rotating proxies to scrape raw job posting counts across major aggregator sites.

## 6. Risks & Mitigation
- **Anti-Bot Defenses**: Sites like LinkedIn and Glassdoor have aggressive anti-scraping measures.
  - *Mitigation*: Use residential proxies, headless browser fingerprinting evasion (e.g., `playwright-stealth`), and keep request rates very low by running the job over the entire weekend. Alternatively, rely heavily on ATS JSON endpoints which are rarely protected.
- **Data Sparsity**: Small-cap companies may have too few job postings to generate a statistically significant velocity metric.
  - *Mitigation*: Apply these features exclusively to mid-cap and large-cap equities.
