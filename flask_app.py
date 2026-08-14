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

import sys, os, json, logging, tempfile, shutil, secrets
from functools import wraps
from pathlib import Path
import yfinance as yf
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler


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

_DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")

def require_auth(f):
    """Simple token auth for write endpoints. Dev mode (no DASHBOARD_SECRET set) stays open."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _DASHBOARD_SECRET:
            return f(*args, **kwargs)
        token = (
            request.headers.get("X-Dashboard-Token") or
            request.args.get("token") or
            (request.get_json(silent=True) or {}).get("token")
        )
        if not secrets.compare_digest(token or "", _DASHBOARD_SECRET):
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ── inject ticker names into all templates ────────────────────────────────────
@app.context_processor
def inject_metadata():
    from portfolio.src.config import TICKER_NAMES, TICKER_SECTORS, ASSET_UNIVERSE
    return dict(
        ticker_names=TICKER_NAMES, 
        ticker_sectors=TICKER_SECTORS, 
        asset_universe=ASSET_UNIVERSE,
        sandbox_mode=(os.getenv("SANDBOX_MODE") == "1")
    )

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
            
            # PERMANENT FIX: Save to DB for ML and future loads
            _persist_single_price(ticker, price, curr)
            
            return price, curr, datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        log.warning(f"Live fallback failed for {ticker}: {e}")
    return None, "EUR", None



def _persist_single_price(ticker, price, currency):
    """Save a single price point to DB so ML and future loads can use it."""
    try:
        from sqlalchemy import text
        _q_execute("""
            INSERT INTO prices (date, ticker, open, high, low, close, volume, adj_close, currency, source)
            VALUES (CURRENT_DATE, :t, :p, :p, :p, :p, 0, :p, :c, 'live_fallback')
            ON CONFLICT (date, ticker) DO UPDATE SET
                adj_close = EXCLUDED.adj_close,
                source    = 'live_fallback'
        """, {"t": ticker, "p": price, "c": currency})
        log.info(f"Persisted live price for {ticker} to DB.")
    except Exception as e:
        log.warning(f"Failed to persist live price for {ticker}: {e}")


def _append_to_ledger_csv(trade_date, action, ticker, qty, price, total, notes):
    """Append a single trade row to portfolio/data/ledger.csv to keep it in sync with SQL."""
    try:
        ledger_path = ROOT / "portfolio" / "data" / "ledger.csv"
        # Ensure directory exists
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Format values for CSV (handle None/NaN)
        s_qty = f"{qty}" if qty is not None else ""
        s_price = f"{price}" if price is not None else ""
        s_total = f"{total}" if total is not None else ""
        
        # Create the row string
        row = f"{trade_date},{action},{ticker},{s_qty},{s_price},{s_total},{notes}\n"
        
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(row)
        log.info(f"Successfully synced trade to {ledger_path.name}")
    except Exception as e:
        log.error(f"Failed to sync trade to ledger.csv: {e}")


def _q_execute(sql, params=None):
    """Helper for write operations."""
    session = get_session()
    try:
        session.execute(text(sql), params or {})
        session.commit()
    finally:
        session.close()


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
            SELECT p.ticker, p.adj_close AS price, p.currency, p.date
            FROM prices p
            INNER JOIN (
                SELECT ticker, MAX(date) AS md FROM prices
                WHERE ticker IN ({tickers_sql})
                GROUP BY ticker
            ) l ON p.ticker = l.ticker AND p.date = l.md
        """)
        # Store as (price, currency)
        price_map = {r["ticker"]: (float(r["price"] or 0.0), r.get("currency") or "EUR", r["date"]) for r in price_rows}

        usd_eur = _get_latest_fx_rate("USDEUR")
        gbp_eur = _get_latest_fx_rate("GBPEUR")

        for ticker, qty in qty_map.items():
            price_data = price_map.get(ticker)
            if not price_data:
                # DB MISSING — try live fetch from yfinance
                log.info(f"Price missing for {ticker} in DB — attempting live fallback.")
                price_data = _get_live_price_fallback(ticker)
                
            raw_price, curr, price_date = price_data

            # Apply dynamic conversion if not EUR
            price = raw_price
            if price is not None:
                if curr == "USD":
                    price = raw_price * usd_eur
                elif curr == "GBP":
                    price = raw_price * gbp_eur
            
            # The "Staleness Check": 3 days (approx 72h)
            is_stale = False
            if price_date:
                try:
                    p_dt = datetime.strptime(price_date, "%Y-%m-%d").date()
                    if (date.today() - p_dt).days > 3:
                        is_stale = True
                except: pass

            has_price = price is not None and price > 0
            value_eur = round(qty * price, 4) if has_price else None
            positions.append({
                "ticker":      ticker,
                "quantity":    round(qty, 6),
                "price":       round(price, 4) if has_price else None,
                "value_eur":   value_eur,
                "weight":      0.0,
                "price_missing": not has_price,
                "is_stale":    is_stale,
                "price_date":  price_date,
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
    rng = np.random.default_rng()  # H2 fix: no fixed seed — genuine MC variation for portfolio VaR/CVaR
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
    """Background task — runs the unified engine pipeline (engine/scheduler.py).

    Replaces the old subprocess call to portfolio/recalculate_engine.py (legacy
    CSV→JSON path that the dashboard never read). The modern scheduler writes
    everything to engine_data.db and shared/state/*.json which the dashboard
    reads exclusively.
    """
    try:
        log.info("⏰ [SCHEDULED REFRESH] Starting unified pipeline via engine.scheduler...")
        from engine.scheduler import run_pipeline
        run_pipeline(dry_run=False)
        log.info("✅ [SCHEDULED REFRESH] Unified pipeline complete.")
    except Exception as e:
        log.error(f"❌ [SCHEDULED REFRESH] Pipeline error: {e}")


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

@app.route("/legal")
def legal():
    return render_template("legal.html")


@app.route("/settings")
def settings():
    from engine.portfolio.tax_rates import JURISDICTION_PRESETS, get_tax_settings
    tax = get_tax_settings()
    return render_template(
        "settings.html", page="settings",
        tax=tax, jurisdictions=JURISDICTION_PRESETS,
    )


@app.route("/api/tax_settings", methods=["GET"])
def api_tax_settings_get():
    from engine.portfolio.tax_rates import get_tax_settings
    return jsonify(get_tax_settings())


@app.route("/api/tax_settings", methods=["POST"])
@require_auth
def api_tax_settings_post():
    from engine.portfolio.tax_rates import set_tax_jurisdiction
    data = request.get_json() or {}
    jurisdiction = data.get("jurisdiction")
    custom_rate = data.get("custom_rate")
    if custom_rate is not None:
        try:
            custom_rate = float(custom_rate) / 100.0   # UI sends a percent, e.g. 26.375
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "custom_rate must be a number"}), 400
    try:
        result = set_tax_jurisdiction(jurisdiction, custom_rate)
        return jsonify({"ok": True, **result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


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

    # Live Reconstruction — so MC updates instantly after a trade
    positions, _ = _live_positions()
    
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


@app.route("/laggards")
def laggards():
    """J7 — sector rotation laggard screen results (most recent weekly run)."""
    rows = _q("""
        SELECT ticker, sector, period_return, relative_rank, peer_median_return,
               catch_up_gap, conviction, disqualifiers, screen_date
        FROM laggard_screen_results
        WHERE screen_date = (SELECT MAX(screen_date) FROM laggard_screen_results)
        ORDER BY catch_up_gap DESC
    """)
    import json as _json
    for r in rows:
        try:
            r['disqualifiers'] = _json.loads(r.get('disqualifiers') or '[]')
        except Exception:
            r['disqualifiers'] = []
    return render_template("laggards.html",
        rows=rows,
        page="laggards",
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
    # Overlay AUC from ml_state so the frontend can compute conviction / gate by AUC
    ml = _load_json(ML_STATE_PATH)
    ml_signals = ml.get("model_signals", {}) or {}
    for row in data:
        sig = ml_signals.get(row["ticker"]) or {}
        row["auc"] = sig.get("auc")
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

    rng = np.random.default_rng(42)   # kept for chart reproducibility (per-ticker histogram)
    n   = 50_000                      # H2 fix: smoother histogram, was 10_000
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
    region = request.args.get('region', 'US').upper()
    data = _load_json(REGIME_STATE_PATH)
    try:
        # Load the history for the selected region
        history = _q("SELECT * FROM regime_history WHERE region = :r ORDER BY date DESC LIMIT 90", {"r": region})
        data['history'] = history
        
        # If the history has a recent entry, use it to override the snapshot's regime
        if history:
            latest = history[0]
            data['regime_risk'] = latest.get('regime_risk')
            data['regime_rates'] = latest.get('regime_rates')
            data['regime_growth'] = latest.get('regime_growth')
            data['regime_composite'] = latest.get('regime_composite')
            data['as_of_date'] = latest.get('date')
            data['macro_snapshot'] = {
                'vix': latest.get('vix'),
                'yield_spread': latest.get('yield_spread'),
                'hy_spread': latest.get('hy_spread'),
                'ig_spread': latest.get('ig_spread'),
                'fed_funds': latest.get('fed_funds')
            }
            
    except Exception as e:
        log.error(f"Failed to load regime history for {region}: {e}")
        data['history'] = []
    
    data['region'] = region
    return jsonify(data)


@app.route("/api/portfolio_mc")
def api_portfolio_mc():
    # Use live reconstruction for instant feedback after trading
    positions, _ = _live_positions()
    
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
    rng = np.random.default_rng()  # H2 fix: no fixed seed — genuine MC variation
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


def _get_single_mc_summary(ticker, n_paths=5000):
    """Helper to run a quick MC and return key metrics (no full histogram)."""
    rows = _q("""
        SELECT up_proba, vol_ann, current_price_eur
        FROM price_targets
        WHERE ticker = :t
        AND date = (SELECT MAX(date) FROM price_targets WHERE ticker = :t)
    """, {"t": ticker})
    if not rows:
        return None
    
    r = rows[0]
    cur   = float(r["current_price_eur"] or 0)
    up_p  = float(r["up_proba"] or 0.5)
    vol   = float(r["vol_ann"] or 0.25)
    t_val = 21 / 252
    edge  = (up_p - 0.5) * 2
    drift = edge * vol * t_val
    sigma = vol * np.sqrt(t_val)

    rng = np.random.default_rng()
    sim_ret = rng.normal(drift, sigma, n_paths)
    sim_prices = cur * np.exp(sim_ret)

    var5  = float(np.percentile(sim_prices, 5))
    p_profit = float(np.mean(sim_prices > cur) * 100)
    exp_21d  = float(np.mean(sim_prices))

    return {
        "ticker": ticker,
        "current": round(cur, 2),
        "expected": round(exp_21d, 2),
        "var5": round(var5, 2),
        "var5_pct": round((var5/cur - 1)*100, 2) if cur > 0 else 0,
        "win_prob": round(p_profit, 1),
        "exp_ret_pct": round((exp_21d/cur - 1)*100, 2) if cur > 0 else 0
    }


@app.route("/api/institutional_mc")
def api_institutional_mc():
    """Return MC summaries for an expanded set of benchmarks and top holdings."""
    # 1. Benchmarks (Multi-Asset Class Context)
    benchmarks = [
        "VUSA.DE",  # S&P 500
        "EXXT.DE",  # Nasdaq 100
        "DBXD.DE",  # DAX 40 (EU/Local)
        "IS04.DE",  # MSCI World (Global)
        "EGLN.DE"   # Gold (Safe Haven)
    ]
    bench_results = []
    for b in benchmarks:
        summary = _get_single_mc_summary(b)
        if summary:
            summary["type"] = "benchmark"
            bench_results.append(summary)
            
    # 2. All Portfolio Holdings (Dynamic from Ledger)
    positions, _ = _live_positions()
    pos_results = []
    for p in positions:
        ticker = p["ticker"]
        summary = _get_single_mc_summary(ticker)
        if summary:
            summary["type"] = "holding"
            pos_results.append(summary)
            
    return jsonify({
        "benchmarks": bench_results,
        "holdings": pos_results
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
@require_auth
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
@require_auth
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


@app.route("/analytics")
def analytics():
    # Use Live Reconstruction to ensure sync after trades
    positions, cash_eur = _live_positions()
    
    # Sort positions by value for the breakdown table
    positions = sorted(positions, key=lambda x: x.get('value_eur') or 0, reverse=True)

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
        INNER JOIN (
            SELECT ticker, MAX(id) AS mid 
            FROM positions_history 
            WHERE ticker=:t 
            GROUP BY ticker
        ) l ON p.id = l.mid
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
    rows = _q("SELECT cash_eur, date FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
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
    import json
    rows = _q("""
        SELECT ticker, current_weight, suggested_weight, delta_weight, bl_return, signal_breakdown
        FROM model_outputs
        WHERE date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY ABS(delta_weight) DESC
    """)
    suggestions = []
    for r in rows:
        delta = float(r.get("delta_weight") or 0)
        action = "BUY" if delta > 0.01 else "SELL" if delta < -0.01 else "HOLD"
        
        breakdown = {}
        if r.get("signal_breakdown"):
            try:
                breakdown = json.loads(r["signal_breakdown"])
            except Exception:
                pass
                
        suggestions.append({**r, "action": action, "signal_breakdown": breakdown})
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
    # Derive active windows (entries within last 7 days)
    active = _q("""
        SELECT ticker, earnings_date AS entry_date, direction, pead_setup_quality AS quality,
               surprise_pct, regime_composite
        FROM pead_setups
        WHERE earnings_date >= date('now', '-60 days')
        ORDER BY earnings_date DESC
    """)

    # Fallback to CSV if DB is empty
    if not history and PEAD_SETUPS_PATH and Path(PEAD_SETUPS_PATH).exists():
        import csv
        try:
            with open(PEAD_SETUPS_PATH, newline="", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                # Map CSV names to what frontend expects
                for r in reader:
                    r['quality'] = r.get('pead_setup_quality')
                    r['entry_date'] = r.get('entry_date')
                
                history = reader[:60]
                
                # Filter active for CSV fallback
                today = datetime.now()
                cutoff = today - timedelta(days=21)
                active = [
                    r for r in reader 
                    if r.get('entry_date') and datetime.strptime(r['entry_date'], '%Y-%m-%d') >= cutoff
                ]
        except Exception as e:
            log.warning(f"CSV fallback failed in /api/pead: {e}")

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
@require_auth
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

    # ── Auto-Sync to Ledger CSV ───────────────────────────────────────────────
    # We append the primary trade. 
    # Actions in CSV are Title Cased (Buy, Sell, Deposit, etc.)
    _append_to_ledger_csv(trade_date, action.title(), ticker, qty, price, total_eur, notes)
    
    # If there was an explicit fee, log it as a separate row in the CSV 
    # to match the user's manual ledger style.
    if fee_eur > 0:
        _append_to_ledger_csv(trade_date, "Fee", "CASH", None, None, fee_eur, f"Fee for {action} {ticker}")

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


@app.route("/api/sync_ledger", methods=["POST"])
@require_auth
def api_sync_ledger():
    """Manual trigger to re-import the ledger.csv into the DB."""
    try:
        from engine.reconciliation.ledger_importer import run_ledger_import
        run_ledger_import()
        return jsonify({"ok": True, "message": "Ledger re-imported successfully."})
    except Exception as e:
        log.error(f"Sync failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


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
    # WORKFLOW-AWARE FIX: Sum both standalone FEE rows and fees integrated into trade rows
    # For FEE actions, total_eur is the fee. For other actions, use explicit fee_eur column.
    total_fees = 0
    for t in trades_rows:
        act = (t.get("action") or "").upper()
        v_eur = float(t.get("total_eur") or 0)
        f_eur = float(t.get("fee_eur") or 0)
        
        if act == "FEE":
            row_fee = v_eur
        else:
            row_fee = f_eur
            
        if row_fee != 0:
            total_fees += row_fee
    
    log.debug(f"Fee calculation: total_fees={total_fees:.2f} from {len(trades_rows)} rows")

    # ── 3. Current portfolio state ────────────────────────────────────────
    positions = _q("""
        SELECT p.ticker, p.value_eur, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(id) AS mid
            FROM positions_history
            WHERE date = (SELECT MAX(date) FROM positions_history)
            GROUP BY ticker
        ) l ON p.id = l.mid
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

    # ── 5. Daily return series adjusted for cash flows ────────────────────
    # Map daily flows: net impact of DEPOSIT, DIVIDEND, FEE, etc.
    flows_by_date = {}
    for t in trades_rows:
        dt = t["date"]
        val = float(t.get("total_eur") or 0)
        action = t["action"].upper()
        
        # Flows that increase balance without being "investment return"
        # Deposits and dividends (if treated as cash injection)
        if action == "DEPOSIT":
            flows_by_date[dt] = flows_by_date.get(dt, 0.0) + val
        elif action == "DIVIDEND":
            # Dividends are profit, but we don't want them to spike the day's % 
            # if they just arrived in cash. However, for TWR, dividends ARE return.
            # We'll treat them as internal growth (no flow adjustment).
            pass
        elif action == "WITHDRAWAL":
            flows_by_date[dt] = flows_by_date.get(dt, 0.0) - val
        elif action == "FEE":
            # Fees are a cost, we subtract them from flow so they count as loss
            flows_by_date[dt] = flows_by_date.get(dt, 0.0) - val

    perf_rows = _q("""
        SELECT date, portfolio_value_eur, benchmark_value_eur, daily_return_pct
        FROM performance_history
        ORDER BY date ASC
    """)

    daily_returns = []   # list of {date, r}
    equity_series = []   # list of {date, value}
    benchmark_series = []   # I5: list of {date, value}

    if perf_rows:
        for row in perf_rows:
            r = row.get("daily_return_pct")
            v = row.get("portfolio_value_eur")
            b = row.get("benchmark_value_eur")
            if r is not None and v is not None:
                # Use a sanity cap for production safety
                r_val = float(r) / 100
                r_val = max(-0.999, min(r_val, 1.0)) # Cap at -100% to +100%
                daily_returns.append({"date": row["date"], "r": r_val})
                equity_series.append({"date": row["date"], "value": float(v)})
            if b is not None:
                benchmark_series.append({"date": row["date"], "value": float(b)})
    else:
        # Reconstruct from cash_history with flow adjustment
        cash_hist = _q("SELECT date, cash_eur FROM cash_history ORDER BY date ASC")
        cash_by_date = {}
        for row in cash_hist:
            cash_by_date[row["date"]] = float(row["cash_eur"])

        dates_sorted = sorted(cash_by_date.keys())
        prev_val = None
        for d in dates_sorted:
            val = cash_by_date[d]
            flow = flows_by_date.get(d, 0.0)
            
            if prev_val is not None and prev_val > 0:
                # Adjusted Return = (Ending Value - Cash Flow - Starting Value) / Starting Value
                r = (val - flow - prev_val) / prev_val
                # Sanity check: cap extreme outliers from data glitches
                r = max(-0.99, min(r, 1.0)) 
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

    # I5: Active Share — rough proxy using ETF weight in the current portfolio
    try:
        from portfolio.src.config import ETF_TICKERS, BENCHMARK_TICKER
        etf_weight = sum(float(p.get("weight") or 0) for p in positions if p.get("ticker") in ETF_TICKERS)
        kpis["active_share_pct"] = round((1 - etf_weight) * 100, 1)
        kpis["benchmark_ticker"] = BENCHMARK_TICKER
    except Exception as e:
        logger.warning(f"Active share calc failed: {e}")

    resp = jsonify({
        "kpis":              kpis,
        "daily_returns":     daily_returns,    # [{date, r}]
        "equity_series":     equity_series,    # [{date, value}]
        "benchmark_series":  benchmark_series, # I5: [{date, value}]
        "ledger":            trades_rows,       # raw trades for ledger table
        "generated_at":      datetime.now().isoformat(),
    })
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/mpt_weights")
def api_mpt_weights():
    """MPT optimal weights from latest model_outputs, vs live current holdings."""
    model_rows = _q("""
        SELECT ticker, suggested_weight, delta_weight, expected_return, bl_return
        FROM model_outputs
        WHERE date = (SELECT MAX(date) FROM model_outputs)
        ORDER BY suggested_weight DESC
    """)
    
    # Get ground-truth live positions
    live_positions, cash_eur = _live_positions()
    live_weights = {p["ticker"]: p["weight"] for p in live_positions}
    live_values  = {p["ticker"]: p["value_eur"] for p in live_positions}

    result = []
    for row in model_rows:
        t = row["ticker"]
        cur_w = live_weights.get(t, 0.0)
        opt_w = row["suggested_weight"] or 0.0
        
        result.append({
            "ticker":           t,
            "current_weight":   cur_w,
            "optimal_weight":   opt_w,
            "delta":            opt_w - cur_w,
            "expected_return":  row.get("expected_return"),
            "bl_return":        row.get("bl_return"),
            "value_eur":        live_values.get(t),
        })
    
    # Add any held tickers that aren't in the model (the "excess" holdings)
    model_tickers = {r["ticker"] for r in model_rows}
    for t, w in live_weights.items():
        if t not in model_tickers:
            result.append({
                "ticker": t,
                "current_weight": w,
                "optimal_weight": 0.0,
                "delta": -w,
                "expected_return": 0,
                "bl_return": 0,
                "value_eur": live_values.get(t),
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


@app.route("/api/circuit_breakers")
def api_circuit_breakers():
    """
    Recent circuit breaker events (last 7 days).
    Used by overview.html to display a prominent red emergency banner.
    Returns {events: [...], any_active: bool}.
    """
    rows = _q("""
        SELECT date, ticker, detail, logged_at
        FROM risk_events
        WHERE event_type = 'circuit_breaker'
          AND date >= date('now', '-7 days')
        ORDER BY logged_at DESC
        LIMIT 20
    """)
    return jsonify({
        "events":     rows,
        "any_active": len(rows) > 0,
        "count":      len(rows),
    })


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
            SELECT ticker, MAX(id) AS mid
            FROM positions_history
            WHERE date = (SELECT MAX(date) FROM positions_history)
            GROUP BY ticker
        ) l ON p.id = l.mid
    """)
    cash_row = _q("SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1")
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
# PAIRS / STAT ARB ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/pairs")
def pairs_page():
    return render_template("pairs.html", page="pairs",
                           now=datetime.now().strftime("%Y-%m-%d %H:%M"))

@app.route("/api/pairs/correlation")
def api_pairs_correlation():
    """
    Compute 60-day rolling correlation matrix for the top N tickers
    that have the most data in the prices table.
    Returns: { tickers: [...], matrix: [[...], ...] }
    """
    try:
        from portfolio.src.config import TRADEABLE_UNIVERSE, TICKER_NAMES

        # Find which tickers actually have enough price rows in the DB
        rows = _q("""
            SELECT ticker, COUNT(*) as cnt
            FROM prices
            WHERE ticker IN (%s)
              AND date >= date('now', '-90 days')
            GROUP BY ticker
            HAVING COUNT(*) >= 30
            ORDER BY cnt DESC
            LIMIT 15
        """ % ','.join(f"'{t}'" for t in TRADEABLE_UNIVERSE))

        if not rows:
            return jsonify({"error": "Not enough price data in DB for heatmap."})

        tickers = [r["ticker"] for r in rows]

        # Fetch 60 days of adj_close for these tickers
        price_rows = _q("""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE ticker IN (%s)
              AND date >= date('now', '-70 days')
            ORDER BY date ASC
        """ % ','.join(f"'{t}'" for t in tickers))

        if not price_rows:
            return jsonify({"error": "No price rows found."})

        df = pd.DataFrame(price_rows)
        df['adj_close'] = pd.to_numeric(df['adj_close'], errors='coerce')
        pivot = df.pivot_table(index='date', columns='ticker', values='adj_close')
        pivot = pivot[tickers]  # keep order
        returns = pivot.pct_change().dropna(how='all')
        corr = returns.corr()

        # Build clean short labels for display
        short_labels = [t.replace('.DE','').replace('.AS','').replace('.BR','') for t in tickers]
        matrix = []
        for t in tickers:
            row = []
            for t2 in tickers:
                v = corr.at[t, t2] if (t in corr.index and t2 in corr.columns) else None
                row.append(round(float(v), 3) if v is not None and not np.isnan(v) else None)
            matrix.append(row)

        return jsonify({
            "tickers": short_labels,
            "full_tickers": tickers,
            "matrix": matrix,
            "n_days": len(returns),
        })
    except Exception as e:
        log.exception("pairs correlation error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/pairs/scan")
def api_pairs_scan():
    """
    Run Engle-Granger cointegration test on a dynamic set of pairs.
    Includes curated same-sector pairs PLUS any highly correlated pairs 
    discovered from the top 100 active tickers.
    """
    try:
        from statsmodels.tsa.stattools import coint
        from portfolio.src.config import TRADEABLE_UNIVERSE, TICKER_NAMES, TICKER_SECTORS, TICKER_MAPPING

        # 1. Curated same-sector candidate pairs (Base list)
        CANDIDATE_PAIRS = [
            ('NVD.DE', 'AMD.DE'), ('INZ.DE', 'QCI.DE'), ('MTH.DE', 'AMD.DE'), ('TSFA.DE', 'NVD.DE'),
            ('MSF.DE', 'ORC.DE'), ('CAS.DE', '6N0.DE'), ('ADB.DE', 'CAS.DE'),
            ('CMC.DE', 'NCB.DE'), ('GOS.DE', 'M9N.DE'), ('3V64.DE', 'M9Z.DE'),
            ('APC.DE', 'MSF.DE'), ('AMZ.DE', 'ABE.DE'), ('NFC.DE', '6SP.DE'),
            ('SAP.DE', 'ORC.DE'), ('IFX.DE', 'INZ.DE'), ('ADS.DE', 'NKE'),
        ]
        
        # 2. DYNAMIC DISCOVERY: Find top 100 tickers by activity
        active_tickers_rows = _q("""
            SELECT ticker, COUNT(*) as cnt FROM prices
            WHERE ticker IN (%s) AND date >= date('now', '-120 days')
            GROUP BY ticker HAVING COUNT(*) >= 20
            ORDER BY cnt DESC LIMIT 100
        """ % ','.join(f"'{t}'" for t in TRADEABLE_UNIVERSE))
        
        active_tickers = [r["ticker"] for r in active_tickers_rows]
        
        # 3. Resolve curated tickers based on actual DB presence
        db_tickers_set = set(active_tickers)
        def resolve(t):
            if t in db_tickers_set: return t
            mapped = TICKER_MAPPING.get(t)
            if mapped and mapped in db_tickers_set: return mapped
            # Reverse lookup
            for k, v in TICKER_MAPPING.items():
                if v == t and k in db_tickers_set: return k
            return t

        normalized_curated = []
        for (ta, tb) in CANDIDATE_PAIRS:
            normalized_curated.append((resolve(ta), resolve(tb)))

        # 4. Fetch price data for ALL candidate and active tickers
        all_needed = set(active_tickers)
        for (ta, tb) in normalized_curated:
            all_needed.add(ta); all_needed.add(tb)
 
        price_rows = _q("""
            SELECT date, ticker, adj_close FROM prices
            WHERE ticker IN (%s) AND date >= date('now', '-400 days')
            ORDER BY date ASC
        """ % ','.join(f"'{t}'" for t in all_needed))
 
        if not price_rows:
            return jsonify({"error": "No price data available."})
 
        df = pd.DataFrame(price_rows)
        df['adj_close'] = pd.to_numeric(df['adj_close'], errors='coerce')
        pivot = df.pivot_table(index='date', columns='ticker', values='adj_close')
 
        # 5. Filter for high correlation pairs within the active set
        dynamic_pairs = set(tuple(sorted(p)) for p in normalized_curated)
        if len(active_tickers) >= 2:
            subset = pivot[active_tickers].tail(90)
            returns_60 = subset.pct_change().dropna(how='all')
            corr_matrix = returns_60.corr()
            
            for i in range(len(active_tickers)):
                for j in range(i + 1, len(active_tickers)):
                    ta, tb = active_tickers[i], active_tickers[j]
                    if ta in corr_matrix.index and tb in corr_matrix.columns:
                        c_val = corr_matrix.at[ta, tb]
                        if not np.isnan(c_val) and c_val > 0.60: 
                            dynamic_pairs.add(tuple(sorted((ta, tb))))
 
        # 6. Run tests on the combined set
        results = []
        for (ta, tb) in dynamic_pairs:
            if ta == tb: continue
            if ta not in pivot.columns or tb not in pivot.columns: continue
            series = pivot[[ta, tb]].dropna()
            if len(series) < 60: continue
 
            xa, xb = series[ta].values, series[tb].values
            corr_val = float(np.corrcoef(xa, xb)[0, 1])
            if np.isnan(corr_val): continue

            try:
                _, pvalue, _ = coint(xa, xb)
                pvalue = float(pvalue)
            except: pvalue = 1.0

            beta = float(np.linalg.lstsq(np.column_stack([np.ones(len(xb)), xb]), xa, rcond=None)[0][1])
            spread = xa - beta * xb
            
            # CONSISTENCY FIX: Use Rolling 60-day Z-score (matching the chart)
            s_series = pd.Series(spread)
            roll_mean = s_series.rolling(60, min_periods=20).mean().iloc[-1]
            roll_std  = s_series.rolling(60, min_periods=20).std().iloc[-1]
            
            if not np.isnan(roll_std) and roll_std > 1e-10:
                zscore = float((spread[-1] - roll_mean) / roll_std)
            else:
                # Fallback to global if rolling window is too short or invalid
                zscore = float((spread[-1] - np.mean(spread)) / np.std(spread)) if np.std(spread) > 1e-10 else 0.0

            try:
                spread_lag, spread_diff = spread[:-1], np.diff(spread)
                beta_ar = float(np.linalg.lstsq(np.column_stack([np.ones(len(spread_lag)), spread_lag]), spread_diff, rcond=None)[0][1])
                half_life = int(round(-np.log(2) / beta_ar)) if beta_ar < 0 else None
            except: half_life = None

            if pvalue < 0.05: status = 'COINTEGRATED'
            elif pvalue < 0.15: status = 'WATCHING'
            else: status = 'DRIFTING'

            signal = 'NEUTRAL'
            if abs(zscore) >= 2.0: signal = 'LONG_B' if zscore > 0 else 'LONG_A'

            s_a, s_b = TICKER_SECTORS.get(ta, '—'), TICKER_SECTORS.get(tb, '—')
            results.append({
                'ticker_a': ta, 'ticker_b': tb,
                'label_a': ta.replace('.DE','').replace('.AS',''), 'label_b': tb.replace('.DE','').replace('.AS',''),
                'sector': s_a if s_a == s_b else f"{s_a}/{s_b}",
                'correlation': round(corr_val, 3), 'pvalue': round(pvalue, 4), 'zscore': round(zscore, 3),
                'status': status, 'signal': signal, 'half_life': half_life,
            })

        results.sort(key=lambda r: (-abs(r['zscore']), r['pvalue']))
        return jsonify({'pairs': results})
    except Exception as e:
        log.exception("pairs scan error")
        return jsonify({'error': str(e)}), 500

    except ImportError:
        return jsonify({'error': 'statsmodels not installed. Run: pip install statsmodels'}), 500
    except Exception as e:
        log.exception("pairs scan error")
        return jsonify({'error': str(e)}), 500


@app.route("/api/pairs/spread/<ta>/<tb>")
def api_pairs_spread(ta, tb):
    """
    Return the full historical spread z-score series for a pair.
    Used by the Spread Chart on the pairs page.
    """
    try:
        from portfolio.src.config import TICKER_NAMES

        price_rows = _q("""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE ticker IN (:ta, :tb)
              AND date >= date('now', '-380 days')
            ORDER BY date ASC
        """, {'ta': ta, 'tb': tb})

        if not price_rows:
            return jsonify({'error': f'No price data found for {ta} or {tb}.'})

        df = pd.DataFrame(price_rows)
        df['adj_close'] = pd.to_numeric(df['adj_close'], errors='coerce')
        pivot = df.pivot_table(index='date', columns='ticker', values='adj_close')

        if ta not in pivot.columns or tb not in pivot.columns:
            return jsonify({'error': f'Insufficient data for {ta}/{tb} in DB.'})

        series = pivot[[ta, tb]].dropna()
        if len(series) < 30:
            return jsonify({'error': f'Not enough overlapping data for {ta}/{tb} (need 30 days, got {len(series)}).'})

        xa = series[ta].values
        xb = series[tb].values

        # OLS hedge ratio
        beta = float(np.linalg.lstsq(np.column_stack([np.ones(len(xb)), xb]), xa, rcond=None)[0][1])

        # Spread z-score (rolling 60-day params for stationarity)
        spread = xa - beta * xb
        roll_mean = pd.Series(spread).rolling(60, min_periods=20).mean().values
        roll_std  = pd.Series(spread).rolling(60, min_periods=20).std().values
        zscores   = np.where(roll_std > 1e-10, (spread - roll_mean) / roll_std, 0.0)

        # Half-life
        try:
            spread_lag  = spread[:-1]
            spread_diff = np.diff(spread)
            beta_ar = float(np.linalg.lstsq(
                np.column_stack([np.ones(len(spread_lag)), spread_lag]),
                spread_diff, rcond=None
            )[0][1])
            half_life = int(round(-np.log(2) / beta_ar)) if beta_ar < 0 else None
            if half_life and (half_life < 1 or half_life > 252):
                half_life = None
        except Exception:
            half_life = None

        z_now  = float(zscores[-1]) if not np.isnan(zscores[-1]) else 0.0
        signal = 'NEUTRAL'
        if abs(z_now) >= 2.0:
            signal = 'LONG_B' if z_now > 0 else 'LONG_A'

        label_a = ta.replace('.DE','').replace('.AS','').replace('.BR','')
        label_b = tb.replace('.DE','').replace('.AS','').replace('.BR','')

        return jsonify({
            'ticker_a':     ta,
            'ticker_b':     tb,
            'label_a':      label_a,
            'label_b':      label_b,
            'dates':        list(series.index.astype(str)),
            'zscores':      [round(float(z), 4) if not np.isnan(z) else None for z in zscores],
            'current_zscore': round(z_now, 4),
            'spread_mean':  round(float(np.mean(spread)), 6),
            'hedge_ratio':  round(beta, 4),
            'half_life':    half_life,
            'signal':       signal,
            'n_days':       len(series),
        })

    except Exception as e:
        log.exception("pairs spread error")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO LAB
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/lab")
def lab():
    from portfolio.src.config import ASSET_UNIVERSE, TICKER_NAMES, TICKER_SECTORS
    # Pre-populate with current live holdings so the user can optimise what they own
    positions, _ = _live_positions()
    live_tickers = [p["ticker"] for p in positions if p.get("value_eur")]

    # Build sector-grouped universe for the picker
    sector_groups = {}
    for t in sorted(ASSET_UNIVERSE):
        s = TICKER_SECTORS.get(t, "Other")
        sector_groups.setdefault(s, []).append(t)

    return render_template("lab.html",
        sector_groups=sector_groups,
        live_tickers=live_tickers,
        page="lab",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/lab/optimize", methods=["POST"])
def api_lab_optimize():
    """
    On-demand portfolio optimizer for the Portfolio Lab tab.

    Body (JSON):
      tickers            list[str]   required, 2–30 items
      objective          str         max_sharpe | min_vol | risk_parity | equal_weight | max_return
      lookback_days      int         default 504
      portfolio_size_eur float       default 10000
      min_weight         float       default 0.0
      max_weight         float       default 0.40
    """
    data = request.get_json(force=True) or {}
    tickers    = [t.strip().upper() for t in (data.get("tickers") or []) if t.strip()]
    objective  = data.get("objective", "max_sharpe")
    lookback   = int(data.get("lookback_days", 504))
    port_size  = float(data.get("portfolio_size_eur", 10_000))
    min_w      = float(data.get("min_weight", 0.0))
    max_w      = float(data.get("max_weight", 0.40))

    if len(tickers) < 2:
        return jsonify({"error": "Select at least 2 tickers"}), 400
    if len(tickers) > 30:
        return jsonify({"error": "Maximum 30 tickers per run"}), 400
    if objective not in ("max_sharpe", "min_vol", "risk_parity", "equal_weight", "max_return"):
        return jsonify({"error": f"Unknown objective: {objective}"}), 400
    if not (0.0 <= min_w < max_w <= 1.0):
        return jsonify({"error": "Invalid weight bounds"}), 400

    try:
        from engine.portfolio.lab_optimizer import run_lab_optimization
        result = run_lab_optimization(
            tickers=tickers,
            objective=objective,
            lookback_days=lookback,
            portfolio_size_eur=port_size,
            min_weight=min_w,
            max_weight=max_w,
        )
        return jsonify(result)
    except Exception as e:
        log.exception("Lab optimizer error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/lab/save_portfolio", methods=["POST"])
def api_lab_save_portfolio():
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    tickers = data.get("tickers", [])
    weights = data.get("weights", {})
    objective = data.get("objective", "")
    metrics = data.get("metrics", {})

    if not name:
        return jsonify({"error": "Portfolio name is required"}), 400
    if not tickers or not weights:
        return jsonify({"error": "No portfolio data to save"}), 400

    try:
        _exec("""
            INSERT INTO saved_portfolios (name, tickers, weights, objective, metrics)
            VALUES (:name, :tickers, :weights, :objective, :metrics)
        """, {
            "name": name,
            "tickers": json.dumps(tickers),
            "weights": json.dumps(weights),
            "objective": objective,
            "metrics": json.dumps(metrics)
        })
        return jsonify({"ok": True, "message": f"Portfolio '{name}' saved successfully!"})
    except Exception as e:
        log.exception("Error saving portfolio")
        return jsonify({"error": str(e)}), 500


@app.route("/api/lab/saved_portfolios", methods=["GET"])
def api_lab_saved_portfolios():
    try:
        rows = _q("""
            SELECT id, name, tickers, weights, objective, metrics, saved_at
            FROM saved_portfolios
            ORDER BY saved_at DESC
        """)
        # Parse JSON fields
        for row in rows:
            row["tickers"] = json.loads(row["tickers"]) if row["tickers"] else []
            row["weights"] = json.loads(row["weights"]) if row["weights"] else {}
            row["metrics"] = json.loads(row["metrics"]) if row["metrics"] else {}
        return jsonify({"portfolios": rows})
    except Exception as e:
        log.exception("Error loading saved portfolios")
        return jsonify({"error": str(e)}), 500


@app.route("/api/lab/delete_portfolio/<int:pid>", methods=["DELETE"])
def api_lab_delete_portfolio(pid):
    try:
        success = _exec("DELETE FROM saved_portfolios WHERE id = :pid", {"pid": pid})
        if not success:
            return jsonify({"error": "Database deletion failed"}), 500
        return jsonify({"ok": True})
    except Exception as e:
        log.exception("Error deleting portfolio")
        return jsonify({"error": str(e)}), 500



# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL QUEUE — DB INIT
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_signal_queue_table():
    """Create the signal_queue table if it doesn't exist yet."""
    _exec("""
        CREATE TABLE IF NOT EXISTS signal_queue (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at     TEXT DEFAULT (datetime('now')),
            ticker           TEXT NOT NULL,
            signal_type      TEXT,
            conviction       REAL,
            short_score      REAL,
            up_proba         REAL,
            auc              REAL,
            rr_ratio         REAL,
            current_price    REAL,
            target_price     REAL,
            stop_price       REAL,
            vol_ann          REAL,
            expires_at       TEXT,
            status           TEXT DEFAULT 'pending',
            reviewed_at      TEXT,
            review_note      TEXT,
            reason_category  TEXT,
            source           TEXT DEFAULT 'ml'
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# HIGHLIGHTED TAB — Conviction Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _compute_conviction_scores():
    """
    Build scored conviction picks from price_targets + ml_state + regime + PEAD.
    Returns (longs, shorts) — each a list of dicts sorted by score desc.
    """
    targets = _q("""
        SELECT ticker, current_price_eur, expected_21d_eur,
               target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
               support_bb_lower, resistance_ma50,
               risk_reward_ratio, up_proba, vol_ann, kelly_half, computed_at
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
    """)
    if not targets:
        return [], []

    ml    = _load_json(ML_STATE_PATH)
    reg   = _load_json(REGIME_STATE_PATH)
    ml_signals = ml.get("model_signals", {})

    # Regime multiplier
    regime_risk = (reg.get("regime_risk") or "").lower()
    regime_mult_long  = 1.2 if "risk-on"  in regime_risk else 0.8 if "risk-off" in regime_risk else 1.0
    regime_mult_short = 1.2 if "risk-off" in regime_risk else 0.7 if "risk-on"  in regime_risk else 1.0
    transition_warning = reg.get("transition_warning", False)
    regime_label = reg.get("regime_risk") or "Unknown"

    # PEAD active setups → set for quick lookup
    pead_active = _q("""
        SELECT ticker, direction, pead_setup_quality
        FROM pead_setups
        WHERE earnings_date >= date('now', '-60 days')
        ORDER BY earnings_date DESC
    """)
    pead_map = {}
    for p in pead_active:
        t = p["ticker"]
        if t not in pead_map:
            pead_map[t] = p

    longs, shorts = [], []

    for row in targets:
        ticker   = row["ticker"]
        up_proba = float(row.get("up_proba") or 0.5)
        auc      = float((ml_signals.get(ticker) or {}).get("auc") or 0)
        rr_ratio = float(row.get("risk_reward_ratio") or 0)
        vol_ann  = float(row.get("vol_ann") or 0)
        cur      = float(row.get("current_price_eur") or 0)
        tgt      = float(row.get("target_1sigma_eur") or 0)
        stop     = float(row.get("stop_1sigma_eur") or 0)
        kelly    = float(row.get("kelly_half") or 0)

        # AUC gate
        if auc < 0.53:
            continue

        # PEAD boost
        pead_info = pead_map.get(ticker)
        pead_boost = 1.0
        pead_tags  = []
        if pead_info:
            q = (pead_info.get("pead_setup_quality") or "").upper()
            d = (pead_info.get("direction") or "").lower()
            pead_boost = 1.15 if q == "HIGH" else 1.08 if q == "MEDIUM" else 1.03
            pead_tags = [f"PEAD {d.upper()}"]

        # Vol score (favour 15–40% ann)
        vol_pct = vol_ann * 100
        vol_score = 1.0
        if 15 <= vol_pct <= 40:
            vol_score = 1.1
        elif vol_pct > 60:
            vol_score = 0.8

        # ── Long conviction ────────────────────────────────────────────────
        if up_proba >= 0.54:
            conv = up_proba * auc * (1 + rr_ratio) * regime_mult_long * pead_boost * vol_score
            tags = list(pead_tags)
            if regime_mult_long > 1.0: tags.append("RISK-ON")
            if transition_warning:     tags.append("TRANSITION RISK")
            if rr_ratio >= 2.0:        tags.append("STRONG R:R")
            if up_proba >= 0.70:       tags.append("HIGH PROBA")
            conv_tier = "HIGH" if conv >= 0.70 else "MEDIUM" if conv >= 0.55 else "LOW"
            longs.append({
                "ticker":      ticker,
                "conviction":  round(conv, 4),
                "conv_tier":   conv_tier,
                "up_proba":    round(up_proba, 4),
                "auc":         round(auc, 4),
                "rr_ratio":    round(rr_ratio, 2),
                "vol_ann_pct": round(vol_pct, 1),
                "kelly_half":  round(kelly, 1),
                "current_price": round(cur, 2),
                "target_price":  round(tgt, 2),
                "stop_price":    round(stop, 2),
                "regime":      regime_label,
                "tags":        tags,
                "side":        "LONG",
                "computed_at": row.get("computed_at") or "",
            })

        # ── Short conviction ───────────────────────────────────────────────
        # Only surface in Risk-Off OR transition OR high-confidence bear OR bearish PEAD
        is_bearish_pead = pead_info and (pead_info.get("direction") or "").lower() in ("bearish", "bear")
        show_short = (
            "risk-off" in regime_risk
            or transition_warning
            or up_proba <= 0.38
            or is_bearish_pead
        )
        if up_proba <= 0.40 and show_short:
            # Derive short R:R: cover at support_bb_lower, stop at stop_tight or +1sigma
            cover = float(row.get("support_bb_lower") or 0)
            short_stop = float(row.get("resistance_ma50") or 0) or (cur * 1.05 if cur > 0 else 0)
            if cur > 0 and cover > 0 and short_stop > cur:
                rr_short = (cur - cover) / (short_stop - cur) if short_stop > cur else rr_ratio * 0.8
            else:
                rr_short = rr_ratio * 0.8
            rr_short = max(0.5, min(rr_short, 5.0))

            bear_proba = 1.0 - up_proba
            short_score = bear_proba * auc * rr_short * regime_mult_short * pead_boost

            # Inverse ETF suggestions (hardcoded lookup)
            INVERSE_ETF_MAP = {
                "tech":     "SQQQ / PSQ (Inverse Nasdaq)",
                "nasdaq":   "SQQQ / PSQ (Inverse Nasdaq)",
                "sp500":    "SH / SDS (Inverse S&P 500)",
                "dax":      "XSPS.DE / DBX4 (Inverse DAX)",
                "eu":       "XSPS.DE (Inverse EU)",
            }
            ml_sig = ml_signals.get(ticker, {})
            sector_raw = (ml_sig.get("sector") or "").lower()
            etf_hint = "SH / SDS (Inverse S&P 500)"  # default
            for key, val in INVERSE_ETF_MAP.items():
                if key in sector_raw or key in ticker.lower():
                    etf_hint = val
                    break

            stags = list(pead_tags)
            if regime_mult_short > 1.0: stags.append("RISK-OFF")
            if transition_warning:       stags.append("TRANSITION RISK")
            if bear_proba >= 0.65:       stags.append("HIGH BEAR PROBA")
            conv_tier = "HIGH" if short_score >= 0.55 else "MEDIUM" if short_score >= 0.40 else "LOW"

            shorts.append({
                "ticker":       ticker,
                "conviction":   round(short_score, 4),
                "conv_tier":    conv_tier,
                "up_proba":     round(up_proba, 4),
                "bear_proba":   round(bear_proba, 4),
                "auc":          round(auc, 4),
                "rr_ratio":     round(rr_short, 2),
                "vol_ann_pct":  round(vol_pct, 1),
                "current_price": round(cur, 2),
                "cover_price":   round(cover, 2) if cover > 0 else None,
                "stop_price":    round(short_stop, 2),
                "regime":       regime_label,
                "tags":         stags,
                "etf_hint":     etf_hint,
                "side":         "SHORT",
                "computed_at":  row.get("computed_at") or "",
            })

    longs.sort(key=lambda x: x["conviction"], reverse=True)
    shorts.sort(key=lambda x: x["conviction"], reverse=True)
    return longs[:12], shorts[:6]


@app.route("/highlighted")
def highlighted():
    regime = _load_json(REGIME_STATE_PATH)
    ages   = state_file_ages()
    return render_template("highlighted.html",
        regime=regime,
        ages=ages,
        page="highlighted",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/highlighted")
def api_highlighted():
    """Return top conviction picks (long + short) with regime context."""
    longs, shorts = _compute_conviction_scores()
    reg = _load_json(REGIME_STATE_PATH)
    return jsonify({
        "longs":   longs,
        "shorts":  shorts,
        "regime":  {
            "risk":       reg.get("regime_risk"),
            "growth":     reg.get("regime_growth"),
            "rates":      reg.get("regime_rates"),
            "composite":  reg.get("regime_composite"),
            "transition": reg.get("transition_warning", False),
        },
        "generated_at": datetime.now().isoformat(),
    })


@app.route("/api/user_state")
def api_user_state():
    """Returns tickers currently in the watchlist and pending in the queue."""
    _ensure_watchlist_table()
    _ensure_signal_queue_table()
    watched = [r["ticker"] for r in _q("SELECT ticker FROM watchlist")]
    queued  = [r["ticker"] for r in _q("SELECT ticker FROM signal_queue WHERE status = 'pending'")]
    return jsonify({
        "watched": watched,
        "queued":  queued
    })



# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL REVIEW QUEUE (HITL)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/queue")
def queue():
    regime = _load_json(REGIME_STATE_PATH)
    ages   = state_file_ages()
    return render_template("queue.html",
        regime=regime,
        ages=ages,
        page="queue",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/signal_queue", methods=["GET"])
def api_signal_queue():
    """Return pending + recently reviewed signals."""
    _ensure_signal_queue_table()
    pending = _q("""
        SELECT id, generated_at, ticker, signal_type, conviction, short_score,
               up_proba, auc, rr_ratio, current_price, target_price, stop_price,
               vol_ann, expires_at, status, source
        FROM signal_queue
        WHERE status = 'pending'
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY conviction DESC
    """)
    reviewed = _q("""
        SELECT id, reviewed_at, ticker, signal_type, conviction, status,
               review_note, reason_category, source
        FROM signal_queue
        WHERE status IN ('approved', 'skipped', 'expired')
        ORDER BY reviewed_at DESC
        LIMIT 30
    """)
    # Auto-expire old pending signals (>3 days)
    _exec("""
        UPDATE signal_queue
        SET status = 'expired', reviewed_at = datetime('now')
        WHERE status = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at <= datetime('now')
    """)
    counts = _q("""
        SELECT status, COUNT(*) AS n
        FROM signal_queue
        GROUP BY status
    """)
    counts_map = {r["status"]: r["n"] for r in counts}
    regime = _load_json(REGIME_STATE_PATH)
    return jsonify({
        "pending":  pending,
        "reviewed": reviewed,
        "counts":   counts_map,
        "regime":   {
            "risk":       regime.get("regime_risk"),
            "transition": regime.get("transition_warning", False),
        },
    })


@app.route("/api/signal_queue/add", methods=["POST"])
def api_signal_queue_add():
    """
    Add a signal to the review queue from the Highlighted tab.
    Body: {ticker, signal_type, conviction, short_score, up_proba, auc, rr_ratio,
           current_price, target_price, stop_price, vol_ann, source}
    """
    _ensure_signal_queue_table()
    data = request.get_json(force=True) or {}
    ticker = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"ok": False, "error": "ticker required"}), 400

    # Check not already pending for this ticker/signal_type
    existing = _q("""
        SELECT id FROM signal_queue
        WHERE ticker = :t AND signal_type = :st AND status = 'pending'
          AND generated_at > datetime('now', '-3 days')
    """, {"t": ticker, "st": data.get("signal_type", "BUY")})
    if existing:
        return jsonify({"ok": True, "already_exists": True, "id": existing[0]["id"]})

    expires = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    ok = _exec("""
        INSERT INTO signal_queue
            (ticker, signal_type, conviction, short_score, up_proba, auc, rr_ratio,
             current_price, target_price, stop_price, vol_ann, expires_at, source)
        VALUES
            (:ticker, :signal_type, :conviction, :short_score, :up_proba, :auc,
             :rr_ratio, :cur, :tgt, :stop, :vol, :expires, :source)
    """, {
        "ticker":      ticker,
        "signal_type": data.get("signal_type", "BUY"),
        "conviction":  data.get("conviction"),
        "short_score": data.get("short_score"),
        "up_proba":    data.get("up_proba"),
        "auc":         data.get("auc"),
        "rr_ratio":    data.get("rr_ratio"),
        "cur":         data.get("current_price"),
        "tgt":         data.get("target_price"),
        "stop":        data.get("stop_price"),
        "vol":         data.get("vol_ann"),
        "expires":     expires,
        "source":      data.get("source", "ml"),
    })
    return jsonify({"ok": ok})


@app.route("/api/signal_queue/action", methods=["POST"])
def api_signal_queue_action():
    """
    Approve or skip a signal in the queue.
    Body: {id, action: 'approve'|'skip', note, reason_category}
    """
    _ensure_signal_queue_table()
    data   = request.get_json(force=True) or {}
    sig_id = data.get("id")
    action = data.get("action", "").lower()  # 'approve' or 'skip'
    note   = data.get("note", "") or ""
    reason = data.get("reason_category", "") or ""

    if action not in ("approve", "skip"):
        return jsonify({"ok": False, "error": "action must be 'approve' or 'skip'"}), 400
    if not sig_id:
        return jsonify({"ok": False, "error": "id required"}), 400

    new_status = "approved" if action == "approve" else "skipped"
    ok = _exec("""
        UPDATE signal_queue
        SET status = :status,
            reviewed_at = datetime('now'),
            review_note = :note,
            reason_category = :reason
        WHERE id = :id AND status = 'pending'
    """, {"status": new_status, "note": note, "reason": reason, "id": int(sig_id)})
    return jsonify({"ok": ok, "new_status": new_status})


@app.route("/api/signal_queue/count")
def api_signal_queue_count():
    """Quick count of pending signals — used by nav badge."""
    _ensure_signal_queue_table()
    rows = _q("""
        SELECT COUNT(*) AS n FROM signal_queue
        WHERE status = 'pending'
          AND (expires_at IS NULL OR expires_at > datetime('now'))
    """)
    return jsonify({"pending": rows[0]["n"] if rows else 0})


# ─────────────────────────────────────────────────────────────────────────────
# WATCHLIST
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_watchlist_table():
    """Create the watchlist table if it doesn't exist yet."""
    _exec("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker           TEXT NOT NULL UNIQUE,
            added_at         TEXT DEFAULT (datetime('now')),
            notes            TEXT,
            side             TEXT DEFAULT 'LONG',   -- LONG | SHORT
            snap_up_proba    REAL,                  -- snapshot when added
            snap_conviction  REAL,                  -- snapshot when added
            snap_price       REAL,                  -- snapshot when added
            alert_threshold  REAL DEFAULT 0.70      -- auto-promote threshold
        )
    """)


def _get_watchlist_enriched():
    """
    Return all watchlist rows enriched with current signals (price_targets + ml_state).
    Computes conviction trend vs snapshot taken when ticker was added.
    Flags auto-promote if conviction >= alert_threshold.
    """
    _ensure_watchlist_table()
    rows = _q("""
        SELECT id, ticker, added_at, notes, side,
               snap_up_proba, snap_conviction, snap_price, alert_threshold
        FROM watchlist
        ORDER BY added_at DESC
    """)
    if not rows:
        return []

    tickers_sql = ",".join(f"'{r['ticker']}'" for r in rows)
    targets = _q(f"""
        SELECT ticker, current_price_eur, up_proba, vol_ann,
               risk_reward_ratio, target_1sigma_eur, stop_1sigma_eur, kelly_half
        FROM price_targets
        WHERE date = (SELECT MAX(date) FROM price_targets)
          AND ticker IN ({tickers_sql})
    """)
    targets_map = {t["ticker"]: t for t in targets}

    ml = _load_json(ML_STATE_PATH)
    ml_signals = ml.get("model_signals", {}) or {}

    reg = _load_json(REGIME_STATE_PATH)
    regime_risk = (reg.get("regime_risk") or "").lower()
    regime_mult = 1.2 if "risk-on" in regime_risk else 0.8 if "risk-off" in regime_risk else 1.0

    enriched = []
    for row in rows:
        ticker = row["ticker"]
        pt     = targets_map.get(ticker, {})
        ml_sig = ml_signals.get(ticker, {})

        up_proba = float(pt.get("up_proba") or ml_sig.get("up_proba_21d") or 0.5)
        auc      = float(ml_sig.get("auc") or 0)
        rr       = float(pt.get("risk_reward_ratio") or 0)
        vol_pct  = float(pt.get("vol_ann") or 0) * 100
        cur      = float(pt.get("current_price_eur") or row.get("snap_price") or 0)
        kelly    = float(pt.get("kelly_half") or 0)
        tgt      = float(pt.get("target_1sigma_eur") or 0)
        stp      = float(pt.get("stop_1sigma_eur") or 0)

        # Current conviction
        vol_score = 1.1 if 15 <= vol_pct <= 40 else 0.8 if vol_pct > 60 else 1.0
        cur_conv = (up_proba * auc * (1 + rr) * regime_mult * vol_score) if auc >= 0.53 else None

        # Trend vs snapshot
        snap_conv = row.get("snap_conviction")
        snap_up   = row.get("snap_up_proba")
        snap_px   = row.get("snap_price")

        if cur_conv is not None and snap_conv is not None:
            conv_delta = cur_conv - snap_conv
            trend = "IMPROVING" if conv_delta > 0.02 else "WEAKENING" if conv_delta < -0.02 else "STABLE"
        else:
            conv_delta = None
            trend = "UNKNOWN"

        up_delta = (up_proba - snap_up) if snap_up is not None else None
        px_delta_pct = ((cur - snap_px) / snap_px * 100) if snap_px and snap_px > 0 else None

        # Determine action signal
        action = "BUY" if up_proba >= 0.60 else "LEAN_BUY" if up_proba >= 0.54 \
            else "SELL" if up_proba <= 0.40 else "LEAN_SELL" if up_proba <= 0.46 else "NEUTRAL"

        # Auto-promote flag
        threshold = float(row.get("alert_threshold") or 0.70)
        auto_promote = cur_conv is not None and cur_conv >= threshold

        enriched.append({
            "id":             row["id"],
            "ticker":         ticker,
            "added_at":       row.get("added_at", ""),
            "notes":          row.get("notes", ""),
            "side":           row.get("side", "LONG"),
            "alert_threshold":threshold,
            # Current signal
            "up_proba":       round(up_proba, 4),
            "auc":            round(auc, 4),
            "rr_ratio":       round(rr, 2),
            "vol_ann_pct":    round(vol_pct, 1),
            "current_price":  round(cur, 2) if cur else None,
            "target_price":   round(tgt, 2) if tgt else None,
            "stop_price":     round(stp, 2)  if stp  else None,
            "kelly_half":     round(kelly, 1),
            "conviction":     round(cur_conv, 4) if cur_conv is not None else None,
            "action":         action,
            # Trend
            "trend":          trend,
            "conv_delta":     round(conv_delta, 4) if conv_delta is not None else None,
            "up_delta":       round(up_delta, 4)   if up_delta   is not None else None,
            "px_delta_pct":   round(px_delta_pct, 2) if px_delta_pct is not None else None,
            # Snapshot
            "snap_up_proba":  row.get("snap_up_proba"),
            "snap_conviction":row.get("snap_conviction"),
            "snap_price":     row.get("snap_price"),
            # Flags
            "auto_promote":   auto_promote,
            "auc_gated":      auc < 0.53,
        })
    return enriched


@app.route("/watchlist")
def watchlist():
    regime = _load_json(REGIME_STATE_PATH)
    ages   = state_file_ages()
    return render_template("watchlist.html",
        regime=regime,
        ages=ages,
        page="watchlist",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/watchlist", methods=["GET"])
def api_watchlist():
    """Return all watchlist entries with enriched live signals."""
    items = _get_watchlist_enriched()
    promote_count = sum(1 for i in items if i["auto_promote"])
    return jsonify({
        "items":         items,
        "total":         len(items),
        "promote_count": promote_count,
    })


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    """
    Add a ticker to the watchlist, snapshotting current signal data.
    Body: {ticker, side, notes, snap_up_proba, snap_conviction, snap_price, alert_threshold}
    """
    _ensure_watchlist_table()
    data   = request.get_json(force=True) or {}
    ticker = (data.get("ticker") or "").strip().upper()
    if not ticker:
        return jsonify({"ok": False, "error": "ticker required"}), 400

    # Upsert: if ticker already on watchlist, update the snapshot & notes
    existing = _q("SELECT id FROM watchlist WHERE ticker = :t", {"t": ticker})
    if existing:
        ok = _exec("""
            UPDATE watchlist
            SET notes            = COALESCE(:notes, notes),
                side             = :side,
                snap_up_proba    = COALESCE(:sup, snap_up_proba),
                snap_conviction  = COALESCE(:sc,  snap_conviction),
                snap_price       = COALESCE(:sp,  snap_price),
                alert_threshold  = COALESCE(:thr, alert_threshold)
            WHERE ticker = :t
        """, {
            "t":    ticker,
            "notes":data.get("notes"),
            "side": data.get("side", "LONG"),
            "sup":  data.get("snap_up_proba"),
            "sc":   data.get("snap_conviction"),
            "sp":   data.get("snap_price"),
            "thr":  data.get("alert_threshold"),
        })
        return jsonify({"ok": ok, "updated": True})

    ok = _exec("""
        INSERT INTO watchlist (ticker, notes, side, snap_up_proba, snap_conviction, snap_price, alert_threshold)
        VALUES (:ticker, :notes, :side, :sup, :sc, :sp, :thr)
    """, {
        "ticker": ticker,
        "notes":  data.get("notes", ""),
        "side":   data.get("side", "LONG"),
        "sup":    data.get("snap_up_proba"),
        "sc":     data.get("snap_conviction"),
        "sp":     data.get("snap_price"),
        "thr":    data.get("alert_threshold", 0.70),
    })
    return jsonify({"ok": ok, "updated": False})


@app.route("/api/watchlist/remove/<ticker>", methods=["DELETE"])
def api_watchlist_remove(ticker):
    """Remove a ticker from the watchlist."""
    _ensure_watchlist_table()
    ok = _exec("DELETE FROM watchlist WHERE ticker = :t", {"t": ticker.upper()})
    return jsonify({"ok": ok})


@app.route("/api/watchlist/count")
def api_watchlist_count():
    """Quick count of watchlist items + how many are ready to promote."""
    _ensure_watchlist_table()
    rows = _q("SELECT COUNT(*) AS n FROM watchlist")
    total = rows[0]["n"] if rows else 0
    # Count promote-ready (need enriched data for conviction, so use threshold heuristic)
    return jsonify({"total": total})


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _ensure_signal_queue_table()
    _ensure_watchlist_table()
    start_scheduler()
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    log.info(f"Control Tower (Flask) starting — http://localhost:5000 and http://0.0.0.0:5000 (LAN) (debug={debug_mode})")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
