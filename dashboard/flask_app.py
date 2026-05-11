"""
dashboard/flask_app.py
======================
Flask Control Tower — replaces Streamlit entirely.

Routes:
    GET  /                  Portfolio overview
    GET  /risk              Risk & Strategy (Monte Carlo, price targets)
    GET  /research          ML signals + PEAD setups
    GET  /regime            Macro regime
    GET  /rebalance         BL rebalance suggestions + override log
    GET  /divergence        ETF divergence labeler
    GET  /health            Pipeline health & data freshness

API (JSON):
    GET  /api/positions     Latest positions from DB
    GET  /api/targets       Latest price targets from DB
    GET  /api/ml            ml_state.json payload
    GET  /api/regime        regime_state.json payload
    GET  /api/pead          pead_state.json payload
    GET  /api/rebalance     model_outputs from DB
    GET  /api/pipeline      pipeline_runs last 7 days
    GET  /api/divergence    unlabeled divergence_labels rows
    GET  /api/cash          latest cash_history row
    GET  /api/trades        last 30 trades
    GET  /api/freshness     age of each shared/state file
    POST /api/override      log a weight override
    POST /api/label         save a divergence label

Run:
    python dashboard/flask_app.py
    # or via: flask --app dashboard/flask_app.py run --port 5050
"""

import os, sys, json, logging
from pathlib import Path
from datetime import datetime, date
import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from flask import Flask, render_template, jsonify, request, abort
from sqlalchemy import text

# Engine imports (graceful degradation if DB not ready)
try:
    from engine.db.db import get_session
    DB_AVAILABLE = True
except Exception as e:
    DB_AVAILABLE = False
    logging.warning(f"DB not available: {e}")

# Shared state paths
try:
    from shared.state_paths import (
        ML_STATE_PATH, PEAD_STATE_PATH, PEAD_SETUPS_PATH,
        REGIME_STATE_PATH, REGIME_HISTORY_PATH,
        FACTOR_STATE_PATH, CORRELATION_STATE_PATH,
        state_file_ages,
    )
except Exception:
    ML_STATE_PATH       = str(_ROOT / "shared/state/ml_state.json")
    PEAD_STATE_PATH     = str(_ROOT / "shared/state/pead_state.json")
    PEAD_SETUPS_PATH    = str(_ROOT / "shared/state/pead_setups.csv")
    REGIME_STATE_PATH   = str(_ROOT / "shared/state/regime_state.json")
    REGIME_HISTORY_PATH = str(_ROOT / "shared/state/regime_history.csv")
    FACTOR_STATE_PATH   = str(_ROOT / "shared/state/factor_state.json")
    CORRELATION_STATE_PATH = str(_ROOT / "shared/state/correlation_state.json")
    def state_file_ages():
        import time
        paths = {
            "ml_state": ML_STATE_PATH, "pead_state": PEAD_STATE_PATH,
            "regime_state": REGIME_STATE_PATH,
        }
        now = time.time()
        return {k: round((now - os.path.getmtime(p)) / 3600, 1) if os.path.exists(p) else None
                for k, p in paths.items()}

# Also check legacy ml_state location
_ML_STATE_LEGACY = str(_ROOT / "portfolio/data/ml_state.json")

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── App factory ───────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")
app.config["JSON_SORT_KEYS"] = False


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path):
    """Load a JSON file; return {} on any error."""
    for p in ([path, _ML_STATE_LEGACY] if "ml_state" in str(path) else [path]):
        try:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log.warning(f"JSON load failed {p}: {e}")
    return {}


def _db_rows(sql, params=None):
    """Execute a SELECT; return list of dicts. Returns [] if DB unavailable."""
    if not DB_AVAILABLE:
        return []
    try:
        session = get_session()
        result  = session.execute(text(sql), params or {})
        keys    = result.keys()
        rows    = [dict(zip(keys, r)) for r in result.fetchall()]
        session.close()
        return rows
    except Exception as e:
        log.warning(f"DB query failed: {e}")
        return []


def _db_exec(sql, params=None):
    """Execute an INSERT/UPDATE; commit. Returns True on success."""
    if not DB_AVAILABLE:
        return False
    try:
        session = get_session()
        session.execute(text(sql), params or {})
        session.commit()
        session.close()
        return True
    except Exception as e:
        log.warning(f"DB exec failed: {e}")
        return False


def _monte_carlo(up_proba, vol_ann, current_price, n_sims=10_000, horizon=21):
    """Return (sim_prices, stats_dict) for a single ticker."""
    rng   = np.random.default_rng(42)
    t     = horizon / 252
    edge  = (up_proba - 0.5) * 2
    drift = edge * vol_ann * t
    sigma = vol_ann * np.sqrt(t)
    rand  = rng.normal(drift, sigma, n_sims)
    sims  = current_price * np.exp(rand)
    var5  = float(np.percentile(sims, 5))
    var1  = float(np.percentile(sims, 1))
    cvar5 = float(np.mean(sims[sims <= var5]))
    return sims, {
        "p_profit":  round(float(np.mean(sims > current_price)) * 100, 1),
        "p_up5":     round(float(np.mean(sims > current_price * 1.05)) * 100, 1),
        "p_down10":  round(float(np.mean(sims < current_price * 0.90)) * 100, 1),
        "var_5_eur": round(var5, 2),
        "var_1_eur": round(var1, 2),
        "cvar_5_eur":round(cvar5, 2),
    }


def _kelly_half(up_proba, target_eur, current_eur):
    if current_eur <= 0:
        return 0.0
    b = (target_eur - current_eur) / current_eur
    if b <= 0:
        return 0.0
    q = 1 - up_proba
    k = (up_proba * b - q) / b
    return round(max(0, min(k / 2, 0.10)) * 100, 1)


def _action_signal(up_proba):
    if up_proba >= 0.60:   return "BUY"
    if up_proba >= 0.54:   return "LEAN_BUY"
    if up_proba <= 0.40:   return "SELL"
    if up_proba <= 0.46:   return "LEAN_SELL"
    return "NEUTRAL"


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def overview():
    return render_template("overview.html", page="overview")


@app.route("/risk")
def risk():
    return render_template("risk.html", page="risk")


@app.route("/research")
def research():
    return render_template("research.html", page="research")


@app.route("/regime")
def regime():
    return render_template("regime.html", page="regime")


@app.route("/rebalance")
def rebalance():
    return render_template("rebalance.html", page="rebalance")


@app.route("/divergence")
def divergence():
    return render_template("divergence.html", page="divergence")


@app.route("/health")
def health():
    return render_template("health.html", page="health")


# ─────────────────────────────────────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/positions")
def api_positions():
    rows = _db_rows("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight, p.date
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) latest ON p.ticker = latest.ticker AND p.date = latest.md
        ORDER BY p.value_eur DESC
    """)
    total = sum(r["value_eur"] or 0 for r in rows)
    return jsonify({"positions": rows, "total_eur": round(total, 2)})


@app.route("/api/cash")
def api_cash():
    rows = _db_rows("""
        SELECT cash_eur, date, event_type, notes
        FROM cash_history ORDER BY date DESC, id DESC LIMIT 1
    """)
    return jsonify(rows[0] if rows else {"cash_eur": 0, "date": None})


@app.route("/api/trades")
def api_trades():
    rows = _db_rows("""
        SELECT date, ticker, action, quantity, price_eur, value_eur, fee_eur, notes
        FROM trades ORDER BY date DESC, id DESC LIMIT 30
    """)
    return jsonify({"trades": rows})


@app.route("/api/targets")
def api_targets():
    ticker = request.args.get("ticker")
    sql = """
        SELECT ticker, current_price_eur, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
               resistance_ma50, resistance_ma200,
               resistance_bb_upper, support_bb_lower,
               high_52w, low_52w, risk_reward_ratio,
               up_proba, vol_ann, computed_at
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
    """
    if ticker:
        sql += " AND ticker = :ticker"
        rows = _db_rows(sql, {"ticker": ticker})
    else:
        sql += " ORDER BY ticker"
        rows = _db_rows(sql)

    # Augment each row with computed fields
    for r in rows:
        up_p = r.get("up_proba") or 0.5
        cur  = r.get("current_price_eur") or 0
        tgt  = r.get("target_1sigma_eur") or cur
        vol  = r.get("vol_ann") or 0.25
        r["kelly_half"]     = _kelly_half(up_p, tgt, cur)
        r["action"]         = _action_signal(up_p)
        r["exp_pct"]        = round((r.get("expected_21d_eur", cur) - cur) / cur * 100, 1) if cur else 0
        _, mc_stats         = _monte_carlo(up_p, vol, cur) if cur > 0 else (None, {})
        r["mc"]             = mc_stats

    return jsonify({"targets": rows, "count": len(rows)})


@app.route("/api/ml")
def api_ml():
    data = _load_json(ML_STATE_PATH)
    return jsonify(data)


@app.route("/api/regime")
def api_regime():
    data = _load_json(REGIME_STATE_PATH)

    # Add regime history from DB if available
    hist = _db_rows("""
        SELECT date, regime_risk, regime_rates, regime_growth, regime_composite,
               transition_warning, vix, yield_spread
        FROM regime_history ORDER BY date DESC LIMIT 90
    """)
    data["history"] = hist
    return jsonify(data)


@app.route("/api/pead")
def api_pead():
    data = _load_json(PEAD_STATE_PATH)

    # Enrich with DB history
    db_hist = _db_rows("""
        SELECT ticker, earnings_date, direction, pead_setup_quality,
               surprise_pct, drift_21d, outcome_label_correct,
               regime_composite, sector
        FROM pead_setups ORDER BY earnings_date DESC LIMIT 60
    """)
    if db_hist:
        data["db_history"] = db_hist
    elif os.path.exists(PEAD_SETUPS_PATH):
        import csv
        with open(PEAD_SETUPS_PATH, newline="", encoding="utf-8") as f:
            data["db_history"] = list(csv.DictReader(f))[:60]

    return jsonify(data)


@app.route("/api/rebalance")
def api_rebalance():
    today = date.today().isoformat()
    rows = _db_rows("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return
        FROM model_outputs
        WHERE date = :date
        ORDER BY ABS(delta_weight) DESC
    """, {"date": today})
    for r in rows:
        dw = r.get("delta_weight", 0) or 0
        r["action"] = "BUY" if dw > 0.005 else ("SELL" if dw < -0.005 else "HOLD")
    return jsonify({"suggestions": rows, "date": today})


@app.route("/api/pipeline")
def api_pipeline():
    rows = _db_rows("""
        SELECT run_date, step_name, status, duration_sec, error_msg, started_at
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 150
    """)
    # Group by run_date
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["run_date"]].append(r)
    runs = [{"date": d, "steps": s} for d, s in sorted(grouped.items(), reverse=True)]
    return jsonify({"runs": runs[:7]})


@app.route("/api/freshness")
def api_freshness():
    ages = state_file_ages()
    db_ok = DB_AVAILABLE
    # Last pipeline run
    last_run = _db_rows("""
        SELECT MAX(run_date) as last_run FROM pipeline_runs WHERE status = 'success'
    """)
    return jsonify({
        "file_ages_hours": ages,
        "db_available":    db_ok,
        "last_pipeline_run": last_run[0]["last_run"] if last_run else None,
    })


@app.route("/api/divergence")
def api_divergence():
    unlabeled = _db_rows("""
        SELECT id, ticker, etf_reference, detected_at,
               etf_return_pct, stock_return_pct, divergence_pct, scenario_label
        FROM divergence_labels
        WHERE scenario_label IS NULL
        ORDER BY detected_at DESC
        LIMIT 20
    """)
    return jsonify({"unlabeled": unlabeled, "count": len(unlabeled)})


@app.route("/api/override", methods=["POST"])
def api_override():
    body = request.get_json(force=True)
    ok = _db_exec("""
        INSERT INTO override_log (date, ticker, model_suggestion, action_taken, reason)
        VALUES (CURRENT_DATE, :ticker, :suggestion, :action, :reason)
    """, {
        "ticker":     body.get("ticker"),
        "suggestion": body.get("model_suggestion"),
        "action":     body.get("action_taken"),
        "reason":     body.get("reason", ""),
    })
    return jsonify({"ok": ok})


@app.route("/api/label", methods=["POST"])
def api_label():
    body = request.get_json(force=True)
    ok = _db_exec("""
        UPDATE divergence_labels
        SET scenario_label  = :scenario,
            confidence      = :confidence,
            notes           = :notes,
            checklist_answers = :checklist,
            labeled_at      = datetime('now')
        WHERE id = :id
    """, {
        "id":         body.get("id"),
        "scenario":   body.get("scenario"),
        "confidence": body.get("confidence"),
        "notes":      body.get("notes", ""),
        "checklist":  json.dumps(body.get("checklist", {})),
    })
    return jsonify({"ok": ok})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Control Tower on http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)
