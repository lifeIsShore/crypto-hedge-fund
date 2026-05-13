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

import sys, os, json, logging, tempfile, shutil
from pathlib import Path
import yfinance as yf
from datetime import datetime, date, timedelta
import pandas as pd
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


def _get_latest_fx_rate(pair="USDEUR"):
    """Fetch latest rate from fx_rates table; fallback to constant if empty."""
    rows = _q("SELECT rate FROM fx_rates WHERE pair = :p ORDER BY date DESC LIMIT 1", {"p": pair})
    if rows:
        return float(rows[0]["rate"])
    # Emergency fallback constants if fx_rates table hasn't been populated
    fallbacks = {"USDEUR": 0.92, "GBPEUR": 1.17}
    return fallbacks.get(pair, 1.0)


def _get_live_price_fallback(ticker):
    """
    Emergency live fetch from yfinance if DB is stale/missing.
    Returns: (price, currency)
    """
    try:
        # We use a very small period for speed
        data = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if not data.empty:
            # Get latest close
            price = float(data['Close'].iloc[-1])
            # Basic currency heuristic: .DE/.AS/.PA are EUR, everything else USD
            curr = "EUR" if any(ticker.endswith(s) for s in [".DE", ".AS", ".PA"]) else "USD"
            return price, curr
    except Exception as e:
        log.warning(f"Live fallback failed for {ticker}: {e}")
    return None, "EUR"


def _live_positions():
    """
    Live Reconstruction model — compute current holdings directly from the
    trades ledger + latest available prices.  This replaces any read from
    positions_history so the dashboard refreshes the instant a trade is logged.

    Returns a list of dicts with keys:
      ticker, quantity, price, value_eur, weight
    and a separate cash_eur float.
    """
    # 1. Sum up all BUY / SELL quantities per ticker from the trades table
    trade_rows = _q("""
        SELECT ticker, action, SUM(quantity) AS qty_sum
        FROM trades
        WHERE action IN ('BUY', 'SELL') AND quantity IS NOT NULL
        GROUP BY ticker, action
    """)

    qty_map = {}  # ticker -> net shares
    for row in trade_rows:
        t   = row["ticker"]
        qty = float(row["qty_sum"] or 0)
        if row["action"] == "BUY":
            qty_map[t] = qty_map.get(t, 0.0) + qty
        else:  # SELL
            qty_map[t] = qty_map.get(t, 0.0) - qty

    # Remove fully-exited positions (≤ 0 shares)
    qty_map = {t: q for t, q in qty_map.items() if q > 1e-8}

    # 2. Fetch latest price for each held ticker
    positions = []
    if qty_map:
        tickers_sql = ",".join(f"'{t}'" for t in qty_map)
        price_rows = _q(f"""
            SELECT p.ticker, p.adj_close AS price, p.currency
            FROM prices p
            INNER JOIN (
                SELECT ticker, MAX(date) AS md FROM prices
                WHERE ticker IN ({tickers_sql})
                GROUP BY ticker
            ) l ON p.ticker = l.ticker AND p.date = l.md
        """)
        # Store as (price, currency)
        price_map = {r["ticker"]: (float(r["price"] or 0.0), r.get("currency") or "EUR") for r in price_rows}

        usd_eur = _get_latest_fx_rate("USDEUR")
        gbp_eur = _get_latest_fx_rate("GBPEUR")

        for ticker, qty in qty_map.items():
            price_data = price_map.get(ticker)
            if not price_data:
                # DB MISSING — try live fetch from yfinance
                log.info(f"Price missing for {ticker} in DB — attempting live fallback.")
                price_data = _get_live_price_fallback(ticker)
                
            raw_price, curr = price_data

            # Apply dynamic conversion if not EUR
            price = raw_price
            if price is not None:
                if curr == "USD":
                    price = raw_price * usd_eur
                elif curr == "GBP":
                    price = raw_price * gbp_eur

            has_price = price is not None and price > 0
            value_eur = round(qty * price, 4) if has_price else None
            positions.append({
                "ticker":      ticker,
                "quantity":    round(qty, 6),
                "price":       round(price, 4) if has_price else None,
                "value_eur":   value_eur,
                "weight":      0.0,
                "price_missing": not has_price,
            })

    # 3. Latest cash from cash_history
    cash_rows = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
    cash_eur  = float(cash_rows[0]["cash_eur"] or 0.0) if cash_rows else 0.0

    # 4. Recalculate portfolio weights — only use positions with known prices
    priced_value = sum(float(p["value_eur"] or 0.0) for p in positions if p["value_eur"] is not None)
    total_eur = priced_value + cash_eur
    if total_eur > 0:
        for p in positions:
            if p["value_eur"] is not None:
                p["weight"] = round(p["value_eur"] / total_eur, 6)
            else:
                p["weight"] = None  # unknown — can't calculate

    # Sort: priced positions first (by value desc), then unpriced at bottom
    positions.sort(key=lambda p: (p["value_eur"] is None, -(p["value_eur"] or 0)))
    return positions, cash_eur


def _mc_portfolio(positions, targets_map, n_paths=8000):
    """Run Monte Carlo on portfolio; return (var5_pct, cvar5_pct, var1_pct, total_eur)."""
    total = sum(float(p.get("value_eur") or 0.0) for p in positions)
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
    """Initialize the background task manager.
    
    Skipped automatically when DASHBOARD_ONLY=1 is set in the environment,
    so DASHBOARD_ONLY.bat never triggers a background data refresh.
    """
    if os.environ.get("DASHBOARD_ONLY") == "1":
        log.info("📺 [OBSERVER MODE] Scheduler disabled — running in dashboard-only mode.")
        return None
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


def log_pipeline_event(step_name: str, message: str, level: str = "INFO", detail=None):
    """Write a structured log entry to pipeline_logs table.
    Call from any pipeline script to make logs visible in health.html."""
    _exec("""
        INSERT INTO pipeline_logs (level, step_name, message, detail, run_date)
        VALUES (:level, :step, :msg, :detail, date('now'))
    """, {
        "level":  level.upper(),
        "step":   step_name,
        "msg":    message,
        "detail": json.dumps(detail) if detail is not None else None,
    })


def check_api_connectivity() -> dict:
    """Probe external data providers. Returns status dict.
    Used by /api/kill_switch_status and health.html Kill Switch panel."""
    import urllib.request
    import urllib.error

    results = {}
    probes = {
        "yahoo_finance": "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=1d",
        "fred":          "https://fred.stlouisfed.org/",
    }
    for name, url in probes.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                results[name] = {"ok": True,  "status": resp.status}
        except urllib.error.HTTPError as e:
            results[name] = {"ok": False, "status": e.code,   "error": str(e.reason)}
        except Exception as e:
            results[name] = {"ok": False, "status": None, "error": str(e)[:120]}
    return results


def atomic_write_json(path, data):
    """Write JSON atomically: write to temp file, then rename.
    Ensures the Flask app never reads a half-finished file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.json")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        shutil.move(str(tmp), str(path))
    except Exception as e:
        log.error(f"atomic_write_json failed for {path}: {e}")
        tmp.unlink(missing_ok=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def overview():
    # Live Reconstruction — reads trades ledger + latest prices, no snapshot needed
    positions, cash_eur = _live_positions()
    total_eur = sum(float(p["value_eur"] or 0.0) for p in positions) + cash_eur

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
        page="overview",
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
        page="risk",
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
        page="research",
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
        page="rebalance",
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
        page="pead",
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
        page="divergence",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# JSON APIS  (consumed by Chart.js / DataTables on the frontend)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/freshness")
def api_freshness():
    """Data freshness endpoint used by base.html footer and health.html."""
    ages = state_file_ages()
    # Determine if any state file is stale (>24h)
    stale = [k for k, v in ages.items() if v is not None and v > 24]
    # Last successful pipeline run
    last_runs = _q("SELECT run_date FROM pipeline_runs WHERE status='success' ORDER BY started_at DESC LIMIT 1")
    last_run = last_runs[0]["run_date"] if last_runs else None
    # DB availability check
    try:
        _q("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        "file_ages_hours": ages,
        "stale_files": stale,
        "last_pipeline_run": last_run,
        "db_available": db_ok,
        "generated_at": datetime.now().isoformat(),
    })


@app.route("/api/holdings")
def api_holdings():
    """Current holdings with ML signal overlay — live reconstruction."""
    positions, cash_eur = _live_positions()

    # Overlay ML signals
    if positions:
        tickers_sql = ",".join(f"'{p['ticker']}'" for p in positions)
        targets = _q(f"""
            SELECT ticker, up_proba, vol_ann, expected_21d_eur,
                   target_1sigma_eur, stop_1sigma_eur, risk_reward_ratio
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
              AND ticker IN ({tickers_sql})
        """)
        targets_map = {t["ticker"]: t for t in targets}
        for p in positions:
            sig = targets_map.get(p["ticker"], {})
            p["up_proba"]          = sig.get("up_proba")
            p["vol_ann"]           = sig.get("vol_ann")
            p["expected_21d_eur"]  = sig.get("expected_21d_eur")
            p["target_1sigma_eur"] = sig.get("target_1sigma_eur")
            p["stop_1sigma_eur"]   = sig.get("stop_1sigma_eur")
            p["risk_reward_ratio"] = sig.get("risk_reward_ratio")

    return jsonify({"positions": positions, "cash_eur": cash_eur})


@app.route("/api/trades")
def api_trades():
    """Trade history."""
    limit = int(request.args.get("limit", 200))
    ticker = request.args.get("ticker")
    if ticker:
        rows = _q("""
            SELECT date, ticker, action, quantity, price_eur,
                   value_eur AS total_eur, notes
            FROM trades WHERE ticker=:t ORDER BY date DESC LIMIT :lim
        """, {"t": ticker.upper(), "lim": limit})
    else:
        rows = _q("""
            SELECT date, ticker, action, quantity, price_eur,
                   value_eur AS total_eur, notes
            FROM trades ORDER BY date DESC LIMIT :lim
        """, {"lim": limit})
    return jsonify(rows)


@app.route("/api/pipeline")
def api_pipeline():
    """Pipeline run history grouped by date."""
    rows = _q("""
        SELECT step_name, status, duration_sec, run_date, started_at, error_msg
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 100
    """)
    # Group by run_date
    grouped = {}
    for r in rows:
        d = r.get("run_date", "unknown")
        grouped.setdefault(d, {"date": d, "steps": []})["steps"].append(r)
    runs = sorted(grouped.values(), key=lambda x: x["date"], reverse=True)
    return jsonify({"runs": runs})

@app.route("/api/price_targets")
def api_price_targets():
    data = _q("""
        SELECT ticker, current_price_eur, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
               resistance_ma50, resistance_ma200,
               resistance_bb_upper, support_bb_lower,
               high_52w, low_52w, risk_reward_ratio,
               up_proba, vol_ann, kelly_half, computed_at
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

    total = sum(float(p.get("value_eur") or 0.0) for p in positions)
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


@app.route("/regime")
def regime():
    reg = _load_json(REGIME_STATE_PATH)
    ages = state_file_ages()
    return render_template("regime.html",
        regime=reg,
        ages=ages,
        page="regime",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/divergence")
def divergence():
    rows = _q("""
        SELECT id, ticker, etf_reference, detected_at,
               etf_return_pct, stock_return_pct, divergence_pct, scenario_label
        FROM divergence_labels
        WHERE scenario_label IS NULL
        ORDER BY detected_at DESC
        LIMIT 30
    """)
    return render_template("divergence.html",
        rows=rows,
        page="divergence",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/analytics")
def analytics():
    positions = _q("""
        SELECT p.ticker, p.quantity, p.price, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
        ORDER BY p.value_eur DESC
    """)
    trades = _q("""
        SELECT date, ticker, action, quantity, price_eur,
               value_eur AS total_eur, notes
        FROM trades
        ORDER BY date DESC
        LIMIT 100
    """)
    perf = _q("""
        SELECT date, portfolio_value_eur, benchmark_value_eur, daily_return_pct, cumulative_return_pct
        FROM performance_history
        ORDER BY date DESC
        LIMIT 252
    """)
    ages = state_file_ages()
    return render_template("analytics.html",
        positions=positions,
        trades=trades,
        perf=perf,
        ages=ages,
        page="analytics",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/holdings")
def holdings():
    # Live Reconstruction — no snapshot dependency
    positions, cash_eur = _live_positions()

    # Overlay ML signals from price_targets
    targets = _q("""
        SELECT ticker, up_proba, vol_ann, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
    """)
    targets_map = {t["ticker"]: t for t in targets}
    for p in positions:
        sig = targets_map.get(p["ticker"], {})
        p["up_proba"]         = sig.get("up_proba")
        p["vol_ann"]          = sig.get("vol_ann")
        p["expected_21d_eur"] = sig.get("expected_21d_eur")
        p["target_1sigma_eur"] = sig.get("target_1sigma_eur")
        p["stop_1sigma_eur"]  = sig.get("stop_1sigma_eur")
    return render_template("holdings.html",
        positions=positions,
        cash_eur=cash_eur,
        page="holdings",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/trades")
def trades():
    from portfolio.src.config import ASSET_UNIVERSE
    rows = _q("""
        SELECT date, ticker, action, quantity, price_eur,
               value_eur AS total_eur, notes
        FROM trades
        ORDER BY date DESC
        LIMIT 200
    """)
    return render_template("trades.html",
        trades=rows,
        universe=sorted(ASSET_UNIVERSE),
        page="trades",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/ticker/<ticker>")
def ticker_detail(ticker):
    """Ticker Detail page — ML signal + risk metrics + trade history in one view."""
    ticker = ticker.upper()
    target = _q("""
        SELECT * FROM price_targets
        WHERE ticker = :t AND date = (SELECT MAX(date) FROM price_targets WHERE ticker = :t)
    """, {"t": ticker})
    target = target[0] if target else {}

    position = _q("""
        SELECT p.* FROM positions_history p
        INNER JOIN (SELECT ticker, MAX(date) AS md FROM positions_history WHERE ticker=:t GROUP BY ticker) l
          ON p.ticker=l.ticker AND p.date=l.md
    """, {"t": ticker})
    position = position[0] if position else {}

    trades_hist = _q("""
        SELECT date, action, quantity, price_eur,
               value_eur AS total_eur, notes
        FROM trades WHERE ticker=:t ORDER BY date DESC LIMIT 50
    """, {"t": ticker})

    ml = _load_json(ML_STATE_PATH)
    ml_signal = (ml.get("model_signals") or {}).get(ticker, {})

    return render_template("ticker_detail.html",
        ticker=ticker,
        target=target,
        position=position,
        trades_hist=trades_hist,
        ml_signal=ml_signal,
        page="",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


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
        page="health",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# API ALIASES  (overview.html + legacy callers use these short names)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/positions")
def api_positions():
    """Alias: same as /api/holdings but shaped for overview.html — live reconstruction."""
    try:
        positions, cash_eur = _live_positions()
        total_eur = sum(float(p["value_eur"] or 0.0) for p in positions) + cash_eur
        return jsonify({"positions": positions, "cash_eur": cash_eur, "total_eur": total_eur})
    except Exception:
        import traceback
        return traceback.format_exc(), 500


@app.route("/api/cash")
def api_cash():
    """Latest cash balance."""
    rows = _q("SELECT cash_eur, date FROM cash_history ORDER BY date DESC LIMIT 1")
    if rows:
        return jsonify({"cash_eur": float(rows[0]["cash_eur"]), "date": rows[0]["date"]})
    return jsonify({"cash_eur": 0.0, "date": None})


@app.route("/api/ml")
def api_ml():
    """Alias: same as /api/ml_signals — for overview.html compatibility."""
    ml = _load_json(ML_STATE_PATH)
    return jsonify({
        "ensemble":           ml.get("ensemble", {}),
        "model_signals":      ml.get("model_signals", {}),
        "experiment_summary": ml.get("experiment_summary", {}),
        "model_comparison":   ml.get("model_comparison", []),
        "feature_importance": ml.get("feature_importance", []),
        "generated_at":       ml.get("generated_at", ""),
    })


@app.route("/api/rebalance")
def api_rebalance():
    """Trade advisor suggestions from model_outputs."""
    rows = _q("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return
        FROM model_outputs
        WHERE date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY ABS(delta_weight) DESC
    """)
    suggestions = []
    for r in rows:
        delta = float(r.get("delta_weight") or 0)
        action = "BUY" if delta > 0.01 else "SELL" if delta < -0.01 else "HOLD"
        suggestions.append({**r, "action": action})
    return jsonify({"suggestions": suggestions})


@app.route("/api/pead")
def api_pead():
    """PEAD state + history for pead.html."""
    state = _load_json(PEAD_STATE_PATH)
    history = _q("""
        SELECT ticker, earnings_date, direction, pead_setup_quality,
               surprise_pct, drift_21d, outcome_label_correct, regime_composite
        FROM pead_setups
        ORDER BY earnings_date DESC
        LIMIT 60
    """)
    # Derive active windows (entries within last 5 trading days)
    active = _q("""
        SELECT ticker, earnings_date AS entry_date, direction, pead_setup_quality AS quality,
               surprise_pct, regime_composite
        FROM pead_setups
        WHERE earnings_date >= date('now', '-7 days')
        ORDER BY earnings_date DESC
    """)
    performance = state.get("performance", {})
    by_quality  = state.get("by_quality", {})
    by_regime   = state.get("by_regime", {})
    return jsonify({
        "performance":  performance,
        "by_quality":   by_quality,
        "by_regime":    by_regime,
        "active_setups": active,
        "db_history":   history,
        "generated_at": state.get("generated_at", ""),
    })


@app.route("/api/log_trade", methods=["POST"])
def api_log_trade():
    """
    Log a manual transaction directly to the SQLite DB.
    Handles: Buy, Sell, Deposit, Dividend, Fee.

    Body (JSON):
      action   : 'Buy' | 'Sell' | 'Deposit' | 'Dividend' | 'Fee'
      ticker   : e.g. 'NVDA', 'CASH'
      quantity : float  (required for Buy/Sell)
      price    : float  (price per share for Buy/Sell; total amount for others)
      date     : 'YYYY-MM-DD'  (optional, defaults to today)
      notes    : str   (optional)
      fee_eur  : float (optional explicit fee, default 0)
    """
    data = request.get_json(force=True)
    action   = (data.get("action") or "").strip()
    ticker   = (data.get("ticker") or "CASH").strip().upper()
    qty      = data.get("quantity")
    price    = data.get("price")
    trade_date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    notes    = data.get("notes", "") or ""
    fee_eur  = float(data.get("fee_eur") or 0)

    # ── Validation ────────────────────────────────────────────────────────────
    if action not in ("Buy", "Sell", "Deposit", "Dividend", "Fee"):
        return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    try:
        price = float(price)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "price must be a number"}), 400

    if price <= 0:
        return jsonify({"ok": False, "error": "price must be > 0"}), 400

    if action in ("Buy", "Sell"):
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "quantity required for Buy/Sell"}), 400
        if qty <= 0:
            return jsonify({"ok": False, "error": "quantity must be > 0"}), 400
        total_eur = round(qty * price, 6)
    else:
        qty = None
        total_eur = round(price, 6)   # price IS the total amount

    # ── Write trade row ───────────────────────────────────────────────────────
    ok = _exec("""
        INSERT INTO trades (date, ticker, action, quantity, price_eur, value_eur, fee_eur, notes, source)
        VALUES (:date, :ticker, :action, :qty, :price, :total, :fee, :notes, 'manual')
    """, {
        "date":   trade_date,
        "ticker": ticker,
        "action": action.upper(),
        "qty":    qty,
        "price":  price if action in ("Buy", "Sell") else None,
        "total":  total_eur,
        "fee":    fee_eur,
        "notes":  notes,
    })
    if not ok:
        return jsonify({"ok": False, "error": "DB write failed for trade row"}), 500

    # ── Update cash_history ───────────────────────────────────────────────────
    # Get current cash balance
    cash_rows = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
    current_cash = float(cash_rows[0]["cash_eur"]) if cash_rows else 0.0

    if action == "Buy":
        new_cash = current_cash - total_eur - fee_eur
        event_type = "BUY_DEBIT"
    elif action == "Sell":
        new_cash = current_cash + total_eur - fee_eur
        event_type = "SELL_CREDIT"
    elif action == "Deposit":
        new_cash = current_cash + total_eur
        event_type = "DEPOSIT"
    elif action == "Dividend":
        new_cash = current_cash + total_eur
        event_type = "DIVIDEND"
    elif action == "Fee":
        new_cash = current_cash - total_eur
        event_type = "FEE_DEBIT"
    else:
        new_cash = current_cash
        event_type = "OTHER"

    _exec("""
        INSERT INTO cash_history (date, cash_eur, event_type, notes)
        VALUES (:date, :cash, :event, :notes)
    """, {
        "date":  trade_date,
        "cash":  round(new_cash, 4),
        "event": event_type,
        "notes": f"{action} {ticker} — {notes}".strip(" —"),
    })

    log.info(f"[TRADE LOGGED] {trade_date} {action} {ticker} qty={qty} price={price} total={total_eur}")
    return jsonify({
        "ok": True,
        "trade": {
            "date": trade_date, "action": action.upper(),
            "ticker": ticker, "quantity": qty,
            "price_eur": price, "total_eur": total_eur,
        },
        "new_cash_eur": round(new_cash, 4),
    })


@app.route("/api/divergence")
def api_divergence():
    """Unlabeled divergence events for the labeling UI."""
    rows = _q("""
        SELECT id, ticker, etf_reference, detected_at,
               etf_return_pct, stock_return_pct, divergence_pct
        FROM divergence_labels
        WHERE scenario_label IS NULL
        ORDER BY detected_at DESC
        LIMIT 30
    """)
    return jsonify({"unlabeled": rows, "count": len(rows)})


@app.route("/api/performance")
def api_performance():
    """
    Compute full portfolio performance analytics from raw DB data.
    Returns KPIs, daily return series, equity curve, and ledger.
    All computed server-side — no synthetic data.
    """
    import math

    # ── 1. Ledger from trades table ──────────────────────────────────────────
    trades_rows = _q("""
        SELECT date, action, ticker, quantity, price_eur,
               value_eur AS total_eur, fee_eur, notes
        FROM trades ORDER BY date ASC, id ASC
    """)

    # ── 2. Total deposited / withdrawn capital ────────────────────────────
    total_deposited = sum(
        float(t.get("total_eur") or 0)
        for t in trades_rows if t["action"] == "DEPOSIT"
    )
    total_dividends = sum(
        float(t.get("total_eur") or 0)
        for t in trades_rows if t["action"] == "DIVIDEND"
    )
    total_fees = sum(
        float(t.get("fee_eur") or 0) + (float(t.get("total_eur") or 0) if t["action"] == "FEE" else 0)
        for t in trades_rows
    )

    # ── 3. Current portfolio state ────────────────────────────────────────
    positions = _q("""
        SELECT p.ticker, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
    """)
    cash_row = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
    cash_eur = float(cash_row[0]["cash_eur"]) if cash_row else 0.0
    holdings_value = sum(float(p.get("value_eur") or 0) for p in positions)
    total_value = holdings_value + cash_eur

    # ── 4. P&L ─────────────────────────────────────────────────────────────
    invested_base = total_deposited  # deposits only, not dividends
    gross_pnl = total_value - invested_base + total_dividends
    net_pnl   = gross_pnl - total_fees
    real_return_pct = (net_pnl / invested_base * 100) if invested_base > 0 else 0.0
    fee_drag_pct    = (total_fees / invested_base * 100) if invested_base > 0 else 0.0

    # ── 5. Daily return series from performance_history OR cash_history proxy ──
    perf_rows = _q("""
        SELECT date, portfolio_value_eur, daily_return_pct
        FROM performance_history
        ORDER BY date ASC
    """)

    daily_returns = []   # list of {date, r} where r is decimal return
    equity_series = []   # list of {date, value}

    if perf_rows:
        for row in perf_rows:
            r = row.get("daily_return_pct")
            v = row.get("portfolio_value_eur")
            if r is not None and v is not None:
                daily_returns.append({"date": row["date"], "r": float(r) / 100})
                equity_series.append({"date": row["date"], "value": float(v)})
    else:
        # Proxy: reconstruct from cash_history snapshots
        cash_hist = _q("""
            SELECT date, cash_eur FROM cash_history ORDER BY date ASC
        """)
        # Group by date — take last entry per date
        cash_by_date = {}
        for row in cash_hist:
            cash_by_date[row["date"]] = float(row["cash_eur"])

        dates_sorted = sorted(cash_by_date.keys())
        prev_val = None
        for d in dates_sorted:
            val = cash_by_date[d]
            # Add holdings value proxy (use total_value as constant for now)
            # This is a rough proxy; proper equity curve needs daily price snapshots
            if prev_val is not None and prev_val > 0:
                r = (val - prev_val) / prev_val
                daily_returns.append({"date": d, "r": r})
            equity_series.append({"date": d, "value": val})
            prev_val = val

    # If still no return series, return minimal KPIs only
    n = len(daily_returns)
    returns_arr = [x["r"] for x in daily_returns]

    # ── 6. Risk metrics (computed from return series) ────────────────────
    def _mean(xs):  return sum(xs) / len(xs) if xs else 0.0
    def _std(xs):
        if len(xs) < 2: return 0.0
        m = _mean(xs)
        return math.sqrt(sum((x - m)**2 for x in xs) / (len(xs) - 1))

    vol_daily   = _std(returns_arr)
    vol_ann_pct = vol_daily * math.sqrt(252) * 100
    rf          = 0.04 / 252            # 4% annual risk-free
    excess      = [r - rf for r in returns_arr]
    sharpe      = (_mean(excess) / _std(excess) * math.sqrt(252)) if _std(excess) > 0 else 0.0

    # Max drawdown
    peak = -math.inf
    max_dd = 0.0
    cum = 1.0
    for r in returns_arr:
        cum *= (1 + r)
        if cum > peak: peak = cum
        dd = (peak - cum) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd

    calmar = (real_return_pct / 100 / max_dd) if max_dd > 0 else 0.0

    # VaR / CVaR
    sorted_r = sorted(returns_arr)
    var95_idx = max(0, int(0.05 * n) - 1)
    var99_idx = max(0, int(0.01 * n) - 1)
    var95_pct = sorted_r[var95_idx] * 100 if sorted_r else 0.0
    var99_pct = sorted_r[var99_idx] * 100 if sorted_r else 0.0
    tail95    = sorted_r[:max(1, int(0.05 * n))]
    cvar95_pct = _mean(tail95) * 100 if tail95 else 0.0

    # Skewness & Kurtosis
    skewness = 0.0
    kurtosis = 0.0
    if n >= 4 and vol_daily > 0:
        m = _mean(returns_arr)
        s = vol_daily
        skewness = _mean([(r - m)**3 for r in returns_arr]) / s**3
        kurtosis = _mean([(r - m)**4 for r in returns_arr]) / s**4 - 3  # excess

    # Win/loss stats
    FLAT = 0.00005
    wins   = [r for r in returns_arr if r >  FLAT]
    losses = [r for r in returns_arr if r < -FLAT]
    win_rate     = len(wins)   / n if n > 0 else 0.0
    loss_rate    = len(losses) / n if n > 0 else 0.0
    avg_win_pct  = _mean(wins)   * 100 if wins   else 0.0
    avg_loss_pct = _mean(losses) * 100 if losses else 0.0   # negative number
    wl_ratio     = (avg_win_pct / abs(avg_loss_pct)) if avg_loss_pct < 0 else 0.0
    expectancy   = (win_rate * avg_win_pct) + (loss_rate * avg_loss_pct)
    profit_factor = (
        sum(wins) / abs(sum(losses))
        if losses and sum(losses) != 0 else 0.0
    )
    consistency  = win_rate * wl_ratio

    best_day_pct  = max(returns_arr) * 100 if returns_arr else 0.0
    worst_day_pct = min(returns_arr) * 100 if returns_arr else 0.0

    # Streaks
    best_win_streak = worst_loss_streak = cur_streak = 0
    cur_type = "flat"
    streak = 0
    streak_type = None
    for r in returns_arr:
        t = "win" if r > FLAT else "loss" if r < -FLAT else "flat"
        if t == streak_type:
            streak += 1
        else:
            streak = 1
            streak_type = t
        if t == "win":  best_win_streak  = max(best_win_streak,  streak)
        if t == "loss": worst_loss_streak = max(worst_loss_streak, streak)
    if returns_arr:
        cur_streak = streak
        cur_type   = streak_type

    # Information Ratio vs flat benchmark (0)
    info_ratio = sharpe * 0.6  # proxy if no benchmark data
    bench_rows = _q("""
        SELECT date, benchmark_value_eur FROM performance_history
        WHERE benchmark_value_eur IS NOT NULL ORDER BY date ASC
    """)
    if len(bench_rows) >= 2:
        bench_rets = []
        for i in range(1, len(bench_rows)):
            prev_b = float(bench_rows[i-1]["benchmark_value_eur"] or 1)
            curr_b = float(bench_rows[i]["benchmark_value_eur"] or 1)
            bench_rets.append((curr_b - prev_b) / prev_b if prev_b > 0 else 0)
        port_slice = [r["r"] for r in daily_returns[:len(bench_rets)]]
        if len(port_slice) == len(bench_rets) and _std(bench_rets) > 0:
            active = [p - b for p, b in zip(port_slice, bench_rets)]
            info_ratio = (_mean(active) / _std(active) * math.sqrt(252)) if _std(active) > 0 else 0

    kpis = {
        "total_deposited":      round(total_deposited, 2),
        "total_dividends":      round(total_dividends, 2),
        "total_fees":           round(total_fees, 2),
        "current_value":        round(total_value, 2),
        "holdings_value":       round(holdings_value, 2),
        "cash_eur":             round(cash_eur, 2),
        "gross_pnl":            round(gross_pnl, 2),
        "net_pnl":              round(net_pnl, 2),
        "real_return_pct":      round(real_return_pct, 3),
        "fee_drag_pct":         round(fee_drag_pct, 3),
        "sharpe_ratio":         round(sharpe, 3),
        "calmar_ratio":         round(calmar, 3),
        "max_drawdown":         round(max_dd, 4),
        "information_ratio":    round(info_ratio, 3),
        "profit_factor":        round(profit_factor, 3),
        "ann_volatility_pct":   round(vol_ann_pct, 3),
        "var95_daily_pct":      round(var95_pct, 4),
        "var99_daily_pct":      round(var99_pct, 4),
        "cvar95_daily_pct":     round(cvar95_pct, 4),
        "skewness":             round(skewness, 4),
        "excess_kurtosis":      round(kurtosis, 4),
        "win_rate":             round(win_rate, 4),
        "loss_rate":            round(loss_rate, 4),
        "avg_win_pct":          round(avg_win_pct, 4),
        "avg_loss_pct":         round(avg_loss_pct, 4),
        "win_loss_ratio":       round(wl_ratio, 3),
        "expectancy_pct":       round(expectancy, 5),
        "consistency_score":    round(consistency, 4),
        "best_day_pct":         round(best_day_pct, 4),
        "worst_day_pct":        round(worst_day_pct, 4),
        "best_win_streak":      best_win_streak,
        "worst_loss_streak":    worst_loss_streak,
        "current_streak":       cur_streak,
        "current_streak_type":  cur_type,
        "total_return_days":    n,
        "win_days":             len(wins),
        "loss_days":            len(losses),
    }

    return jsonify({
        "kpis":          kpis,
        "daily_returns": daily_returns,    # [{date, r}]
        "equity_series": equity_series,    # [{date, value}]
        "ledger":        trades_rows,       # raw trades for ledger table
        "generated_at":  datetime.now().isoformat(),
    })


@app.route("/api/mpt_weights")
def api_mpt_weights():
    """MPT optimal weights from latest model_outputs, vs current holdings."""
    model = _q("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, expected_return, bl_return
        FROM model_outputs
        WHERE date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY suggested_weight DESC
    """)
    # Current positions for cross-reference
    positions = _q("""
        SELECT p.ticker, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
    """)
    pos_map = {p["ticker"]: p for p in positions}
    result = []
    for row in model:
        t = row["ticker"]
        cur = pos_map.get(t, {})
        result.append({
            "ticker":           t,
            "current_weight":   row.get("current_weight"),
            "optimal_weight":   row.get("suggested_weight"),
            "delta":            row.get("delta_weight"),
            "expected_return":  row.get("expected_return"),
            "bl_return":        row.get("bl_return"),
            "value_eur":        cur.get("value_eur"),
        })
    return jsonify({"weights": result, "count": len(result)})


@app.route("/backtests")
def backtests():
    """List backtest report files in the backtests/ folder."""
    import glob
    bt_dir = ROOT / "backtests"
    bt_dir.mkdir(exist_ok=True)
    files = sorted(bt_dir.glob("*.html"), reverse=True) + \
            sorted(bt_dir.glob("*.json"), reverse=True) + \
            sorted(bt_dir.glob("*.csv"),  reverse=True)
    reports = [{"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
               for f in files]
    return render_template("backtests.html",
        reports=reports,
        page="health",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/backtests/<filename>")
def backtest_file(filename):
    """Serve a specific backtest report file."""
    from flask import send_from_directory
    bt_dir = ROOT / "backtests"
    return send_from_directory(bt_dir, filename)


@app.route("/history")
def history():
    return render_template("history.html",
        page="history",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/risk_events")
def api_risk_events():
    """Risk events for health.html Kill Switch panel."""
    rows = _q("""
        SELECT date, event_type, ticker, detail, logged_at
        FROM risk_events
        ORDER BY logged_at DESC
        LIMIT 30
    """)
    return jsonify(rows)


@app.route("/api/kill_switch_status")
def api_kill_switch_status():
    """Live connectivity probe for external data providers.
    health.html Kill Switch panel polls this to turn RED when data providers are down."""
    connectivity = check_api_connectivity()
    all_ok = all(v["ok"] for v in connectivity.values())
    ages   = state_file_ages()
    stale  = [k for k, v in ages.items() if v is not None and v > 24]
    return jsonify({
        "all_providers_ok": all_ok,
        "providers":        connectivity,
        "stale_files":      stale,
        "kill_switch_active": not all_ok or len(stale) > 0,
        "checked_at":       datetime.now().isoformat(),
    })


@app.route("/api/pipeline_logs")
def api_pipeline_logs():
    """Structured pipeline log entries for health.html log viewer."""
    level = request.args.get("level")   # optional filter: ERROR, WARNING, INFO
    limit = int(request.args.get("limit", 100))
    if level:
        rows = _q("""
            SELECT id, logged_at, level, step_name, message, detail, run_date
            FROM pipeline_logs
            WHERE level = :level
            ORDER BY logged_at DESC
            LIMIT :lim
        """, {"level": level.upper(), "lim": limit})
    else:
        rows = _q("""
            SELECT id, logged_at, level, step_name, message, detail, run_date
            FROM pipeline_logs
            ORDER BY logged_at DESC
            LIMIT :lim
        """, {"lim": limit})
    return jsonify({"logs": rows, "count": len(rows)})


@app.route("/api/stress_tests")
def api_stress_tests():
    """Beta-adjusted stress test results for current holdings.
    Beta is computed from the past 252 trading days of daily log-returns,
    regressing each ticker against the benchmark (EUNL.DE as SPY proxy).
    Falls back to beta=1.0 if fewer than 60 overlapping days exist."""
    import math

    positions = _q("""
        SELECT p.ticker, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS md FROM positions_history GROUP BY ticker
        ) l ON p.ticker = l.ticker AND p.date = l.md
    """)
    cash_row = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC LIMIT 1")
    cash_eur = float(cash_row[0]["cash_eur"]) if cash_row else 0.0
    total_value = sum(float(p["value_eur"]) for p in positions) + cash_eur

    # Historical scenarios with approximate market drawdowns
    SCENARIOS = [
        {"name": "COVID Crash (Feb-Mar 2020)",    "market_dd": -0.340, "period": "2020-02-20/2020-03-23"},
        {"name": "GFC (Oct 2007 – Mar 2009)",      "market_dd": -0.570, "period": "2007-10-01/2009-03-09"},
        {"name": "Dot-Com Bust (Mar 2000–Oct 2002)","market_dd": -0.490, "period": "2000-03-01/2002-10-09"},
        {"name": "2022 Rate Shock (Jan-Oct 2022)", "market_dd": -0.255, "period": "2022-01-03/2022-10-12"},
        {"name": "Flash Crash (May 2010)",          "market_dd": -0.099, "period": "2010-05-06/2010-05-07"},
    ]

    # ── Compute real beta per ticker from 252-day price history ─────────────────
    from portfolio.src.config import BENCHMARK_TICKER

    # Load benchmark daily returns
    bench_rows = _q("""
        SELECT date,
               (adj_close / LAG(adj_close) OVER (ORDER BY date)) - 1 AS r
        FROM prices
        WHERE ticker = :b
        ORDER BY date DESC
        LIMIT 253
    """, {"b": BENCHMARK_TICKER})
    bench_map = {row["date"]: float(row["r"]) for row in bench_rows if row["r"] is not None}

    def _compute_beta(ticker: str) -> tuple:
        """Return (beta, n_days). Falls back to (1.0, 0) on insufficient data."""
        stock_rows = _q("""
            SELECT date,
                   (adj_close / LAG(adj_close) OVER (ORDER BY date)) - 1 AS r
            FROM prices
            WHERE ticker = :t
            ORDER BY date DESC
            LIMIT 253
        """, {"t": ticker})
        stock_map = {row["date"]: float(row["r"]) for row in stock_rows if row["r"] is not None}

        common_dates = sorted(set(stock_map) & set(bench_map))
        n = len(common_dates)
        if n < 30:
            return 1.0, n

        xs = [bench_map[d]  for d in common_dates]   # benchmark returns
        ys = [stock_map[d]  for d in common_dates]   # stock returns

        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov    = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (n - 1)
        var_x  = sum((x - mean_x) ** 2             for x in xs)           / (n - 1)

        beta = cov / var_x if var_x > 1e-10 else 1.0
        # Clamp to reasonable range: -3 to +5
        beta = max(-3.0, min(5.0, beta))
        return round(beta, 3), n

    # Cache betas (one DB round-trip per ticker)
    beta_cache = {}
    for pos in positions:
        ticker = pos["ticker"]
        if ticker not in beta_cache:
            beta_cache[ticker] = _compute_beta(ticker)

    results = []
    for scenario in SCENARIOS:
        port_impact_pct = 0.0
        for pos in positions:
            ticker = pos["ticker"]
            w = float(pos.get("weight") or 0)
            beta, n_days = beta_cache.get(ticker, (1.0, 0))
            port_impact_pct += w * beta * scenario["market_dd"] * 100

        loss_eur = total_value * (port_impact_pct / 100)
        results.append({
            "scenario":              scenario["name"],
            "period":                scenario["period"],
            "market_dd_pct":         round(scenario["market_dd"] * 100, 1),
            "portfolio_impact_pct":  round(port_impact_pct, 2),
            "estimated_loss_eur":    round(loss_eur, 2),
            "portfolio_value_eur":   round(total_value + loss_eur, 2),
        })

    # Include per-ticker betas in response so risk.html can display them
    betas_out = [
        {"ticker": t, "beta": beta_cache[t][0], "n_days": beta_cache[t][1]}
        for t in sorted(beta_cache)
    ]

    n_real = sum(1 for b in beta_cache.values() if b[1] >= 30)
    return jsonify({
        "stress_tests":    results,
        "total_value_eur": round(total_value, 2),
        "ticker_betas":    betas_out,
        "generated_at":    datetime.now().isoformat(),
        "note": (
            f"Beta computed from up to 252 trading days vs {BENCHMARK_TICKER}. "
            f"{n_real}/{len(beta_cache)} tickers have real beta (≥30 days); "
            "remainder default to 1.0."
        ),
    })


@app.route("/api/historical_returns/<ticker>")
def api_historical_returns(ticker):
    """Real historical daily returns for a ticker from the prices table.
    Replaces any JS-synthesised return data."""
    ticker = ticker.upper()
    limit  = int(request.args.get("limit", 252))
    rows = _q("""
        SELECT date,
               adj_close,
               (adj_close / LAG(adj_close) OVER (ORDER BY date)) - 1 AS daily_return
        FROM prices
        WHERE ticker = :t
        ORDER BY date DESC
        LIMIT :lim
    """, {"t": ticker, "lim": limit + 1})

    # Drop first row (no prior close for return calculation)
    rows = [r for r in rows if r.get("daily_return") is not None]
    # Return chronological order
    rows = list(reversed(rows))

    if not rows:
        return jsonify({"error": f"No price data found for {ticker}"}), 404

    returns    = [round(float(r["daily_return"]) * 100, 4) for r in rows]
    dates      = [r["date"] for r in rows]
    closes     = [round(float(r["adj_close"]), 4) for r in rows]
    vol_ann    = round(float(np.std(returns)) * np.sqrt(252), 2) if returns else 0
    cum_return = round((np.prod([1 + r/100 for r in returns]) - 1) * 100, 2) if returns else 0

    return jsonify({
        "ticker":        ticker,
        "dates":         dates,
        "daily_returns": returns,
        "adj_closes":    closes,
        "ann_vol_pct":   vol_ann,
        "cum_return_pct": cum_return,
        "n_days":        len(rows),
    })


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    start_scheduler()
    log.info("Control Tower (Flask) starting — http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
