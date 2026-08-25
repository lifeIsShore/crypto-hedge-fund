# 07 - Supply Chain & Macro NLP

## Concept
For manufacturing, hardware, and retail companies, the biggest risk to their margins is the cost of goods sold (COGS). By scanning global shipping and logistics news, an AI agent can predict margin contractions caused by supply chain bottlenecks before the earnings call.

## Data Sources
- **Industry Trade Publications:** Shipping news (e.g., FreightWaves), commodities news.
- **Global Port/Logistics Data:** News regarding port strikes, canal blockages (e.g., Suez/Panama), or container pricing indices (e.g., Freightos Baltic Index).

## Core Features to Extract

### 1. Commodity & Logistics Bottleneck Flag
- **Mechanism:** The agent constantly scans global shipping news.
- **LLM Task:** "Identify any major disruptions to global supply chains, such as port strikes, shipping lane blockages, or semiconductor shortages. If a disruption is found, list the specific industries heavily exposed to it (e.g., 'Automotive', 'Consumer Electronics')."
- **Output:** `supply_chain_disruption_risk` (Boolean). This flag is mapped to specific sectors in your universe. If a port strike hits, the flag flips to True for all retail and manufacturing stocks in your portfolio.

### 2. Input Cost Inflation Proxy
- **Mechanism:** NLP parsing of raw commodity news (lumber, copper, oil) or scraping of real-time container freight pricing indices.
- **Logic:** If the cost to ship a container from Shanghai to LA spikes by 50% in a month, margins for US consumer goods companies will contract in the following quarter.
- **Output:** `freight_cost_spike` (Boolean).

## Architecture Pipeline
1. **Targeted Scraping:** A script that parses specific logistics and shipping RSS feeds.
2. **LLM Mapping:** The LLM reads the disruption and maps it to a specific sector (e.g., Sector: Technology Hardware).
3. **Feature Broadcast:** The `supply_chain_disruption_risk` flag is broadcasted to every ticker in the affected sector within the `feature_builder.py` pipeline, allowing the ML model to tactically reduce exposure to those names ahead of earnings.
