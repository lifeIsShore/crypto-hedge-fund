"""
engine/briefing/data.py
========================
Shared data-gathering for the Briefing tab. Used by both flask_app.py (the
/briefing route) and generate_cli.py (the pipeline-triggered regeneration),
so there's one source of truth for what "the briefing data" means and the
CLI doesn't need to boot Flask just to query the DB.
"""

from pathlib import Path
import pandas as pd
from sqlalchemy import text

from engine.db.db import get_session

ROOT = Path(__file__).resolve().parents[2]


def _q(sql, params=None):
    """Execute a read query and return list-of-dicts. Mirrors flask_app._q."""
    session = get_session()
    try:
        result = session.execute(text(sql), params or {})
        cols = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]
    except Exception:
        return []
    finally:
        session.close()


def briefing_gate_results():
    gate_path = ROOT / "before-go-live" / "better-alpha" / "gate2_results.csv"
    if not gate_path.exists():
        return []
    try:
        df = pd.read_csv(gate_path)
        if df.empty:
            return []
        df = df.sort_values("date_tested").groupby("flag_name", as_index=False).last()
        return df.to_dict("records")
    except Exception:
        return []


def briefing_pipeline_health():
    last_run = _q("""
        SELECT run_date, status, MAX(started_at) AS started_at
        FROM pipeline_runs
        GROUP BY run_date
        ORDER BY started_at DESC LIMIT 1
    """)
    last_run_date = last_run[0]["run_date"] if last_run else None

    failed_steps = _q("""
        SELECT step_name, status, error_msg, duration_sec
        FROM pipeline_runs
        WHERE run_date = (SELECT MAX(run_date) FROM pipeline_runs)
          AND status != 'success'
        ORDER BY started_at DESC
    """)

    recent_issues = _q("""
        SELECT level, step_name, message, logged_at
        FROM pipeline_logs
        WHERE level IN ('WARNING', 'ERROR', 'CRITICAL')
        ORDER BY logged_at DESC LIMIT 10
    """)

    validation_issues = _q("""
        SELECT issue_type, COUNT(*) AS n
        FROM data_validation_log
        WHERE date = (SELECT MAX(date) FROM data_validation_log)
        GROUP BY issue_type
        ORDER BY n DESC
    """)

    coverage_rows = _q("SELECT COUNT(DISTINCT ticker) AS n FROM signals WHERE date = (SELECT MAX(date) FROM signals)")
    covered = coverage_rows[0]["n"] if coverage_rows else 0
    try:
        from portfolio.src.config import ASSET_UNIVERSE
        universe_size = len(ASSET_UNIVERSE) if ASSET_UNIVERSE else 0
    except Exception:
        universe_size = 0

    return {
        "last_run_date": last_run_date,
        "failed_steps": failed_steps,
        "recent_issues": recent_issues,
        "validation_issues": validation_issues,
        "covered": covered,
        "universe_size": universe_size,
    }


def briefing_ticker_picks():
    rows = _q("""
        SELECT pt.ticker, pt.risk_reward_ratio, pt.up_proba, pt.vol_ann,
               pt.kelly_half, pt.current_price_eur, pt.target_1sigma_eur,
               pt.stop_1sigma_eur, mo.signal_breakdown
        FROM price_targets pt
        LEFT JOIN model_outputs mo
               ON mo.ticker = pt.ticker AND mo.date = pt.date
        WHERE pt.date = (SELECT MAX(date) FROM price_targets)
          AND pt.risk_reward_ratio IS NOT NULL
          AND pt.up_proba IS NOT NULL
    """)

    must_check = sorted(
        [r for r in rows if r["up_proba"] is not None],
        key=lambda r: r["up_proba"], reverse=True
    )[:8]

    best_risk_reward = sorted(
        [r for r in rows if r["risk_reward_ratio"] is not None and (r["vol_ann"] or 1) < 0.40],
        key=lambda r: r["risk_reward_ratio"], reverse=True
    )[:6]

    gamble_tier = sorted(
        [r for r in rows if r["vol_ann"] and r["vol_ann"] >= 0.40 and (r["up_proba"] or 0) > 0.5],
        key=lambda r: (r["vol_ann"] or 0), reverse=True
    )[:6]

    return must_check, best_risk_reward, gamble_tier


def briefing_regime():
    try:
        from shared.state_paths import REGIME_STATE_PATH
        import json
        with open(REGIME_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def briefing_tax_harvest():
    try:
        from engine.risk.circuit_breaker import get_average_entry_prices
        entry_prices = get_average_entry_prices()
        
        # Get current prices from price_targets (today's close)
        rows = _q("SELECT ticker, current_price_eur FROM price_targets WHERE date = (SELECT MAX(date) FROM price_targets)")
        prices = {r["ticker"]: r["current_price_eur"] for r in rows}
        
        # 1. Calculate Unrealized Losers (from current positions)
        pos_rows = _q("SELECT ticker, quantity FROM positions_history WHERE date = (SELECT MAX(date) FROM positions_history)")
        unrealized_losers = []
        for p in pos_rows:
            t = p["ticker"]
            qty = p["quantity"]
            if t in entry_prices and t in prices and qty > 0:
                cost_basis = entry_prices[t]
                current_p = prices[t]
                if current_p < cost_basis:
                    loss_eur = (cost_basis - current_p) * qty
                    unrealized_losers.append({"ticker": t, "loss_eur": round(loss_eur, 2)})
        
        # Sort by biggest losers
        unrealized_losers.sort(key=lambda x: x["loss_eur"], reverse=True)
        
        # 2. Calculate Pending Realized Gains (from model outputs that suggest selling)
        mo_rows = _q("SELECT ticker, current_weight, delta_weight FROM model_outputs WHERE date = (SELECT MAX(date) FROM model_outputs)")
        pending_gains = []
        for mo in mo_rows:
            t = mo["ticker"]
            if mo["delta_weight"] < -0.01 and t in entry_prices and t in prices:
                # We are selling a portion (or all) of it. Calculate how many shares we are selling.
                # delta_weight is negative. We don't have total portfolio value here easily, 
                # so we can approximate the gain based on the entire position's % gain, and scale by the sell ratio.
                # Actually, simpler: just flag the ticker and total potential gain if sold completely, or just the % gain.
                cost_basis = entry_prices[t]
                current_p = prices[t]
                if current_p > cost_basis:
                    gain_pct = (current_p - cost_basis) / cost_basis
                    pending_gains.append({"ticker": t, "gain_pct": round(gain_pct * 100, 2), "delta_weight": round(mo["delta_weight"], 3)})
                    
        return {"pending_gains": pending_gains, "unrealized_losers": unrealized_losers[:5]}
    except Exception as e:
        return {"pending_gains": [], "unrealized_losers": []}


def gather_all():
    """Everything the /briefing route and the narrator both need, in one call."""
    health = briefing_pipeline_health()
    gate_results = briefing_gate_results()
    must_check, best_risk_reward, gamble_tier = briefing_ticker_picks()
    regime = briefing_regime()
    tax = briefing_tax_harvest()
    return health, gate_results, must_check, best_risk_reward, gamble_tier, regime, tax


def narrator_payload(health, gate_results, must_check, best_risk_reward, gamble_tier, regime, tax):
    """Compact form passed to the LLM — keep it small so generation stays fast."""
    def _pick(rows, keys):
        return [{k: r.get(k) for k in keys} for r in rows]

    return {
        "last_run_date": health["last_run_date"],
        "failed_steps": _pick(health["failed_steps"], ["step_name", "status", "error_msg"]),
        "recent_issues": _pick(health["recent_issues"], ["level", "step_name", "message"]),
        "validation_issues": health["validation_issues"],
        "covered": health["covered"],
        "universe_size": health["universe_size"],
        "gate_results": _pick(gate_results, ["flag_name", "delta_ic", "delta_auc", "pass"]),
        "must_check": _pick(must_check, ["ticker", "up_proba", "risk_reward_ratio", "kelly_half"]),
        "best_risk_reward": _pick(best_risk_reward, ["ticker", "risk_reward_ratio", "vol_ann"]),
        "gamble_tier": _pick(gamble_tier, ["ticker", "up_proba", "vol_ann"]),
        "regime": {
            "regime_composite": regime.get("regime_composite"),
            "regime_risk": regime.get("regime_risk"),
        },
        "tax_harvesting": tax,
    }
