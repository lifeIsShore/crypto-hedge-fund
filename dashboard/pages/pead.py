# dashboard/pages/pead.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import streamlit as st
import json, pandas as pd
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
PEAD_STATE = _ROOT / "ml_quant_finance_research/quant_research/pead_engine/data/pead_state.json"
PEAD_CSV   = _ROOT / "ml_quant_finance_research/quant_research/pead_engine/data/pead_setups.csv"

st.header("PEAD Setups")
st.caption("Post-Earnings Announcement Drift — earnings surprises that the market hasn't fully priced in yet.")

if not PEAD_STATE.exists():
    st.warning("No PEAD state found. Run: `python run_engine.py` in `pead_engine/`")
    st.stop()

with open(PEAD_STATE) as f:
    s = json.load(f)

# ── Performance KPIs ──────────────────────────────────────────────────────────
perf = s.get("performance", {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Setups (all-time)",  perf.get("total_setups", 0))
col2.metric("21d Hit Rate",   f"{perf.get('overall_hit_rate_21d', 0)*100:.1f}%" if perf.get('overall_hit_rate_21d') else "—",
            help="% of setups where stock drifted in predicted direction 21 days later")
col3.metric("Avg 21d Drift",  f"{perf.get('overall_avg_drift_21d', 0):+.2f}%" if perf.get('overall_avg_drift_21d') else "—")
col4.metric("Active Setups",  len(s.get("active_setups", [])))

st.divider()

# ── Active setups (entry window open today) ───────────────────────────────────
active = s.get("active_setups", [])
st.subheader(f"Active Entry Window ({len(active)} setups)")
if not active:
    st.info("No setups in entry window today. New signals appear within 3 days after earnings.")
else:
    rows = []
    for setup in active:
        direction_icon = "🟢 BULL" if setup.get("direction") == "bullish" else "🔴 BEAR"
        quality_color  = "🔥" if setup.get("quality") == "HIGH" else ("⭐" if setup.get("quality") == "MEDIUM" else "")
        rows.append({
            "Ticker":       setup["ticker"],
            "Direction":    direction_icon,
            "Quality":      f"{quality_color} {setup.get('quality', '')}",
            "Surprise %":   f"{setup.get('surprise_pct', 0):+.1f}%",
            "Entry Date":   setup.get("entry_date", ""),
            "Drift Window": f"{setup.get('drift_window', 21)}d",
            "Underreaction": "⚠️ YES" if setup.get("underreaction") else "No",
            "Regime":       setup.get("regime_composite", "—"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ── Historical setups table ───────────────────────────────────────────────────
st.subheader("All Historical Setups")
if PEAD_CSV.exists():
    df = pd.read_csv(PEAD_CSV)
    # Show key cols
    show_cols = [c for c in ["earnings_date","ticker","direction","quality","surprise_pct",
                              "drift_21d","hit_21d","regime_composite"] if c in df.columns]
    df_show = df[show_cols].sort_values("earnings_date", ascending=False).head(50)

    # Color the direction column
    def style_row(row):
        color = "#d4edda" if row.get("direction") == "bullish" else "#f8d7da"
        return [f"background-color: {color}"] * len(row)

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Hit rate by regime
    if "regime_composite" in df.columns and "hit_21d" in df.columns:
        st.divider()
        st.subheader("Hit Rate by Regime")
        regime_perf = df[df["hit_21d"].notna()].groupby("regime_composite").agg(
            Setups=("hit_21d", "count"),
            HitRate=("hit_21d", "mean"),
            AvgDrift=("drift_21d", "mean")
        ).reset_index()
        regime_perf["HitRate"] = (regime_perf["HitRate"] * 100).round(1).astype(str) + "%"
        regime_perf["AvgDrift"] = regime_perf["AvgDrift"].round(2).astype(str) + "%"
        st.dataframe(regime_perf, use_container_width=True, hide_index=True)
else:
    st.info("No historical CSV found yet.")
