# dashboard/pages/divergence_labeler.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from engine.db.db import get_session
from engine.screens.etf_divergence import apply_scenario_label

st.header("ETF divergence labeler")
st.caption("Label each divergence event. Your labels become ML training data.")

try:
    session = get_session()
    result = session.execute(text("""
        SELECT id, ticker, etf_reference, detected_at,
               etf_return_pct, stock_return_pct, divergence_pct, scenario_label
        FROM divergence_labels
        WHERE scenario_label IS NULL
        ORDER BY detected_at DESC
        LIMIT 20
    """))
    rows = result.fetchall()
    session.close()
except Exception as e:
    st.warning(f"Database not ready yet: {e}")
    rows = []

if not rows:
    st.success("No unlabeled divergence events.")
else:
    df = pd.DataFrame(rows, columns=["id", "ticker", "etf", "detected", "etf_ret", "stock_ret", "divergence", "label"])
    st.dataframe(df[["ticker", "etf", "detected", "etf_ret", "stock_ret", "divergence"]], hide_index=True)

    st.divider()
    st.subheader("Label a divergence")

    selected_id = st.selectbox("Select divergence ID", df["id"].tolist())
    selected = df[df["id"] == selected_id].iloc[0]
    st.write(f"**{selected['ticker']}** vs **{selected['etf']}** — detected {selected['detected']}")
    st.write(f"ETF return: **{selected['etf_ret']:.1%}** | Stock return: **{selected['stock_ret']:.1%}** | Divergence: **{selected['divergence']:.1%}**")

    st.markdown("""
    **Scenario guide:**
    - **1 — Temporary Rotation**: no bad news, capital rotating, ETF confirms macro. → Potential buy.
    - **2 — Stock-specific bad news**: identifiable catalyst, high volume, analyst downgrades. → Watch list.
    - **3 — Valuation compression**: prior large run, mean-reverting to fair value. → Wait.
    - **4 — Thesis break**: sustained divergence, insider selling, short interest rising. → Avoid / exit.
    """)

    scenario    = st.radio("Scenario", [1, 2, 3, 4], horizontal=True)
    confidence  = st.select_slider("Confidence", ["low", "medium", "high"])
    notes       = st.text_area("Notes (what are you seeing?)")

    checklist = {
        "negative_news":     st.checkbox("Is there identifiable negative news?"),
        "prior_large_run":   st.checkbox("Did the stock have a large prior run (>50%)?"),
        "divergence_weeks":  st.checkbox("Has divergence lasted more than 2 weeks?"),
        "peers_weak":        st.checkbox("Are peers in same sub-industry also quietly weak?"),
        "short_int_rising":  st.checkbox("Is short interest rising or insider selling present?"),
    }

    if st.button("Save label", type="primary"):
        apply_scenario_label(selected_id, scenario, confidence, notes, checklist)
        st.success(f"Scenario {scenario} saved for {selected['ticker']}")
        st.rerun()
