# dashboard/app.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

st.set_page_config(
    page_title="Hedge Fund Control Tower",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Control Tower")
st.caption("Decision support — you make the final call")

pages = {
    "Portfolio Overview":        "dashboard/pages/overview.py",
    "Rebalance Suggestions":     "dashboard/pages/rebalance.py",
    "Risk & Strategy":           "dashboard/pages/risk_strategy.py",   # Stream 4
    "Risk Dashboard":            "dashboard/pages/risk.py",
    "Model Health":              "dashboard/pages/models.py",
    "ML Signals":                "dashboard/pages/ml_signals.py",
    "Macro Regime":              "dashboard/pages/regime.py",
    "PEAD Setups":               "dashboard/pages/pead.py",
    "Laggard Screen":            "dashboard/pages/screens.py",
    "ETF Divergence Labeler":    "dashboard/pages/divergence_labeler.py",
}

# Run via: streamlit run dashboard/app.py
