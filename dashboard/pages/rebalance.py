# dashboard/pages/rebalance.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
import datetime

st.header("Rebalance suggestions")

today = str(datetime.date.today())

try:
    session = get_session()
    result = session.execute(text("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return
        FROM model_outputs
        WHERE date = :date
        ORDER BY ABS(delta_weight) DESC
    """), {"date": today})
    rows = result.fetchall()
    session.close()
except Exception as e:
    st.warning(f"Database not ready yet: {e}")
    rows = []

if not rows:
    st.info("No model outputs for today — run the daily pipeline first.")
else:
    df = pd.DataFrame(rows, columns=["Ticker", "Current %", "Suggested %", "Δ Weight", "BL Return"])
    df["Current %"]   = (df["Current %"] * 100).round(2)
    df["Suggested %"] = (df["Suggested %"] * 100).round(2)
    df["Δ Weight"]    = (df["Δ Weight"] * 100).round(2)
    df["BL Return"]   = (df["BL Return"] * 100).round(2)

    df["Action"] = df["Δ Weight"].apply(
        lambda x: "🟢 BUY" if x > 0.5 else ("🔴 SELL" if x < -0.5 else "✅ HOLD")
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Log an override")
    col1, col2, col3 = st.columns(3)
    with col1:
        ov_ticker = st.selectbox("Ticker", df["Ticker"].tolist())
    with col2:
        ov_action = st.number_input("Weight you're actually setting (%)", min_value=0.0, max_value=100.0, step=0.5)
    with col3:
        ov_reason = st.text_input("Reason")

    if st.button("Log override"):
        model_suggestion = float(df[df["Ticker"] == ov_ticker]["Suggested %"].values[0]) / 100
        session = get_session()
        session.execute(text("""
            INSERT INTO override_log (date, ticker, model_suggestion, action_taken, reason)
            VALUES (CURRENT_DATE, :ticker, :suggestion, :action, :reason)
        """), {"ticker": ov_ticker, "suggestion": model_suggestion,
               "action": ov_action / 100, "reason": ov_reason})
        session.commit()
        session.close()
        st.success(f"Override logged for {ov_ticker}")
