tr_quant_engine/
│
├── data/                       # Where all CSV files live
│   ├── ledger.csv              # Your manual transaction history
│   ├── historical_prices.csv   # Cached Yahoo Finance data (saves API calls)
│   └── engine_state.json       # The algorithm's current target weights
│
├── src/                        # The Python Backend Code
│   ├── config.py               # Hard-coded rules (Tickers, €25 min trade, 2% risk-free rate)
│   ├── data_loader.py          # Connects to yfinance and reads your ledger
│   ├── math_optimizer.py       # Covariance, Volatility, and MPT calculations
│   ├── rules_engine.py         # Checks the 5% drift and Minimum Trade Size
│   └── app.py                  # The Streamlit Frontend / UI
│
├── docs/                       # System Documentation
│   ├── STRATEGY_RULES.md       # The financial logic
│   └── TUNING_LOG.md           # Your diary for algorithm adjustments
│
├── requirements.txt            # Python libraries (pandas, yfinance, streamlit, plotly)
└── run_engine.bat / .sh        # A one-click script to start the dashboard

