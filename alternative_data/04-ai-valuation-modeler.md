# 04 - The "AI Valuation Modeler & Strategic Reader"

## Concept
This is a hybrid fundamental-AI agent. It automatically builds a classic Discounted Cash Flow (DCF) model to find a stock's "intrinsic fair value", while simultaneously reading the forward-looking statements to extract categorical strategic pivots. 

This creates a highly objective long-term fundamental anchor that perfectly complements the short-term tactical momentum of the 21-day ML model.

## Data Sources
- **SEC EDGAR:** For 10-K and 10-Q filings.
- **Investor Relations (IR) Websites:** For investor presentations and supplementary financial tables.
- **Treasury Yield APIs:** For the Risk-Free Rate used in the WACC calculation.

## Core Features to Extract

### 1. Automated DCF Fair Value Output
- **Mechanism:** The agent autonomously downloads the latest financial statements and extracts the raw fundamental inputs: Free Cash Flow (FCF), Shares Outstanding, Total Debt, Cash and Equivalents.
- **LLM Task:** The LLM reads the management's guidance to extract the projected revenue/FCF growth rate for the next 1-3 years.
- **Math Engine:** A Python script calculates the Weighted Average Cost of Capital (WACC), projects the FCF for 5 years using the LLM's extracted growth rate, applies a terminal multiple, and discounts it back to present value.
- **Output:** `dcf_fair_value_price` (Float) and `dcf_upside_pct` (Float). If `dcf_upside_pct > 0.30` and the ML model signals a BUY, it creates a massive high-conviction trade.

### 2. Strategic "Verbal Signals"
- **Mechanism:** While processing the report, the agent specifically scans the "Strategic Initiatives" or "Forward-Looking Statements" sections.
- **LLM Task:** "Identify if the company is executing a strategic pivot, initiating heavy R&D/CapEx, or pausing share buybacks. Return boolean flags."
- **Output:** Categorical features such as `strategic_pivot=True` or `heavy_capex_cycle=True`.

## Architecture Pipeline
1. **Trigger:** Runs quarterly as soon as a company releases its 10-Q/10-K.
2. **Extraction:** PyPDF2 or Unstructured.io is used to parse the financial tables from the PDF.
3. **Calculation:** A strict deterministic Python class `DCFModeler` takes the extracted inputs and computes the math (to prevent LLM hallucination on math).
4. **Integration:** The `dcf_upside_pct` is appended to the feature matrix as a highly predictive fundamental anchor.
