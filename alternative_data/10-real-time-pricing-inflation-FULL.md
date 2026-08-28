# 10: Real-Time E-Commerce Pricing & Inflation Tracking

## 1. The Concept
For consumer discretionary, retail, and hardware tech companies, revenue is highly sensitive to pricing power. If a company is secretly slashing prices or running heavy promotions mid-quarter, it usually indicates weak consumer demand or bloated inventory, which leads to margin compression in the next earnings report. Conversely, if a company is consistently raising prices without losing market share, it demonstrates pricing power and strong future margins. 

By scraping real-time pricing data for a basket of a company's core products, the ML model can front-run earnings misses and beats.

## 2. Target Data Sources
- **Direct Corporate Storefronts**:
  - Tesla (EV vehicle prices).
  - Apple (iPhone/Mac availability and pricing).
- **Major Retailers / Aggregators**:
  - Amazon (Pricing, Best Seller Rank, and "Discount" percentage flags).
  - Walmart / Target (Inventory levels and rollback pricing).
- **Secondary Markets**:
  - StockX / eBay (Premium/Discount to MSRP for high-demand goods like sneakers or electronics).

## 3. Feature Engineering
Raw prices are normalized into rolling indices for the ML model:
- `price_index_30d`: The 30-day percentage change in the price of the company's core product basket.
- `discount_frequency`: The percentage of tracked SKUs currently marked as "On Sale" or "Clearance".
- `inventory_stockout_ratio`: The percentage of tracked SKUs that are "Out of Stock" (indicating high demand or supply chain constraint).
- `secondary_market_premium`: The percentage premium the product demands on secondary markets versus MSRP.

## 4. Pipeline Architecture
1. **Product Mapping**: Maintain a config file (`config/product_basket.yaml`) that maps specific tickers to specific product URLs (e.g., TSLA -> Model 3 order page, AAPL -> iPhone 15 Pro Amazon page).
2. **Scraping Engine**: A daily cron job (`engine/data/pricing_scraper.py`) visits these URLs, extracts the current price and stock status, and saves it to a database.
3. **Normalization**: Since a $50,000 car and a $1,000 phone are vastly different, the raw prices are converted into a normalized index (Base 100 on Day 1).
4. **Feature Store**: `feature_store.py` computes the rolling changes and provides `com_price_*` features to the ML engine.

## 5. Implementation Roadmap
- **Phase 1 (The Tesla/Apple Test)**: Build a simple web scraper that tracks the daily price of the Tesla Model 3/Y on Tesla.com, and the iPhone on Apple.com. These sites are relatively easy to scrape and highly correlated with the stock price.
- **Phase 2 (Amazon Bestsellers)**: Use an Amazon scraping API (like Rainforest API or Zinc) to track the pricing and Best Seller Rank (BSR) of flagship products for companies like Sony, Microsoft, and Logitech.
- **Phase 3 (Broad Basket Indexing)**: Expand the config to track 5-10 core products for all major retail/consumer discretionary tickers in the universe.

## 6. Risks & Mitigation
- **Dynamic DOM Changes**: E-commerce sites frequently change their HTML structure, breaking scrapers.
  - *Mitigation*: Rely on official APIs where possible, or use visual scraping / LLM-based parsing (passing the raw HTML to a cheap, fast LLM to extract the price) which is highly resilient to DOM changes.
- **Geographic Pricing**: Prices vary by IP address/region.
  - *Mitigation*: Ensure the scraper always routes through a consistent IP location (e.g., US-East) to maintain data continuity.
