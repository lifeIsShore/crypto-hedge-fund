# dashboard/pages/risk_strategy.py
"""
Stream 4 — Risk/Strategy Page (Probabilistic View)

Ticker-by-ticker probabilistic price targets, Kelly sizing,
and portfolio-level VaR/CVaR via Monte Carlo simulation.
Data source: price_targets table (written by scheduler step 12).
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import streamlit as st
import pandas as pd
import numpy as np
import json
from sqlalchemy import text
from engine.db.db import get_session

st.set_page_config(layout="wide")
st.header("📊 Risk & Strategy — Probabilistic View")
st.caption("Price targets are lognormal medians. They will be wrong ~50% of the time. "
           "The value is in having an explicit, pre-committed exit plan.")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_targets():
    try:
        session = get_session()
        rows = session.execute(text("""
            SELECT ticker, current_price_eur, expected_21d_eur,
                   target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
                   resistance_ma50, resistance_ma200,
                   resistance_bb_upper, support_bb_lower,
                   high_52w, low_52w, risk_reward_ratio,
                   up_proba, vol_ann, computed_at
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
            ORDER BY ticker
        """)).fetchall()
        session.close()
        cols = [
            'ticker', 'current_price_eur', 'expected_21d_eur',
            'target_1sigma_eur', 'stop_1sigma_eur', 'stop_tight_eur',
            'resistance_ma50', 'resistance_ma200',
            'resistance_bb_upper', 'support_bb_lower',
            'high_52w', 'low_52w', 'risk_reward_ratio',
            'up_proba', 'vol_ann', 'computed_at',
        ]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.warning(f"Could not load price targets: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_positions():
    try:
        session = get_session()
        rows = session.execute(text("""
            SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
            FROM positions_history p
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date
                FROM positions_history GROUP BY ticker
            ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
        """)).fetchall()
        session.close()
        return pd.DataFrame(rows, columns=['ticker', 'quantity', 'price', 'value_eur', 'weight'])
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_regime():
    try:
        from shared.state_paths import REGIME_STATE_PATH
        if os.path.exists(REGIME_STATE_PATH):
            with open(REGIME_STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


df_targets  = load_targets()
df_positions = load_positions()
regime       = load_regime()

if df_targets.empty:
    st.info("No price targets found. Run the pipeline first: `python -m engine.scheduler`")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION A — GLOBAL TICKER SELECTOR + REGIME BANNER
# ─────────────────────────────────────────────────────────────────────────────

col_sel, col_reg = st.columns([2, 3])

with col_sel:
    ticker_list = sorted(df_targets['ticker'].tolist())
    selected = st.selectbox("Select Ticker", ticker_list, index=0)

with col_reg:
    if regime:
        risk_label   = regime.get('regime_risk', '—')
        rates_label  = regime.get('regime_rates', '—')
        growth_label = regime.get('regime_growth', '—')
        ew_flag      = regime.get('transition_warning', False)
        risk_color   = '🟢' if risk_label == 'Risk-On' else ('🔴' if risk_label == 'Risk-Off' else '🟡')
        st.info(
            f"**Macro Regime:** {risk_color} {risk_label} · {rates_label} · {growth_label}"
            + (" · ⚠️ **Transition Warning**" if ew_flag else "")
        )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# PER-TICKER VIEW
# ─────────────────────────────────────────────────────────────────────────────

row = df_targets[df_targets['ticker'] == selected].iloc[0]

cur   = float(row['current_price_eur'])
exp21 = float(row['expected_21d_eur'])
tgt   = float(row['target_1sigma_eur'])
stop  = float(row['stop_1sigma_eur'])
stp_t = float(row['stop_tight_eur'])
rr    = float(row['risk_reward_ratio'])
up_p  = float(row['up_proba'])
vol   = float(row['vol_ann'])
ma50  = row['resistance_ma50']
ma200 = row['resistance_ma200']
bb_u  = row['resistance_bb_upper']
bb_l  = row['support_bb_lower']
h52   = row['high_52w']
l52   = row['low_52w']

exp_pct = (exp21 - cur) / cur * 100 if cur > 0 else 0
upside  = (tgt  - cur) / cur * 100
downside = (cur - stop) / cur * 100

# Kelly fraction: f = (p*b - q) / b  where b = upside as decimal
b = (tgt - cur) / cur if cur > 0 else 0.0001
q = 1 - up_p
kelly_raw  = (up_p * b - q) / b if b > 0 else 0
kelly_half = max(0, min(kelly_raw / 2, 0.10))  # half-Kelly, capped at 10%

# ── Core metrics ─────────────────────────────────────────────────────────────
st.subheader(f"🎯 {selected} — Strategy Card")

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Current Price", f"€{cur:.2f}")
m2.metric("Expected 21d", f"€{exp21:.2f}", f"{exp_pct:+.1f}%")
m3.metric("Target (+1σ)",  f"€{tgt:.2f}",  f"+{upside:.1f}%")
m4.metric("Stop (-1σ)",    f"€{stop:.2f}", f"-{downside:.1f}%")
m5.metric("Risk/Reward",   f"{rr:.2f}x")
m6.metric("Half-Kelly",    f"{kelly_half*100:.1f}%",
          help="Recommended max position size (half-Kelly). Never exceed 10% on a single name.")

st.divider()

# ── Probability distribution (Monte Carlo) ───────────────────────────────────
col_chart, col_levels = st.columns([3, 2])

with col_chart:
    st.subheader("📈 Return Distribution (21d, 10,000 paths)")

    np.random.seed(42)
    n_sims = 10_000
    horizon = 21
    t = horizon / 252
    edge  = (up_p - 0.5) * 2
    drift = edge * vol * t
    sigma = vol * np.sqrt(t)

    # Lognormal Monte Carlo
    rand_returns = np.random.normal(drift, sigma, n_sims)
    sim_prices   = cur * np.exp(rand_returns)

    p_profit   = np.mean(sim_prices > cur) * 100
    p_up5      = np.mean(sim_prices > cur * 1.05) * 100
    p_down10   = np.mean(sim_prices < cur * 0.90) * 100
    var_5      = np.percentile(sim_prices, 5)
    var_1      = np.percentile(sim_prices, 1)
    cvar_5     = np.mean(sim_prices[sim_prices <= var_5])

    # Distribution chart using streamlit bar_chart
    bins = np.linspace(sim_prices.min(), sim_prices.max(), 60)
    hist, edges = np.histogram(sim_prices, bins=bins)
    bin_centers = (edges[:-1] + edges[1:]) / 2
    chart_df = pd.DataFrame({'Price (€)': bin_centers, 'Frequency': hist})
    st.bar_chart(chart_df.set_index('Price (€)'))

    c1, c2, c3 = st.columns(3)
    c1.metric("P(Profit > 0)",  f"{p_profit:.1f}%")
    c2.metric("P(Return > 5%)", f"{p_up5:.1f}%")
    c3.metric("P(Loss > 10%)",  f"{p_down10:.1f}%")

    st.caption(
        f"VaR(5%): €{var_5:.2f} | VaR(1%): €{var_1:.2f} | "
        f"CVaR(5%): €{cvar_5:.2f} (avg of worst 5% of outcomes)"
    )

with col_levels:
    st.subheader("📐 Price Levels")

    levels = [
        ("52w High",      h52,   "resistance"),
        ("BB Upper",      bb_u,  "resistance"),
        ("MA 200",        ma200, "resistance"),
        ("MA 50",         ma50,  "resistance"),
        ("Current",       cur,   "current"),
        ("Expected 21d",  exp21, "target"),
        ("Target (+1σ)",  tgt,   "target"),
        ("Tight Stop",    stp_t, "stop"),
        ("Stop (-1σ)",    stop,  "stop"),
        ("BB Lower",      bb_l,  "support"),
        ("52w Low",       l52,   "support"),
    ]

    level_rows = []
    for name, val, kind in sorted(levels, key=lambda x: x[1] or 0, reverse=True):
        if val is None:
            continue
        pct_from_cur = (val - cur) / cur * 100 if cur > 0 else 0
        icon = {'resistance': '🔴', 'current': '⚪', 'target': '🟢',
                'stop': '❌', 'support': '🔵'}.get(kind, '⚫')
        level_rows.append({
            'Level': f"{icon} {name}",
            'Price (€)': f"€{val:.2f}",
            'vs Current': f"{pct_from_cur:+.1f}%",
        })

    if level_rows:
        st.dataframe(pd.DataFrame(level_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.caption("**Buy zone:**")
    st.write(f"€{bb_l:.2f} — €{ma50:.2f}" if bb_l and ma50 else "Insufficient history")
    st.caption("**Target exit:**")
    st.write(f"€{tgt:.2f} (+{upside:.1f}%)")
    st.caption("**Hard stop-loss:**")
    st.write(f"€{stop:.2f} (-{downside:.1f}%)")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION D — FULL UNIVERSE TABLE
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("📋 Universe Risk/Reward Summary")

def _kelly_half(row):
    b_val = (row['target_1sigma_eur'] - row['current_price_eur']) / row['current_price_eur'] \
            if row['current_price_eur'] > 0 else 0.0001
    q_val = 1 - row['up_proba']
    k = (row['up_proba'] * b_val - q_val) / b_val if b_val > 0 else 0
    return round(max(0, min(k / 2, 0.10)) * 100, 1)

def _action(row):
    if row['up_proba'] >= 0.60:   return '🟢 BUY'
    elif row['up_proba'] >= 0.54: return '🟡 LEAN BUY'
    elif row['up_proba'] <= 0.40: return '🔴 SELL'
    elif row['up_proba'] <= 0.46: return '🟠 LEAN SELL'
    return '⚪ NEUTRAL'

summary_df = df_targets.copy()
summary_df['exp_pct']   = ((summary_df['expected_21d_eur'] - summary_df['current_price_eur'])
                            / summary_df['current_price_eur'] * 100).round(1)
summary_df['kelly_half'] = summary_df.apply(_kelly_half, axis=1)
summary_df['action']     = summary_df.apply(_action, axis=1)
summary_df['win_prob']   = (summary_df['up_proba'] * 100).round(1)
summary_df['rr_fmt']     = summary_df['risk_reward_ratio'].round(2)

display_cols = {
    'ticker':             'Ticker',
    'current_price_eur':  'Price €',
    'expected_21d_eur':   'Exp 21d €',
    'exp_pct':            'Exp %',
    'target_1sigma_eur':  'Target €',
    'stop_1sigma_eur':    'Stop €',
    'rr_fmt':             'R:R',
    'win_prob':           'Win %',
    'kelly_half':         'Kelly½ %',
    'action':             'Signal',
}

table = summary_df[list(display_cols.keys())].rename(columns=display_cols)
st.dataframe(table, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION E — PORTFOLIO-LEVEL RISK (Monte Carlo aggregated)
# ─────────────────────────────────────────────────────────────────────────────

if not df_positions.empty:
    st.subheader("🏦 Portfolio-Level Risk Distribution")

    merged = df_positions.merge(df_targets[['ticker','up_proba','vol_ann']], on='ticker', how='inner')

    if not merged.empty:
        total_val = float(df_positions['value_eur'].sum())
        np.random.seed(0)
        n_paths = 10_000

        port_sim = np.zeros(n_paths)
        for _, r in merged.iterrows():
            w     = float(r['weight'])
            u     = float(r['up_proba'])
            v     = float(r['vol_ann'])
            e     = (u - 0.5) * 2
            d_i   = e * v * t
            s_i   = v * np.sqrt(t)
            ret_i = np.random.normal(d_i, s_i, n_paths)
            port_sim += w * ret_i

        port_prices = total_val * np.exp(port_sim)
        port_var5   = np.percentile(port_sim, 5) * 100
        port_cvar5  = np.mean(port_sim[port_sim <= np.percentile(port_sim, 5)]) * 100
        port_var1   = np.percentile(port_sim, 1) * 100

        pv1, pv2, pv3, pv4 = st.columns(4)
        pv1.metric("Portfolio Value",    f"€{total_val:,.0f}")
        pv2.metric("VaR 95% (21d)",      f"{port_var5:.1f}%",
                   help="5% chance of losing more than this over 21 trading days")
        pv3.metric("CVaR 95% (21d)",     f"{port_cvar5:.1f}%",
                   help="Average loss in the worst 5% of scenarios")
        pv4.metric("VaR 99% (21d)",      f"{port_var1:.1f}%")

        bins_p = np.linspace(port_sim.min(), port_sim.max(), 60)
        hist_p, edges_p = np.histogram(port_sim, bins=bins_p)
        mid_p = (edges_p[:-1] + edges_p[1:]) / 2 * 100
        st.bar_chart(pd.DataFrame({'Portfolio Return %': mid_p, 'Frequency': hist_p})
                     .set_index('Portfolio Return %'))
    else:
        st.info("No overlapping data between positions and price targets yet.")
else:
    st.info("No positions found. Import your ledger by running the pipeline.")

st.caption(f"Data computed at: {df_targets['computed_at'].iloc[0] if not df_targets.empty else '—'}")
