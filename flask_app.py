"""
flask_app.py — Hedge Fund Control Tower (Stream 6: Flask rewrite)
=================================================================
Single entry point.  Run:
    python flask_app.py
Then open http://localhost:5000

All data is read from:
  - engine_data.db  (SQLite via SQLAlchemy)
  - shared/state/*.json (ML state, regime, PEAD)

No Streamlit dependency.  Streamlit pages still exist as a fallback.
"""

import sys, os, json, logging
from pathlib import Path
from datetime import datetime, date
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from flask import Flask, render_template, jsonify, request, abort
from sqlalchemy import text
from engine.db.db import get_session
from shared.state_paths import (
    ML_STATE_PATH, REGIME_STATE_PATH,
    PEAD_STATE_PATH, PEAD_SETUPS_PATH,
    state_file_ages,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path):
    """Load a JSON state file; return {} on any error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _q(sql, params=None):
    """Execute a read query and return list-of-dicts."""
    session = get_session()
    try:
        result = session.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]
    except Exception as e:
        log.warning(f"Query failed: {e}")
        return []
    finally:
        session.close()


def _exec(sql, params=None):
    """Execute a write statement."""
    session = get_session()
    try:
        session.execute(text(sql), params or {})
        session.commit()
        return True
    except Exception as e:
        log.warning(f"Write failed: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def _mc_portfolio(positions, targets_map, n_paths=8000):
    """Run Monte Carlo on portfolio; return (var5_pct, cvar5_pct, var1_pct, total_eur)."""
    total = sum(float(p.get("value_eur", 0)) for p in positions)
    if total <= 0:
        return 0, 0, 0, 0
    port_ret = np.zeros(n_paths)
    t = 21 / 252
    rng = np.random.default_rng(seed=0)
    for p in positions:
        ticker = p["ticker"]
        w = float(p.get("weight", 0))
        sig = targets_map.get(ticker, {})
        up_p = float(sig.get("up_proba", 0.5))
        vol  = float(sig.get("vol_ann", 0.25))
        edge = (up_p - 0.5) * 2
        dr   = edge * vol * t
        sr   = vol * np.sqrt(t)
        port_ret += w * rng.normal(dr, sr, n_paths)
    var5  = float(np.percentile(port_ret, 5)  * 100)
    var1  = float(np.percentile(port_ret, 1)  * 100)
    cvar5 = float(np.mean(port_ret[port_ret <= np.percentile(port_ret, 5)]) * 100)
    return round(var5, 2), round(cvar5, 2), round(var1, 2), round(total, 2)


def _run_scheduled_rebalance():
    """Background task to refresh the portfolio engine weekly."""
    try:
        log.info("⏰ [SCHEDULED REFRESH] Starting weekly portfolio rebalance...")
        res = subprocess.run([sys.executable, str(ROOT / "portfolio" / "recalculate_engine.py")], 
                             capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            log.info("✅ [SCHEDULED REFRESH] Weekly rebalance successful.")
        else:
            log.error(f"❌ [SCHEDULED REFRESH] Rebalance failed: {res.stderr}")
    except Exception as e:
        log.error(f"❌ [SCHEDULED REFRESH] Error: {e}")


def start_scheduler():
    """Initialize the background task manager."""
    scheduler = BackgroundScheduler()
    # Monday at 17:00 CET
    scheduler.add_job(
        func=_run_scheduled_rebalance,
        trigger="cron",
        day_of_week=0,
        hour=17,
        minute=0,
        timezone="Europe/Berlin",
        id="weekly_refresh"
    )
    scheduler.start()
    log.info("⏱️  Scheduler active: Weekly refresh set for Monday 17:00 CET")
    return scheduler


# ─────────────────────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def overview():
    # Positions
    positions = _q("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
        ORDER BY p.value_eur DESC
    """)

    # Cash (latest row)
    cash_rows = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
    cash_eur = float(cash_rows[0]["cash_eur"]) if cash_rows else 0.0

    total_eur = sum(float(p["value_eur"]) for p in positions) + cash_eur

    # Trade advisor diff
    trade_advice = _q("""
        SELECT m.ticker, m.current_weight, m.suggested_weight, m.delta_weight, m.bl_return
        FROM model_outputs m
        WHERE m.date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY ABS(m.delta_weight) DESC
    """)

    # Pipeline health (last 14 runs)
    pipeline = _q("""
        SELECT step_name, status, duration_sec, run_date
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 14
    """)

    # Risk events (last 5)
    risk_events = _q("""
        SELECT date, event_type, ticker, detail
        FROM risk_events
        ORDER BY logged_at DESC
        LIMIT 5
    """)

    # State file freshness
    ages = state_file_ages()

    # Regime banner
    regime = _load_json(REGIME_STATE_PATH)

    return render_template("overview.html",
        positions=positions,
        cash_eur=cash_eur,
        total_eur=total_eur,
        trade_advice=trade_advice,
        pipeline=pipeline,
        risk_events=risk_events,
        ages=ages,
        regime=regime,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/risk")
def risk():
    targets = _q("""
        SELECT ticker, current_price_eur, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
               resistance_ma50, resistance_ma200,
               resistance_bb_upper, support_bb_lower,
               high_52w, low_52w, risk_reward_ratio,
               up_proba, vol_ann, computed_at
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
        ORDER BY ticker
    """)

    positions = _q("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
    """)

    regime = _load_json(REGIME_STATE_PATH)

    # Portfolio MC
    targets_map = {t["ticker"]: t for t in targets}
    var5, cvar5, var1, total_eur = _mc_portfolio(positions, targets_map)

    return render_template("risk.html",
        targets=targets,
        positions=positions,
        regime=regime,
        port_var5=var5,
        port_cvar5=cvar5,
        port_var1=var1,
        port_total=total_eur,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/research")
def research():
    ml  = _load_json(ML_STATE_PATH)
    reg = _load_json(REGIME_STATE_PATH)
    ages = state_file_ages()
    return render_template("research.html",
        ml=ml,
        regime=reg,
        ages=ages,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/rebalance")
def rebalance():
    today = str(date.today())
    rows = _q("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return
        FROM model_outputs
        WHERE date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY ABS(delta_weight) DESC
    """)
    overrides = _q("""
        SELECT date, ticker, model_suggestion, action_taken, reason
        FROM override_log
        ORDER BY logged_at DESC
        LIMIT 20
    """)
    return render_template("rebalance.html",
        rows=rows,
        overrides=overrides,
        today=today,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/pead")
def pead():
    state = _load_json(PEAD_STATE_PATH)

    # Try SQLite first; fall back to CSV
    history = _q("""
        SELECT ticker, earnings_date, direction, pead_setup_quality,
               surprise_pct, drift_21d, outcome_label_correct, regime_composite
        FROM pead_setups
        ORDER BY earnings_date DESC
        LIMIT 60
    """)
    if not history and PEAD_SETUPS_PATH and Path(PEAD_SETUPS_PATH).exists():
        import csv
        with open(PEAD_SETUPS_PATH, newline="") as f:
            reader = csv.DictReader(f)
            history = list(reader)[:60]

    return render_template("pead.html",
        state=state,
        history=history,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/labels")
def labels():
    rows = _q("""
        SELECT id, ticker, etf_reference, detected_at,
               etf_return_pct, stock_return_pct, divergence_pct, scenario_label
        FROM divergence_labels
        WHERE scenario_label IS NULL
        ORDER BY detected_at DESC
        LIMIT 30
    """)
    return render_template("labels.html",
        rows=rows,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# JSON APIS  (consumed by Chart.js / DataTables on the frontend)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/price_targets")
def api_price_targets():
    data = _q("""
        SELECT ticker, current_price_eur, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
               resistance_ma50, resistance_ma200,
               resistance_bb_upper, support_bb_lower,
               high_52w, low_52w, risk_reward_ratio,
               up_proba, vol_ann, computed_at
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
        ORDER BY ticker
    """)
    return jsonify(data)


@app.route("/api/ticker_mc/<ticker>")
def api_ticker_mc(ticker):
    """Return Monte Carlo histogram + stats for one ticker."""
    rows = _q("""
        SELECT up_proba, vol_ann, current_price_eur
        FROM price_targets
        WHERE ticker = :t
        AND date = (SELECT MAX(date) FROM price_targets WHERE ticker = :t)
    """, {"t": ticker})
    if not rows:
        return jsonify({"error": "not found"}), 404

    r = rows[0]
    cur   = float(r["current_price_eur"] or 0)
    up_p  = float(r["up_proba"] or 0.5)
    vol   = float(r["vol_ann"] or 0.25)
    t_val = 21 / 252
    edge  = (up_p - 0.5) * 2
    drift = edge * vol * t_val
    sigma = vol * np.sqrt(t_val)

    rng = np.random.default_rng(42)
    n   = 10_000
    sim_ret = rng.normal(drift, sigma, n)
    sim_prices = cur * np.exp(sim_ret)

    bins = np.linspace(sim_prices.min(), sim_prices.max(), 50)
    hist, edges = np.histogram(sim_prices, bins=bins)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()

    var5  = float(np.percentile(sim_prices, 5))
    var1  = float(np.percentile(sim_prices, 1))
    cvar5 = float(np.mean(sim_prices[sim_prices <= var5]))
    p_profit = float(np.mean(sim_prices > cur) * 100)
    p_up5    = float(np.mean(sim_prices > cur * 1.05) * 100)
    p_down10 = float(np.mean(sim_prices < cur * 0.90) * 100)

    return jsonify({
        "ticker":    ticker,
        "labels":    [round(c, 2) for c in centers],
        "counts":    hist.tolist(),
        "cur":       round(cur, 2),
        "var5":      round(var5, 2),
        "var1":      round(var1, 2),
        "cvar5":     round(cvar5, 2),
        "p_profit":  round(p_profit, 1),
        "p_up5":     round(p_up5, 1),
        "p_down10":  round(p_down10, 1),
    })


@app.route("/api/ml_signals")
def api_ml_signals():
    ml = _load_json(ML_STATE_PATH)
    return jsonify({
        "ensemble":           ml.get("ensemble", {}),
        "model_signals":      ml.get("model_signals", {}),
        "experiment_summary": ml.get("experiment_summary", {}),
        "model_comparison":   ml.get("model_comparison", []),
        "feature_importance": ml.get("feature_importance", []),
        "generated_at":       ml.get("generated_at", ""),
    })


@app.route("/api/regime")
def api_regime():
    return jsonify(_load_json(REGIME_STATE_PATH))


@app.route("/api/portfolio_mc")
def api_portfolio_mc():
    positions = _q("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
    """)
    targets = _q("""
        SELECT ticker, up_proba, vol_ann
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
    """)
    targets_map = {t["ticker"]: t for t in targets}

    total = sum(float(p.get("value_eur", 0)) for p in positions)
    if total <= 0:
        return jsonify({"error": "no positions"}), 404

    n_paths = 8000
    port_ret = np.zeros(n_paths)
    rng = np.random.default_rng(0)
    t_val = 21 / 252

    for p in positions:
        w    = float(p.get("weight", 0))
        sig  = targets_map.get(p["ticker"], {})
        up_p = float(sig.get("up_proba", 0.5))
        vol  = float(sig.get("vol_ann", 0.25))
        edge = (up_p - 0.5) * 2
        dr   = edge * vol * t_val
        sr   = vol * np.sqrt(t_val)
        port_ret += w * rng.normal(dr, sr, n_paths)

    bins = np.linspace(port_ret.min(), port_ret.max(), 50)
    hist, edges = np.histogram(port_ret, bins=bins)
    centers = ((edges[:-1] + edges[1:]) / 2 * 100).tolist()

    return jsonify({
        "labels":     [round(c, 2) for c in centers],
        "counts":     hist.tolist(),
        "var5_pct":   round(float(np.percentile(port_ret, 5))  * 100, 2),
        "var1_pct":   round(float(np.percentile(port_ret, 1))  * 100, 2),
        "cvar5_pct":  round(float(np.mean(port_ret[port_ret <= np.percentile(port_ret, 5)])) * 100, 2),
        "total_eur":  round(total, 2),
    })


@app.route("/api/pipeline_status")
def api_pipeline_status():
    rows = _q("""
        SELECT step_name, status, duration_sec, run_date, started_at
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 30
    """)
    ages = state_file_ages()
    return jsonify({"steps": rows, "state_ages": ages})


@app.route("/api/override", methods=["POST"])
def api_override():
    data = request.get_json()
    ok = _exec("""
        INSERT INTO override_log (date, ticker, model_suggestion, action_taken, reason)
        VALUES (CURRENT_DATE, :ticker, :suggestion, :action, :reason)
    """, {
        "ticker":     data.get("ticker"),
        "suggestion": float(data.get("suggestion", 0)),
        "action":     float(data.get("action", 0)),
        "reason":     data.get("reason", ""),
    })
    return jsonify({"ok": ok})


@app.route("/api/label", methods=["POST"])
def api_label():
    data = request.get_json()
    ok = _exec("""
        UPDATE divergence_labels
        SET scenario_label = :scenario,
            confidence     = :confidence,
            notes          = :notes,
            checklist_answers = :checklist,
            labeled_at     = datetime('now')
        WHERE id = :id
    """, {
        "id":         int(data.get("id")),
        "scenario":   int(data.get("scenario")),
        "confidence": data.get("confidence", "medium"),
        "notes":      data.get("notes", ""),
        "checklist":  json.dumps(data.get("checklist", {})),
    })
    return jsonify({"ok": ok})


@app.route("/health")
def health():
    pipeline = _q("""
        SELECT step_name, status, duration_sec, run_date, started_at, error_msg
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 50
    """)
    risk_events = _q("""
        SELECT date, event_type, ticker, detail, logged_at
        FROM risk_events
        ORDER BY logged_at DESC
        LIMIT 20
    """)
    ages = state_file_ages()
    return render_template("health.html",
        pipeline=pipeline,
        risk_events=risk_events,
        ages=ages,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_scheduler()
    log.info("Control Tower (Flask) starting — http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
