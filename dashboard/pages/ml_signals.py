# dashboard/pages/ml_signals.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import streamlit as st
import json, pandas as pd
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
ML_STATE = _ROOT / "portfolio/data/ml_state.json"

st.header("ML Signals")
st.caption("Walk-forward validated ML models (LR, RF, XGBoost) trained on 10 years of price + macro data.")

if not ML_STATE.exists():
    st.warning("No ML state found. Run: `python run_ml_pipeline.py` in `stock_ml_lab/`")
    st.stop()

with open(ML_STATE) as f:
    s = json.load(f)

st.caption(f"Generated at: {s.get('generated_at', '—')}")

# ── Ensemble verdict ───────────────────────────────────────────────────────────
ens = s.get("ensemble", {})
verdict = ens.get("verdict", "UNKNOWN")
score   = ens.get("weighted_score", 0)
VERDICT_COLOR = {"BULLISH": "🟢", "MIXED": "🟡", "BEARISH": "🔴"}.get(verdict, "⚪")

col1, col2, col3 = st.columns(3)
col1.metric("Ensemble Verdict",  f"{VERDICT_COLOR} {verdict}")
col2.metric("Weighted Score",    f"{score:.3f}", help="0=fully bearish, 1=fully bullish, 0.5=neutral")
col3.metric("Tickers Covered",   ens.get("n_tickers", 0))

st.divider()

# ── Per-ticker signals ────────────────────────────────────────────────────────
st.subheader("Per-Ticker Signals (21-day horizon)")
signals = s.get("model_signals", {})
if signals:
    rows = []
    for ticker, sig in sorted(signals.items()):
        up_p = sig.get("up_proba_21d", 0.5)
        auc  = sig.get("auc", 0.5)
        if up_p >= 0.65:   action = "🟢 BUY"
        elif up_p >= 0.55: action = "🟡 LEAN BUY"
        elif up_p <= 0.35: action = "🔴 SELL"
        elif up_p <= 0.45: action = "🟠 LEAN SELL"
        else:              action = "⚪ NEUTRAL"
        rows.append({
            "Ticker":        ticker,
            "Sector":        sig.get("sector", "—"),
            "21d Up Proba":  f"{up_p:.1%}",
            "AUC":           f"{auc:.4f}",
            "Signal":        action,
            "Last Price":    f"${sig.get('last_price', 0):.2f}",
            "Ann. Vol":      f"{sig.get('vol_ann', 0):.1%}",
            "Gate":          "✅ PASS" if auc >= 0.53 else "⛔ GATED",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ── Model comparison table ────────────────────────────────────────────────────
st.subheader("Model Performance (avg across tickers, walk-forward)")
mc = s.get("model_comparison", [])
if mc:
    df_mc = pd.DataFrame(mc)
    df_mc["acc"]    = (df_mc["acc"] * 100).round(1).astype(str) + "%"
    df_mc["auc"]    = df_mc["auc"].round(4)
    df_mc["beats"]  = df_mc["beats"].map({True: "✅ YES", False: "❌ NO"})
    df_mc = df_mc.rename(columns={"model":"Model","acc":"Accuracy","auc":"AUC",
                                   "sharpe":"Sharpe","dd":"Max DD","beats":"Beats Baseline?"})
    st.dataframe(df_mc, use_container_width=True, hide_index=True)

st.divider()

# ── Feature importance ────────────────────────────────────────────────────────
st.subheader("Top Feature Importances (RandomForest)")
fi = s.get("feature_importance", [])
if fi:
    df_fi = pd.DataFrame(fi[:12])
    df_fi["importance"] = (df_fi["importance"] * 100).round(2)
    st.bar_chart(df_fi.set_index("feature")["importance"])

st.divider()

# ── Experiment summary ────────────────────────────────────────────────────────
st.subheader("Experiment Summary")
es = s.get("experiment_summary", {})
c1, c2, c3, c4 = st.columns(4)
c1.metric("Best Model",    es.get("best_model", "—"))
c2.metric("Best AUC",      f"{es.get('best_auc', 0):.4f}")
c3.metric("Best Accuracy", f"{es.get('best_accuracy', 0):.1%}")
c4.metric("Beat Baseline", f"{es.get('beats_baseline_pct', 0):.0%} of models")
