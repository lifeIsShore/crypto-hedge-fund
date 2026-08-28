# 12: Patent Filings & Clinical Trials (Tech/Biotech)

## 1. The Concept
For technology, semiconductor, and biotechnology companies, intellectual property is the primary driver of future valuation. A newly granted patent for a breakthrough AI chip architecture, or a successful Phase 2 clinical trial for an oncology drug, acts as an explosive binary catalyst. By systematically tracking USPTO (US Patent Office) filings and ClinicalTrials.gov updates, the ML model can price in technological innovation and regulatory milestones before retail investors read about it in the mainstream financial press.

## 2. Target Data Sources
- **Patent Data**:
  - USPTO Bulk Data / PatentsView API (Free APIs providing patent grants and applications by corporate assignee).
  - Google Patents (Scrapable alternative for specific corporate entities).
- **Clinical & Regulatory Data (FDA)**:
  - `ClinicalTrials.gov` API (Tracking Phase 1-3 progress, completion dates, and status changes).
  - OpenFDA API (For drug approvals, adverse event reports, and 510(k) device clearances).

## 3. Feature Engineering
The features track the volume and velocity of innovation:
- `patent_grant_velocity_90d`: The number of patents granted to the corporate entity in the last 90 days relative to their historical average.
- `ai_patent_ratio`: The percentage of recent patents containing keywords related to "Artificial Intelligence", "Machine Learning", or "Neural Networks".
- `trial_completion_imminent`: A binary flag (0/1) indicating that a Phase 2 or Phase 3 clinical trial is scheduled to complete within the next 30 days (a known catalyst event causing high implied volatility).
- `fda_adverse_spike`: A sudden spike in FDA adverse event reports for a company's flagship medical product.

## 4. Pipeline Architecture
1. **Entity Mapping**: Map financial tickers to their exact legal corporate assignee names (e.g., "AAPL" -> "Apple Inc.", "PFE" -> "Pfizer Inc.").
2. **Weekly Ingestion**: `engine/data/ip_tracker.py` runs every Tuesday (when the USPTO typically issues new patents) to query the PatentsView API for new grants.
3. **Daily Regulatory Monitor**: Queries the ClinicalTrials.gov API for status changes on tracked biotech tickers.
4. **Feature Store Integration**: Injects `ip_*` and `fda_*` prefixed features into the main ML feature matrix.

## 5. Implementation Roadmap
- **Phase 1 (Patent Velocity)**: Map the top 50 tech/semiconductor tickers to their USPTO assignee names. Use the PatentsView API to calculate a simple rolling 90-day patent grant velocity metric.
- **Phase 2 (Clinical Trial Catalyst Calendar)**: Map biotech/pharma tickers to the ClinicalTrials API. Build a feature that flags when a major trial shifts status from "Recruiting" to "Active, not recruiting" or "Completed", signaling an imminent data readout.
- **Phase 3 (NLP Patent Analysis)**: Pass the abstracts of newly granted patents through a local LLM to classify their potential impact or buzzword relevance (e.g., tagging patents as "GenAI" or "Solid State Battery").

## 6. Risks & Mitigation
- **Corporate Shell Games**: Large companies often file patents under obscure subsidiaries or shell companies to hide their R&D from competitors.
  - *Mitigation*: Utilize extensive corporate hierarchy mapping (available via databases like OpenCorporates) to link subsidiaries back to the parent ticker.
- **Binary Volatility**: Clinical trial readouts are highly volatile binary events. Models without proper risk constraints can get wiped out if they guess the trial outcome wrong.
  - *Mitigation*: The `trial_completion_imminent` feature should be used by the pipeline to *reduce* position sizing (via Black-Litterman/Kelly overrides) ahead of the binary event to protect capital, rather than trying to blindly guess the outcome.
