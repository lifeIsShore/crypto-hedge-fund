# dashboard/pages/regime.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import streamlit as st
import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
REGIME_STATE = _ROOT / "ml_quant_finance_research/quant_research/regime_engine/data/regime_state.json"

st.header("Macro Regime")
st.caption("Current market regime derived from VIX, yield curve, HY spreads, and Fed Funds.")

if not REGIME_STATE.exists():
    st.warning("No regime state found. Run the regime engine first: `python run_engine.py` in `regime_engine/`")
    st.stop()

with open(REGIME_STATE) as f:
    s = json.load(f)

# ── Top KPIs ──────────────────────────────────────────────────────────────────
st.subheader(f"Snapshot — {s['as_of_date']}")

RISK_COLOR  = {"Risk-On": "🟢", "Neutral": "🟡", "Risk-Off": "🔴"}.get(s['regime_risk'],  "⚪")
RATE_COLOR  = {"Easing":  "🟢", "Neutral": "🟡", "Tightening": "🔴"}.get(s['regime_rates'], "⚪")
GROW_COLOR  = {"Expansion": "🟢", "Recovery": "🟢", "Slowdown": "🟡", "Contraction": "🔴"}.get(s['regime_growth'], "⚪")
EW_COLOR    = "🔴" if s['transition_warning'] else "🟢"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Risk Appetite",    f"{RISK_COLOR} {s['regime_risk']}")
col2.metric("Rate Environment", f"{RATE_COLOR} {s['regime_rates']}")
col3.metric("Growth Cycle",     f"{GROW_COLOR} {s['regime_growth']}")
col4.metric("Early Warnings",   f"{EW_COLOR} {s['ew_active_count']}/4 triggers")

if s['transition_warning']:
    st.error("⚠️ Regime transition warning active — multiple stress indicators firing simultaneously.")
else:
    st.success(f"Regime stable: **{s['regime_composite']}** — {s['current_streak_days']} consecutive days")

st.divider()

# ── Macro snapshot ────────────────────────────────────────────────────────────
st.subheader("Live Macro Inputs")
m = s['macro_snapshot']
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("VIX",           f"{m['vix']:.2f}",   help="<20 = calm, >30 = stressed")
c2.metric("10Y-2Y Spread", f"{m['yield_spread']:+.2f}%", help=">0 = normal, <0 = inverted (recession signal)")
c3.metric("HY Spread",     f"{m['hy_spread']:.2f}%", help="<3% = tight credit (risk-on), >5% = stress")
c4.metric("IG Spread",     f"{m['ig_spread']:.2f}%")
c5.metric("Fed Funds",     f"{m['fed_funds']:.2f}%")

st.divider()

# ── Regime distribution ───────────────────────────────────────────────────────
st.subheader("Historical Regime Distribution (last 2 years)")
dist = s['regime_distribution']
import pandas as pd
df_dist = pd.DataFrame([{"Regime": k, "% of Days": v} for k, v in sorted(dist.items(), key=lambda x: -x[1])])
st.bar_chart(df_dist.set_index("Regime"))

st.divider()

# ── Early warning flags ───────────────────────────────────────────────────────
st.subheader("Early Warning Flags")
ew = s['ew_flags']
cols = st.columns(4)
flags = [
    ("VIX Rising",          ew.get('vix_rising',       False), "VIX spiking from calm into stress zone"),
    ("Curve Flattening",    ew.get('curve_flattening',  False), "Yield curve flattening rapidly"),
    ("HY Widening",         ew.get('hy_widening',       False), "High-yield spreads widening sharply"),
    ("Rate Repricing",      ew.get('rate_reprice',      False), "Fed funds rate repricing significantly"),
]
for col, (name, active, desc) in zip(cols, flags):
    col.metric(name, "🔴 ACTIVE" if active else "✅ Clear", help=desc)

# ── Signal guidance ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Signal Reliability in Current Regime")
GUIDANCE = {
    ("Expansion",   "Risk-On"):  {"Laggard Screen": "HIGH",  "PEAD":  "HIGH",  "Short Squeeze": "HIGH",  "Corr Break": "HIGH"},
    ("Expansion",   "Neutral"):  {"Laggard Screen": "HIGH",  "PEAD":  "HIGH",  "Short Squeeze": "MED",   "Corr Break": "HIGH"},
    ("Slowdown",    "Neutral"):  {"Laggard Screen": "MOD",   "PEAD":  "MOD",   "Short Squeeze": "MED",   "Corr Break": "AVOID"},
    ("Slowdown",    "Risk-On"):  {"Laggard Screen": "MOD",   "PEAD":  "HIGH",  "Short Squeeze": "MED",   "Corr Break": "MOD"},
    ("Slowdown",    "Risk-Off"): {"Laggard Screen": "LOW",   "PEAD":  "LOW",   "Short Squeeze": "AVOID", "Corr Break": "AVOID"},
    ("Contraction", "Risk-Off"): {"Laggard Screen": "AVOID", "PEAD":  "LOW",   "Short Squeeze": "AVOID", "Corr Break": "AVOID"},
    ("Recovery",    "Risk-On"):  {"Laggard Screen": "HIGH",  "PEAD":  "MOD",   "Short Squeeze": "HIGH",  "Corr Break": "HIGH"},
    ("Recovery",    "Neutral"):  {"Laggard Screen": "HIGH",  "PEAD":  "MOD",   "Short Squeeze": "MOD",   "Corr Break": "MOD"},
}
COLOR = {"HIGH": "🟢", "MOD": "🟡", "MED": "🟡", "LOW": "🔴", "AVOID": "⛔", "UNKNOWN": "❓"}
guidance = GUIDANCE.get((s['regime_growth'], s['regime_risk']),
                        {k: "UNKNOWN" for k in ["Laggard Screen","PEAD","Short Squeeze","Corr Break"]})
gcols = st.columns(4)
for col, (tech, rel) in zip(gcols, guidance.items()):
    col.metric(tech, f"{COLOR.get(rel,'❓')} {rel}")
