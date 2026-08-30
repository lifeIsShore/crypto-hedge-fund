# engine/scheduler.py
"""
Daily pipeline scheduler.

Usage:
  python -m engine.scheduler            # run now
  python -m engine.scheduler --test     # dry run (skips actual ingestion/BL)

Step frequencies:
  Daily (every trading day):
    ledger import, data ingestion, features, alpha signals, divergence scan,
    portfolio construction (BL → optimizer → pre-trade → orders → post-trade risk),
    price targets, regime engine refresh

  Weekly (Monday):
    PEAD engine full refresh

  Weekend (Saturday):
    ML pipeline full refresh

  Standalone heartbeat check:
    python -c "from engine.alerting.digest import check_heartbeat; check_heartbeat()"
"""

import logging
import datetime
import traceback
import argparse
import sys
import os
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
)
logger = logging.getLogger('scheduler')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

try:
    from portfolio.src.config import ASSET_UNIVERSE
    TICKERS = ASSET_UNIVERSE
except Exception as e:
    logger.error(f"Could not import ASSET_UNIVERSE from portfolio/src/config.py: {e}")
    TICKERS = ['APC.DE', 'MSF.DE', 'NVDA', 'SAP.DE', 'EUNL.DE']

TODAY   = str(datetime.date.today())
WEEKDAY = datetime.date.today().weekday()   # 0=Mon, 5=Sat, 6=Sun
HISTORY_START = '2022-01-01'

# ─────────────────────────────────────────────────────────────────────────────
# STEP RUNNER
# ─────────────────────────────────────────────────────────────────────────────

_step_results: list = []


def _run_step(name: str, fn, dry_run: bool = False):
    import time
    from engine.alerting.digest import check_slow_step

    logger.info(f"▶ {name}")
    start = time.time()

    if dry_run:
        logger.info(f"  [DRY RUN] Skipped")
        _log_pipeline_run(name, 'skipped', 0)
        _step_results.append({'name': name, 'status': 'skipped', 'duration_sec': 0})
        return

    try:
        fn()
        elapsed = round(time.time() - start, 1)
        logger.info(f"✅ {name} ({elapsed}s)")
        _log_pipeline_run(name, 'success', elapsed)
        _step_results.append({'name': name, 'status': 'success', 'duration_sec': elapsed})
        check_slow_step(name, elapsed)
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        logger.error(f"❌ {name} FAILED after {elapsed}s: {e}")
        logger.error(traceback.format_exc())
        _log_pipeline_run(name, 'failed', elapsed, str(e)[:500])
        _step_results.append({'name': name, 'status': 'failed', 'duration_sec': elapsed})
        send_alert(f"Pipeline step FAILED: {name}\n{e}")


def _log_pipeline_run(step_name: str, status: str, duration_sec: float, error_msg: str = None):
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("""
            INSERT INTO pipeline_runs (run_date, step_name, status, duration_sec, error_msg)
            VALUES (CURRENT_DATE, :step, :status, :duration, :error)
        """), {'step': step_name, 'status': status,
               'duration': duration_sec, 'error': error_msg})
        session.commit()
        session.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────────────────────────────────────

def step_ledger_import():
    """Stream 8 — replay ledger.csv → sync live positions + cash to DB."""
    from engine.reconciliation.ledger_importer import run_ledger_import
    result = run_ledger_import(date=TODAY)
    if result:
        logger.info(
            f"[ledger] {len(result.get('holdings', {}))} positions, "
            f"cash=€{result.get('cash_eur', 0):.2f}"
        )
        advisor = result.get('trade_advisor_df')
        if advisor is not None and not advisor.empty:
            n_trades = len(advisor[advisor['action'] != 'HOLD'])
            logger.info(f"[ledger] Trade advisor: {n_trades} orders suggested")


def step_ingest():
    """
    Bug fix (2026-08-20): this used to call run_ingestion(TICKERS, HISTORY_START, TODAY)
    unconditionally — re-downloading ~4.5 years of history for all 135 tickers via
    yfinance on EVERY daily run. That was the direct cause of the recurring
    "Slow step: 1. Data ingestion took 422s (threshold 120s)" alert.
    Now: fetch incrementally from the latest date already in the DB (with a small
    overlap buffer to catch adjusted-close revisions), falling back to the full
    HISTORY_START only when the DB has no rows yet (first run / new ticker).
    """
    from engine.data.ingestion import run_ingestion
    from engine.db.db import get_session
    from sqlalchemy import text

    INCREMENTAL_OVERLAP_DAYS = 5

    from_date = HISTORY_START
    try:
        session = get_session()
        row = session.execute(text("SELECT MAX(date) FROM prices")).fetchone()
        session.close()
        if row and row[0]:
            latest_dt = datetime.datetime.strptime(str(row[0])[:10], '%Y-%m-%d').date()
            overlap_dt = latest_dt - datetime.timedelta(days=INCREMENTAL_OVERLAP_DAYS)
            # Never go earlier than HISTORY_START, and never later than TODAY
            history_start_dt = datetime.datetime.strptime(HISTORY_START, '%Y-%m-%d').date()
            from_date = str(max(overlap_dt, history_start_dt))
    except Exception as e:
        logger.warning(f"[ingest] Could not determine latest DB date, falling back to full history: {e}")
        from_date = HISTORY_START

    logger.info(f"[ingest] Fetching from {from_date} (incremental, overlap={INCREMENTAL_OVERLAP_DAYS}d)")
    run_ingestion(TICKERS, from_date, TODAY)


def _mirror_all_state_files():
    """
    Copies all state files from their engine-local data/ folders into shared/state/.
    Called once at the start of the pipeline so every step sees fresh files,
    AND again after regime/PEAD engines run so any new output is immediately visible.
    """
    import shutil
    from shared.state_paths import (
        REGIME_STATE_PATH, REGIME_HISTORY_PATH,
        PEAD_STATE_PATH, PEAD_SETUPS_PATH,
        ensure_state_dir,
    )
    ensure_state_dir()

    copies = [
        # (source, destination)
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'regime_engine', 'data', 'regime_state.json'),   REGIME_STATE_PATH),
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'regime_engine', 'data', 'regime_history.csv'),  REGIME_HISTORY_PATH),
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'pead_engine',   'data', 'pead_state.json'),      PEAD_STATE_PATH),
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'pead_engine',   'data', 'pead_setups.csv'),      PEAD_SETUPS_PATH),
        # Also pick up regime files that the pead_engine may have refreshed
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'pead_engine',   'data', 'regime_state.json'),    REGIME_STATE_PATH),
        (os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                      'pead_engine',   'data', 'regime_history.csv'),   REGIME_HISTORY_PATH),
    ]

    copied, skipped, newer = 0, 0, 0
    seen_dest = set()
    for src, dst in copies:
        if dst in seen_dest:          # don't overwrite with a less-preferred source
            continue
        if not os.path.exists(src):
            skipped += 1
            continue
        # Don't overwrite a NEWER destination with an OLDER source.
        # This prevents stale regime_engine/data/ copies from clobbering
        # the fresh shared/state/ files that regime_db.py just wrote.
        if os.path.exists(dst):
            src_mtime = os.path.getmtime(src)
            dst_mtime = os.path.getmtime(dst)
            if dst_mtime >= src_mtime:
                seen_dest.add(dst)   # dst is already the freshest version
                newer += 1
                logger.debug(f"[mirror] {os.path.basename(dst)} already up-to-date (skipping stale source)")
                continue
        shutil.copy2(src, dst)
        seen_dest.add(dst)
        copied += 1
        logger.info(f"[mirror] {os.path.basename(src)} → shared/state/")

    logger.info(f"[mirror] {copied} copied, {newer} already fresh, {skipped} sources not found")


def step_regime_refresh():
    import subprocess
    project_root = _ROOT
    regime_dir = os.path.join(
        project_root, 'ml_quant_finance_research', 'quant_research', 'regime_engine'
    )

    if not os.path.isdir(regime_dir):
        logger.warning(f"[regime] regime_engine dir not found: {regime_dir} — skipping")
        # Still mirror whatever files already exist
        _mirror_all_state_files()
        return

    try:
        result = subprocess.run(
            [sys.executable, 'run_engine.py', '--region', 'ALL'],
            cwd=regime_dir, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            logger.warning(f"[regime] Engine non-zero:\n{result.stderr[-500:]}")
        else:
            logger.info("[regime] regime_state.json updated")
        # Mirror regardless — if the run updated files, copy them; if not, copy what's there
        _mirror_all_state_files()
        _sync_regime_history_to_db(
            os.path.join(_ROOT, 'ml_quant_finance_research', 'quant_research',
                         'regime_engine', 'data', 'regime_history.csv')
        )
    except subprocess.TimeoutExpired:
        logger.error("[regime] Timed out after 5 minutes")
        _mirror_all_state_files()   # copy whatever we have
    except Exception as e:
        logger.error(f"[regime] Failed: {e}")
        _mirror_all_state_files()


def _mirror_regime_to_shared(regime_dir: str, project_root: str):
    import shutil
    from shared.state_paths import REGIME_STATE_PATH, REGIME_HISTORY_PATH, ensure_state_dir
    ensure_state_dir()

    src_state   = os.path.join(regime_dir, 'data', 'regime_state.json')
    src_history = os.path.join(regime_dir, 'data', 'regime_history.csv')

    if os.path.exists(src_state):
        shutil.copy2(src_state, REGIME_STATE_PATH)

    if os.path.exists(src_history):
        shutil.copy2(src_history, REGIME_HISTORY_PATH)
        _sync_regime_history_to_db(src_history)


def _sync_regime_history_to_db(csv_path: str):
    try:
        df = pd.read_csv(csv_path)
        if df.empty or 'date' not in df.columns:
            return
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        count = 0
        try:
            for _, row in df.iterrows():
                session.execute(text("""
                    INSERT INTO regime_history
                        (date, region, regime_risk, regime_rates, regime_growth, regime_composite,
                         transition_warning, ew_active_count,
                         vix, yield_spread, hy_spread, fed_funds, computed_at)
                    VALUES (:date,:region,:risk,:rates,:growth,:composite,:ew_flag,:ew_count,
                            :vix,:yield_spread,:hy_spread,:fed_funds,datetime('now'))
                    ON CONFLICT(date, region) DO UPDATE SET
                        regime_risk=:risk, regime_rates=:rates, regime_growth=:growth,
                        regime_composite=:composite, transition_warning=:ew_flag,
                        ew_active_count=:ew_count, vix=:vix,
                        yield_spread=:yield_spread, hy_spread=:hy_spread, fed_funds=:fed_funds
                """), {
                    'date': str(row.get('date', '')),
                    'region': row.get('region', 'US'),
                    'risk': row.get('regime_risk'), 'rates': row.get('regime_rates'),
                    'growth': row.get('regime_growth'), 'composite': row.get('regime_composite'),
                    'ew_flag': int(row.get('transition_warning', 0)),
                    'ew_count': int(row.get('ew_active_count', 0)),
                    'vix': row.get('vix'), 'yield_spread': row.get('yield_spread'),
                    'hy_spread': row.get('hy_spread'), 'fed_funds': row.get('fed_funds'),
                })
                count += 1
            session.commit()
            logger.info(f"[regime] Synced {count} rows → regime_history table")
        except Exception as e:
            session.rollback()
            logger.warning(f"[regime] DB sync failed: {e}")
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"[regime] CSV→DB sync error: {e}")


def step_features():
    from engine.features.feature_store import run_feature_pipeline
    run_feature_pipeline(TICKERS, TODAY)


def step_earnings_calendar():
    """
    J4 — fetches upcoming earnings dates via Finnhub and persists them,
    remapped to this engine's primary tickers (see earnings_calendar.py's
    module docstring for why the remap is necessary).
    Non-fatal by design: a missing/rate-limited Finnhub call should never
    break the pipeline, it just means the earnings throttle has no data
    to act on until the next successful run.
    """
    from engine.data.earnings_calendar import run_earnings_ingestion
    from portfolio.src.config import TICKER_MAPPING

    # Finnhub returns US-style symbols. Build symbol -> primary_ticker so
    # rows land under the same key order_manager/PEAD already use.
    # 1) Primary .DE tickers that have a US fallback (TICKER_MAPPING values).
    symbol_to_primary = {us_symbol: primary for primary, us_symbol in TICKER_MAPPING.items()}
    # 2) Tickers already in US/native form in the universe (e.g. 'UNH', 'NVDA'
    #    itself if ever added directly) map to themselves.
    for t in TICKERS:
        symbol_to_primary.setdefault(t, t)

    count = run_earnings_ingestion(symbol_to_primary)
    logger.info(f"[earnings_calendar] {count} rows persisted for {TODAY}")


def step_alpha(model_name: str):
    from engine.alpha.momentum         import MomentumAlpha
    from engine.alpha.sector_momentum  import SectorMomentumAlpha
    from engine.alpha.mean_reversion   import MeanReversionAlpha
    from engine.alpha.vol_timing       import VolTimingAlpha
    from engine.alpha.pead_alpha       import PEADAlpha
    from engine.alpha.ml_alpha         import MLAlpha

    model_map = {
        'momentum':        MomentumAlpha(),
        'sector_momentum': SectorMomentumAlpha(),   # J5
        'mean_reversion':  MeanReversionAlpha(),
        'vol_timing':      VolTimingAlpha(),
        'pead':            PEADAlpha(),
        'ml_model':        MLAlpha(),
    }
    model = model_map[model_name]
    signals = model.generate_signals(TODAY, TICKERS)
    if signals is not None and not signals.empty:
        model.persist_signals(TODAY, signals)
        logger.info(f"[{model_name}] {len(signals)} signals persisted")
    else:
        logger.info(f"[{model_name}] No signals generated")


def step_divergence_scan():
    from engine.screens.etf_divergence import detect_divergences, save_divergence_events
    divergences = detect_divergences(TODAY)
    save_divergence_events(divergences)
    logger.info(f"ETF divergence scan: {len(divergences)} events found")


def step_outcome_fill():
    from engine.screens.etf_divergence import fill_outcome_data
    fill_outcome_data()


def step_portfolio_construction():
    """
    Full portfolio construction:
      1. Covariance matrix from DB returns
      2. Current weights (now from ledger import via positions_history)
      3. Regime info from feature_store (_PORTFOLIO features)
      4. Black-Litterman posterior returns
      5. Constrained optimizer → suggested weights
      6. Pre-trade risk checks
      7. Order queue generation
      8. Post-trade risk snapshot
    """
    import numpy as np
    from engine.portfolio.black_litterman import run_black_litterman
    from engine.portfolio.optimizer import optimize_with_bl, persist_model_outputs
    from engine.risk.pre_trade import run_pre_trade_checks
    from engine.risk.post_trade import run_post_trade_risk
    from engine.risk.circuit_breaker import run_circuit_breaker_check, get_average_entry_prices
    from engine.execution.order_manager import generate_order_queue
    from engine.features.feature_store import load_returns_from_db
    from engine.db.db import get_session
    from sqlalchemy import text

    log_returns = load_returns_from_db(TICKERS, lookback_days=252)
    if log_returns.empty:
        logger.error("[portfolio] No returns in DB — run ingestion first")
        return

    available_tickers = [t for t in TICKERS if t in log_returns.columns]
    if len(available_tickers) < 2:
        logger.error("[portfolio] < 2 tickers with data — skipping")
        return

    cov_matrix = log_returns[available_tickers].cov() * 252

    # H1 fix: Ledoit-Wolf shrinkage — reduces estimation noise in the covariance
    # matrix (N~130 tickers vs T=252 obs is right at the noise boundary).
    try:
        from sklearn.covariance import LedoitWolf
        returns_matrix = log_returns[available_tickers].dropna()
        if len(returns_matrix) >= len(available_tickers):
            lw = LedoitWolf().fit(returns_matrix.values)
            cov_matrix = pd.DataFrame(
                lw.covariance_ * 252,
                index=available_tickers,
                columns=available_tickers,
            )
            logger.info(f"[portfolio] Covariance: Ledoit-Wolf shrinkage applied (shrinkage={lw.shrinkage_:.3f})")
        else:
            logger.warning("[portfolio] Insufficient data for Ledoit-Wolf — using raw covariance")
    except Exception as e:
        logger.warning(f"[portfolio] Ledoit-Wolf shrinkage failed, using raw covariance: {e}")

    # Current weights — sourced from ledger import (positions_history)
    session = get_session()
    rows = session.execute(text("""
        SELECT p.ticker, p.weight
        FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS max_date
            FROM positions_history GROUP BY ticker
        ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
    """)).fetchall()
    session.close()
    current_weights = pd.Series(
        {r[0]: float(r[1]) for r in rows if r[0] in available_tickers}
    ).reindex(available_tickers, fill_value=0.0)

    market_weights = pd.Series(1.0 / len(available_tickers), index=available_tickers)

    # Regime info
    regime_info = None
    try:
        session2 = get_session()
        result_row = session2.execute(text("""
            SELECT feature_name, feature_value FROM feature_store
            WHERE ticker = '_PORTFOLIO' AND date = :date
        """), {'date': TODAY}).fetchall()
        session2.close()

        if result_row:
            feat = {r[0]: float(r[1]) for r in result_row}
            if feat.get('regime_high', 0):    stat = 'high_stress'
            elif feat.get('regime_low', 0):   stat = 'low_stress'
            else:                             stat = 'medium'

            mc = []
            mc.append('RiskOn' if feat.get('macro_risk_on') else ('RiskOff' if feat.get('macro_risk_off') else 'Neutral'))
            mc.append('Easing' if feat.get('macro_easing') else ('Tightening' if feat.get('macro_tightening') else 'Neutral'))
            mc.append('Expansion' if feat.get('macro_expansion') else
                      ('Contraction' if feat.get('macro_contraction') else
                       ('Recovery' if feat.get('macro_recovery') else 'Slowdown')))

            regime_info = {
                'regime': stat, 'stress_score': feat.get('stress_score', 0.5),
                'macro_composite': '_'.join(mc),
                'macro_risk_on': bool(feat.get('macro_risk_on')),
                'macro_risk_off': bool(feat.get('macro_risk_off')),
                'macro_expansion': bool(feat.get('macro_expansion')),
                'macro_ew_transition': bool(feat.get('macro_ew_transition')),
                'macro_ew_count': int(feat.get('macro_ew_count', 0)),
                'macro_vix': feat.get('macro_vix', 20.0),
            }
            logger.info(f"[portfolio] Regime: {stat} | {regime_info['macro_composite']}")
    except Exception as e:
        logger.warning(f"[portfolio] Regime load failed: {e}")

    from engine.alpha.momentum        import MomentumAlpha
    from engine.alpha.sector_momentum import SectorMomentumAlpha
    from engine.alpha.mean_reversion  import MeanReversionAlpha
    from engine.alpha.vol_timing      import VolTimingAlpha
    from engine.alpha.pead_alpha      import PEADAlpha
    from engine.alpha.ml_alpha        import MLAlpha
    from portfolio.src.config         import TICKER_SECTORS
    models_dict = {
        'momentum': MomentumAlpha(), 'sector_momentum': SectorMomentumAlpha(),  # J5
        'mean_reversion': MeanReversionAlpha(),
        'vol_timing': VolTimingAlpha(), 'pead': PEADAlpha(), 'ml_model': MLAlpha(),
    }

    mu_bl, signal_breakdown = run_black_litterman(
        tickers=available_tickers, cov_matrix=cov_matrix,
        market_weights=market_weights, date=TODAY,
        regime_info=regime_info, models_dict=models_dict,
    )

    # Current prices — fetched once, reused for both the tax penalty (J2)
    # and the circuit breaker check below (previously fetched twice).
    session_px = get_session()
    px_rows = session_px.execute(text("""
        SELECT p.ticker, p.adj_close
        FROM prices p
        INNER JOIN (
            SELECT ticker, MAX(date) AS max_date FROM prices GROUP BY ticker
        ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
    """)).fetchall()
    session_px.close()
    current_prices = pd.Series({r[0]: float(r[1]) for r in px_rows if r[1] is not None})

    suggested_weights = optimize_with_bl(
        mu_bl=mu_bl, cov_matrix=cov_matrix, current_weights=current_weights,
        current_prices=current_prices, sector_map=TICKER_SECTORS, date=TODAY,
    )
    persist_model_outputs(TODAY, suggested_weights, current_weights, mu_bl, signal_breakdown)

    # ── I3: Circuit Breaker — force-exit positions down > threshold from entry ──
    try:
        # Reuse current_prices fetched above for the J2 tax penalty — no need to re-query
        current_prices_cb = current_prices.to_dict()

        # Average cost basis per ticker from trades table
        entry_prices_cb = get_average_entry_prices()

        # Positions with positive weight in current allocation
        positions_cb = {
            t: float(current_weights.get(t, 0))
            for t in available_tickers
            if float(current_weights.get(t, 0)) > 0
        }

        cb_triggered = run_circuit_breaker_check(
            positions=positions_cb,
            current_prices=current_prices_cb,
            entry_prices=entry_prices_cb,
        )

        if cb_triggered:
            for ticker in cb_triggered:
                if ticker in suggested_weights.index:
                    suggested_weights[ticker] = 0.0   # force full exit
            logger.critical(
                f"[circuit_breaker] Forced weights to 0 for: {cb_triggered}"
            )
            send_alert(f"🚨 CIRCUIT BREAKER activated for: {', '.join(cb_triggered)}")

    except Exception as e:
        logger.warning(f"[circuit_breaker] Check failed (non-fatal, continuing): {e}")

    pre_trade = run_pre_trade_checks(suggested_weights)
    if not pre_trade['passed']:
        logger.warning(f"[portfolio] Pre-trade FAILED: {pre_trade['violations']}")
        send_alert("Pre-trade checks failed:\n" + "\n".join(pre_trade['violations']))
        run_post_trade_risk(weights=current_weights.to_dict(), tickers=available_tickers)
        return

    # Portfolio value from ledger-synced positions + cash
    session3 = get_session()
    val_row  = session3.execute(text("""
        SELECT SUM(value_eur) FROM positions_history p
        INNER JOIN (SELECT ticker, MAX(date) AS max_date FROM positions_history GROUP BY ticker)
        latest ON p.ticker=latest.ticker AND p.date=latest.max_date
    """)).fetchone()
    cash_row = session3.execute(text("""
        SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1
    """)).fetchone()
    session3.close()

    portfolio_value = float(val_row[0] or 0) + float(cash_row[0] if cash_row else 0)
    if portfolio_value < 100:
        logger.warning("[portfolio] Low portfolio value — using €10,000 default")
        portfolio_value = 10_000.0

    orders = generate_order_queue(
        suggested_weights=suggested_weights,
        current_weights=current_weights,
        total_portfolio_eur=portfolio_value,
    )
    logger.info(f"[portfolio] {len(orders)} orders (portfolio=€{portfolio_value:,.0f})")
    
    # Pre-Trade Tax Awareness Check (Task 9)
    try:
        from engine.risk.pre_trade import check_tax_awareness
        check_tax_awareness(orders)
    except Exception as e:
        logger.error(f"[tax_awareness] check failed: {e}")

    order_dicts = []
    for o in orders:
        logger.info(f"  {o.action:4s} {o.ticker:12s} €{o.value_eur:>8.2f}")
        order_dicts.append({"ticker": o.ticker, "action": o.action, "value_eur": o.value_eur, "order_id": o.order_id, "state": o.state.value, "notes": o.notes})
        
    # Save to state for manual execution via UI
    import json
    from shared.state_paths import STATE_DIR
    import os
    queue_path = os.path.join(STATE_DIR, "order_queue.json")
    try:
        import datetime
        with open(queue_path, "w") as f:
            json.dump({"orders": order_dicts, "generated_at": datetime.datetime.now().isoformat(), "portfolio_value": portfolio_value}, f)
    except Exception as e:
        logger.error(f"Failed to save order_queue.json: {e}")

    if os.getenv("SANDBOX_MODE") == "1":
        from engine.execution.paper_trader import execute_paper_orders
        session_sandbox = get_session()
        sb_price_rows = session_sandbox.execute(text("""
            SELECT p.ticker, p.adj_close
            FROM prices p
            INNER JOIN (SELECT ticker, MAX(date) AS max_date FROM prices GROUP BY ticker)
            latest ON p.ticker=latest.ticker AND p.date=latest.max_date
        """)).fetchall()
        session_sandbox.close()
        current_prices_sb = {r[0]: float(r[1]) for r in sb_price_rows if r[1] is not None}
        execute_paper_orders(orders, current_prices_sb, portfolio_value)

    run_post_trade_risk(weights=suggested_weights.to_dict(), tickers=available_tickers)


def step_price_targets():
    """Stream 3 — probabilistic price targets for all tickers."""
    from engine.analysis.price_targets import run_price_targets
    targets = run_price_targets(TICKERS, TODAY)
    logger.info(f"[price_targets] {len(targets)} targets computed")


def step_pead_refresh():
    from engine.alpha.pead_alpha import run_pead_engine_weekly
    run_pead_engine_weekly()


def step_ml_refresh():
    from engine.alpha.ml_alpha import run_ml_pipeline_refresh
    run_ml_pipeline_refresh()


def step_performance_log():
    """
    Final step: calculate total wealth (Cash + Stocks) and log to performance_history.
    This is the data source for the dashboard's Equity Curve and Risk Metrics.
    """
    from engine.db.db import get_session
    from sqlalchemy import text
    session = get_session()
    
    # 1. Get current positions market value
    val_row = session.execute(text("""
        SELECT SUM(value_eur) FROM positions_history p
        INNER JOIN (SELECT ticker, MAX(date) AS max_date FROM positions_history GROUP BY ticker)
        latest ON p.ticker=latest.ticker AND p.date=latest.max_date
    """)).fetchone()
    
    # 2. Get current cash
    cash_row = session.execute(text("""
        SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1
    """)).fetchone()
    
    total_val = float(val_row[0] or 0) + float(cash_row[0] if cash_row else 0)
    
    # 3. Get previous day's value for return calculation
    prev_row = session.execute(text("""
        SELECT date, portfolio_value_eur FROM performance_history 
        WHERE date < :d ORDER BY date DESC LIMIT 1
    """), {'d': TODAY}).fetchone()
    
    # 4. Get today's net cash flow (deposits/withdrawals) to adjust return
    flow_row = session.execute(text("""
        SELECT SUM(value_eur) FROM (
            SELECT value_eur FROM trades WHERE date = :d AND action = 'DEPOSIT'
            UNION ALL
            SELECT -value_eur FROM trades WHERE date = :d AND action = 'WITHDRAWAL'
        )
    """), {'d': TODAY}).fetchone()
    
    flow = float(flow_row[0] or 0)
    prev_val = float(prev_row[1]) if prev_row else total_val - flow

    # Bug fix (2026-08-20): daily_return_pct used to be computed against
    # whatever row happened to be logged most recently, with no check on
    # how long ago that was. If the pipeline skipped days (or a manual DB
    # correction changed portfolio_value_eur without being routed through
    # DEPOSIT/WITHDRAWAL), the resulting number is a multi-day or corrective
    # jump mislabeled as a single day's return (this is what produced the
    # "-39.62%" print). Now: (a) only treat it as a true daily return if the
    # previous row is exactly one calendar day back, otherwise log it as a
    # gap-adjusted return and flag it explicitly; (b) fire a CRITICAL alert
    # instead of silently trusting any |return| > 15%, since that's either a
    # real emergency or a data/accounting bug either way worth a human look.
    is_gap = False
    if prev_row:
        prev_date = datetime.datetime.strptime(str(prev_row[0])[:10], '%Y-%m-%d').date()
        today_date = datetime.datetime.strptime(TODAY, '%Y-%m-%d').date()
        is_gap = (today_date - prev_date).days > 1

    daily_ret = 0.0
    if prev_val > 0:
        daily_ret = (total_val - flow - prev_val) / prev_val

    if is_gap:
        logger.warning(
            f"[performance] Previous logged value is from {prev_row[0]}, not yesterday — "
            f"'daily_return_pct' below actually covers that whole gap, not one day."
        )
    if abs(daily_ret) > 0.15:
        send_alert(
            f"🚨 Performance logging computed an unusually large "
            f"{'gap-adjusted ' if is_gap else 'daily '}return of {daily_ret*100:+.2f}% "
            f"(prev={prev_val:,.2f} EUR on {prev_row[0] if prev_row else 'n/a'}, "
            f"today={total_val:,.2f} EUR). Verify this isn't a data/accounting error "
            f"before trusting the dashboard."
        )
    
    # I5: Benchmark equity curve — track MSCI World (EUNL.DE) alongside portfolio
    from portfolio.src.config import BENCHMARK_TICKER
    bench_val = None
    try:
        bench_today = session.execute(text("""
            SELECT adj_close FROM prices WHERE ticker = :b ORDER BY date DESC LIMIT 1
        """), {'b': BENCHMARK_TICKER}).fetchone()

        bench_prev = session.execute(text("""
            SELECT adj_close FROM prices
            WHERE ticker = :b AND date < (SELECT MAX(date) FROM prices WHERE ticker = :b)
            ORDER BY date DESC LIMIT 1
        """), {'b': BENCHMARK_TICKER}).fetchone()

        bench_row = session.execute(text("""
            SELECT benchmark_value_eur FROM performance_history
            WHERE date < :d AND benchmark_value_eur IS NOT NULL
            ORDER BY date DESC LIMIT 1
        """), {'d': TODAY}).fetchone()

        if bench_today and bench_prev and bench_prev[0] and float(bench_prev[0]) > 0:
            bench_ret = (float(bench_today[0]) - float(bench_prev[0])) / float(bench_prev[0])
            if bench_row and bench_row[0]:
                bench_val = round(float(bench_row[0]) * (1 + bench_ret), 2)
            else:
                # Initialize benchmark to same starting value as portfolio (first deposit)
                first_deposit = session.execute(text("""
                    SELECT SUM(value_eur) FROM trades WHERE action = 'DEPOSIT'
                """)).fetchone()
                if first_deposit and first_deposit[0]:
                    bench_val = round(float(first_deposit[0]), 2)
    except Exception as e:
        logger.warning(f"[performance] Benchmark tracking failed (non-fatal): {e}")
    
    # 5. Persist to DB
    session.execute(text("""
        INSERT INTO performance_history (date, portfolio_value_eur, daily_return_pct, benchmark_value_eur)
        VALUES (:d, :v, :r, :b)
        ON CONFLICT(date) DO UPDATE SET
            portfolio_value_eur = excluded.portfolio_value_eur,
            daily_return_pct = excluded.daily_return_pct,
            benchmark_value_eur = excluded.benchmark_value_eur
    """), {
        'd': TODAY,
        'v': round(total_val, 2),
        'r': round(daily_ret * 100, 4),
        'b': bench_val,
    })
    
    session.commit()
    session.close()
    logger.info(f"[performance] Logged: €{total_val:,.2f} | Return: {daily_ret*100:+.2f}%")


def _get_held_and_watchlisted_tickers() -> list:
    from engine.db.db import get_session
    from sqlalchemy import text
    session = get_session()
    try:
        held = session.execute(text(
            "SELECT DISTINCT ticker FROM positions_history "
            "WHERE date = (SELECT MAX(date) FROM positions_history)"
        )).fetchall()
        watched = session.execute(text("SELECT DISTINCT ticker FROM watchlist")).fetchall()
        return sorted({r[0] for r in held} | {r[0] for r in watched})
    finally:
        session.close()


def step_pead_calendar_trigger():
    """
    Daily fast-path check: did any held/watchlisted ticker report earnings in
    the last 2 days? If so and it has no active PEAD setup yet, run a targeted
    PEAD screen for just that ticker instead of waiting for Monday's full scan.
    """
    from engine.data.earnings_calendar import get_recently_reported
    from engine.alpha.pead_alpha import PEAD_SETUPS_PATH
    import pandas as pd
    import sys
    import os
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    watch_tickers = _get_held_and_watchlisted_tickers()
    if not watch_tickers:
        return

    reported = get_recently_reported(watch_tickers, within_days=2)
    if not reported:
        return

    already_covered = set()
    if os.path.exists(PEAD_SETUPS_PATH):
        try:
            existing = pd.read_csv(PEAD_SETUPS_PATH)
            if 'entry_date' in existing.columns and 'ticker' in existing.columns:
                existing['entry_date'] = pd.to_datetime(existing['entry_date'], errors='coerce')
                recent_cutoff = pd.Timestamp(TODAY) - pd.Timedelta(days=5)
                already_covered = set(
                    existing[existing['entry_date'] >= recent_cutoff]['ticker']
                )
        except Exception as e:
            logger.warning(f"[pead_calendar_trigger] Could not read pead_setups.csv: {e}")

    to_screen = list(reported - already_covered)
    if not to_screen:
        logger.info(f"[pead_calendar_trigger] {len(reported)} ticker(s) reported "
                     f"recently, all already covered by an active setup")
        return

    logger.info(f"[pead_calendar_trigger] Triggering targeted PEAD screen for: {to_screen}")

    pead_dir = os.path.join(_PROJECT_ROOT, 'ml_quant_finance_research',
                             'quant_research', 'pead_engine')
    original_dir = os.getcwd()
    try:
        os.chdir(pead_dir)
        if pead_dir not in sys.path:
            sys.path.insert(0, pead_dir)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_engine", os.path.join(pead_dir, "run_engine.py"))
        run_engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_engine)
        run_engine.run_targeted(to_screen)
        from engine.alpha.pead_alpha import _mirror_pead_to_shared
        _mirror_pead_to_shared(pead_dir)
    except Exception as e:
        logger.error(f"[pead_calendar_trigger] Targeted screen failed (non-fatal, "
                      f"Monday's full run will still catch it): {e}")
    finally:
        os.chdir(original_dir)
        if pead_dir in sys.path:
            sys.path.remove(pead_dir)


def step_liquidity_classification():
    from engine.data.liquidity_classifier import run_liquidity_classification
    run_liquidity_classification(TICKERS, TODAY)


def step_laggard_screen():
    """
    Weekly (Monday) — sector rotation laggard screen (J7).

    Deviation from the J7 doc worth flagging: SECTOR_ETF_MAP only has 3 broad
    regional/market proxies (Nasdaq-100, DAX, MSCI World), not true per-sector
    ETFs (XLK/XLE/XLF/...), while TICKER_SECTORS classifies tickers into ~20
    granular sectors (Semiconductors, Software, Ecommerce, ...). There's no
    honest way to match those two vocabularies 1:1, so `detect_rising_sectors`
    is used here as a coarse "is the broad market in an uptrend" gate rather
    than a per-sector filter: if none of the 3 proxies show sustained 8%+
    momentum, skip the screen for the week (no point hunting laggards in a
    falling market). If at least one is rising, the screen runs across every
    real TICKER_SECTORS group with >=4 members — true sector-level gating
    would need real sector ETF data this system doesn't ingest.
    """
    from engine.screens.laggard_screen import (
        detect_rising_sectors, run_laggard_screen, persist_laggard_results, SECTOR_ETF_MAP
    )
    from portfolio.src.config import TICKER_SECTORS

    rising = detect_rising_sectors(SECTOR_ETF_MAP)
    if not rising:
        logger.info("[laggard_screen] No broad-market uptrend detected this week — skipping")
        return
    logger.info(f"[laggard_screen] Broad-market gate passed via: {[r['sector'] for r in rising]}")

    # Build peer groups from the real, granular sector classification
    peer_groups = {}
    for ticker, sector in TICKER_SECTORS.items():
        if ticker in TICKERS:   # only tickers actually in this engine's universe
            peer_groups.setdefault(sector, []).append(ticker)

    candidates = run_laggard_screen(peer_groups)
    if candidates:
        persist_laggard_results(TODAY, candidates)
    else:
        logger.info(f"[laggard_screen] 0 candidates for {TODAY}")


def step_lstm_train():
    """Saturday — walk-forward train LSTM for all tickers and save models."""
    from engine.alpha.lstm_model import LSTMAlpha
    try:
        model = LSTMAlpha()
        summary = model.train_all(tickers=TICKERS, date=TODAY)
        passed = sum(1 for v in summary.values() if v.get('auc', 0) >= 0.53)
        logger.info(f"[lstm_train] {passed}/{len(summary)} tickers above AUC gate")
    except Exception as e:
        logger.error(f"[lstm_train] Training failed: {e}")

def step_reconciliation():
    """Daily — compare internal tax_lots with Binance API balance."""
    try:
        from engine.execution.reconciliation import run_reconciliation
        run_reconciliation()
    except Exception as e:
        logger.error(f"[reconciliation] Failed: {e}")


def step_push_signals_to_queue(
    long_conv_threshold: float = 0.65,
    short_conv_threshold: float = 0.45,
    auc_gate: float = 0.53,
    expiry_days: int = 3,
):
    """
    Auto-populate the HITL signal_queue table from today’s pipeline outputs.

    Reads price_targets (conviction proxy) + ml_state (AUC) + regime + PEAD,
    and inserts any signal that:
      - Passes the AUC gate
      - Exceeds the conviction threshold (long or short)
      - Is NOT already pending for the same ticker/signal_type in the last 3 days

    Also auto-inserts newly active PEAD setups regardless of conviction threshold.

    This turns the Review Queue from a purely manual inbox into an active inbox
    populated automatically after each pipeline run.
    """
    if _is_system_halted():
        logger.warning("[SOS] System is HALTED — skipping signal push to queue")
        return

    import json, os
    from datetime import datetime as _dt, timedelta as _td
    from engine.db.db import get_session
    from sqlalchemy import text

    # ── Ensure table exists (safe to call if already created) ────────────────
    _create_signal_queue_sql = """
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
    """
    session = get_session()
    try:
        session.execute(text(_create_signal_queue_sql))
        session.commit()
    finally:
        session.close()

    # ── Load price targets ───────────────────────────────────────────────────
    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT ticker, current_price_eur, target_1sigma_eur, stop_1sigma_eur,
                   support_bb_lower, resistance_ma50,
                   risk_reward_ratio, up_proba, vol_ann
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
        """)).fetchall()
        cols = ['ticker','current_price_eur','target_1sigma_eur','stop_1sigma_eur',
                'support_bb_lower','resistance_ma50','risk_reward_ratio','up_proba','vol_ann']
        targets = [dict(zip(cols, r)) for r in rows]
    finally:
        session.close()

    if not targets:
        logger.info("[signal_push] No price targets found — skipping queue push")
        return

    # ── Load ML state (AUC per ticker) ───────────────────────────────────────
    from shared.state_paths import ML_STATE_PATH, REGIME_STATE_PATH
    def _load_json_safe(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    ml     = _load_json_safe(ML_STATE_PATH)
    reg    = _load_json_safe(REGIME_STATE_PATH)
    ml_signals = ml.get('model_signals', {}) or {}

    regime_risk   = (reg.get('regime_risk') or '').lower()
    regime_mult_l = 1.2 if 'risk-on' in regime_risk else 0.8 if 'risk-off' in regime_risk else 1.0
    regime_mult_s = 1.2 if 'risk-off' in regime_risk else 0.7 if 'risk-on' in regime_risk else 1.0
    transition    = bool(reg.get('transition_warning', False))

    # ── Load PEAD active setups ──────────────────────────────────────────────
    session = get_session()
    try:
        pead_rows = session.execute(text("""
            SELECT ticker, direction, pead_setup_quality
            FROM pead_setups
            WHERE earnings_date >= date('now', '-60 days')
            ORDER BY earnings_date DESC
        """)).fetchall()
        pead_map = {}
        for r in pead_rows:
            t = r[0]
            if t not in pead_map:
                pead_map[t] = {'direction': r[1], 'pead_setup_quality': r[2]}
    finally:
        session.close()

    expires_at = (_dt.now() + _td(days=expiry_days)).strftime('%Y-%m-%d %H:%M:%S')
    cutoff     = (_dt.now() - _td(days=expiry_days)).strftime('%Y-%m-%d %H:%M:%S')

    pushed_long = pushed_short = pushed_pead = already_exists = 0

    def _already_pending(ticker, signal_type, cutoff_ts):
        """True if a pending entry for this ticker+signal_type exists within cutoff."""
        session2 = get_session()
        try:
            row = session2.execute(text("""
                SELECT id FROM signal_queue
                WHERE ticker = :t AND signal_type = :st AND status = 'pending'
                  AND generated_at > :cutoff
            """), {'t': ticker, 'st': signal_type, 'cutoff': cutoff_ts}).fetchone()
            return row is not None
        finally:
            session2.close()

    def _insert_signal(ticker, signal_type, conviction, short_score,
                       up_proba, auc, rr_ratio, cur, tgt, stop, vol_ann, source):
        session3 = get_session()
        try:
            session3.execute(text("""
                INSERT INTO signal_queue
                    (ticker, signal_type, conviction, short_score, up_proba, auc,
                     rr_ratio, current_price, target_price, stop_price,
                     vol_ann, expires_at, source)
                VALUES
                    (:ticker, :st, :conv, :ss, :up, :auc, :rr,
                     :cur, :tgt, :stop, :vol, :expires, :source)
            """), {
                'ticker': ticker, 'st': signal_type, 'conv': conviction,
                'ss': short_score, 'up': up_proba, 'auc': auc, 'rr': rr_ratio,
                'cur': cur, 'tgt': tgt, 'stop': stop, 'vol': vol_ann,
                'expires': expires_at, 'source': source,
            })
            session3.commit()
        finally:
            session3.close()

    for row in targets:
        ticker   = row['ticker']
        up_proba = float(row.get('up_proba') or 0.5)
        auc      = float((ml_signals.get(ticker) or {}).get('auc') or 0)
        rr_ratio = float(row.get('risk_reward_ratio') or 0)
        vol_ann  = float(row.get('vol_ann') or 0)
        cur      = float(row.get('current_price_eur') or 0)
        tgt      = float(row.get('target_1sigma_eur') or 0)
        stop     = float(row.get('stop_1sigma_eur') or 0)

        if auc < auc_gate:
            continue

        # PEAD boost
        pead_info = pead_map.get(ticker)
        pead_boost = 1.0
        if pead_info:
            q = (pead_info.get('pead_setup_quality') or '').upper()
            pead_boost = 1.15 if q == 'HIGH' else 1.08 if q == 'MEDIUM' else 1.03

        vol_pct   = vol_ann * 100
        vol_score = 1.1 if 15 <= vol_pct <= 40 else 0.8 if vol_pct > 60 else 1.0

        # ── Long signal ──────────────────────────────────────────────────────
        if up_proba >= 0.54:
            conv = up_proba * auc * (1 + rr_ratio) * regime_mult_l * pead_boost * vol_score
            if conv >= long_conv_threshold:
                if _already_pending(ticker, 'BUY', cutoff):
                    already_exists += 1
                else:
                    _insert_signal(ticker, 'BUY', round(conv, 4), None,
                                   round(up_proba, 4), round(auc, 4), round(rr_ratio, 2),
                                   round(cur, 2), round(tgt, 2), round(stop, 2),
                                   round(vol_ann, 4), 'pipeline')
                    pushed_long += 1

        # ── Short signal (regime-gated) ──────────────────────────────────────
        is_bearish_pead = pead_info and (pead_info.get('direction') or '').lower() in ('bearish', 'bear')
        show_short = ('risk-off' in regime_risk or transition or up_proba <= 0.38 or is_bearish_pead)
        if up_proba <= 0.40 and show_short:
            bear_proba = 1.0 - up_proba
            short_cover = float(row.get('support_bb_lower') or 0)
            short_stop  = float(row.get('resistance_ma50') or 0) or (cur * 1.05 if cur > 0 else 0)
            rr_short = max(0.5, min(
                (cur - short_cover) / (short_stop - cur) if (short_stop > cur and short_cover > 0) else rr_ratio * 0.8,
                5.0
            ))
            short_score = bear_proba * auc * rr_short * regime_mult_s * pead_boost
            if short_score >= short_conv_threshold:
                if _already_pending(ticker, 'SHORT', cutoff):
                    already_exists += 1
                else:
                    _insert_signal(ticker, 'SHORT', round(short_score, 4), round(short_score, 4),
                                   round(up_proba, 4), round(auc, 4), round(rr_short, 2),
                                   round(cur, 2), round(short_cover, 2), round(short_stop, 2),
                                   round(vol_ann, 4), 'pipeline')
                    pushed_short += 1

    # ── Auto-push PEAD setups (regardless of conviction) ────────────────────
    for ticker, pead_info in pead_map.items():
        direction = (pead_info.get('direction') or '').lower()
        sig_type  = 'BUY' if direction in ('bullish', 'bull') else 'SHORT'
        q         = (pead_info.get('pead_setup_quality') or '').upper()
        pead_conv = 0.50 + (0.10 if q == 'HIGH' else 0.05 if q == 'MEDIUM' else 0.0)
        source    = 'pead'

        # Only push if we have some price data
        pt_match = next((r for r in targets if r['ticker'] == ticker), None)
        if pt_match:
            cur  = float(pt_match.get('current_price_eur') or 0)
            auc  = float((ml_signals.get(ticker) or {}).get('auc') or 0)
            if _already_pending(ticker, sig_type, cutoff):
                already_exists += 1
                continue
            _insert_signal(ticker, sig_type, pead_conv, None,
                           None, round(auc, 4) if auc else None, None,
                           round(cur, 2) if cur else None, None, None,
                           None, source)
            pushed_pead += 1

    logger.info(
        f"[signal_push] Pushed {pushed_long} long / {pushed_short} short / "
        f"{pushed_pead} PEAD signals — {already_exists} already pending (skipped)"
    )



# ─────────────────────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────────────────────

def send_alert(message: str):
    from engine.alerting.digest import send_alert as _send
    _send(message)


# ─────────────────────────────────────────────────────────────────────────────
# RISK SUMMARY FOR DIGEST
# ─────────────────────────────────────────────────────────────────────────────

def _build_risk_summary() -> dict:
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        metrics_rows = session.execute(text(
            "SELECT metric_name, metric_value FROM risk_metrics WHERE date=:d"
        ), {'d': TODAY}).fetchall()
        violations = session.execute(text(
            "SELECT COUNT(*) FROM risk_events WHERE date=:d AND event_type='pre_trade_violation'"
        ), {'d': TODAY}).fetchone()
        val_row = session.execute(text("""
            SELECT SUM(value_eur) FROM positions_history p
            INNER JOIN (SELECT ticker, MAX(date) AS max_date FROM positions_history GROUP BY ticker)
            latest ON p.ticker=latest.ticker AND p.date=latest.max_date
        """)).fetchone()
        # Bug fix (2026-08-20): 'regime' was never in risk_metrics (see
        # post_trade.py fix note) so this always fell back to 'unknown'.
        # The human-readable label is now logged to pipeline_logs by
        # run_post_trade_risk(); read it back here instead of risk_metrics.
        regime_row = session.execute(text("""
            SELECT detail FROM pipeline_logs
            WHERE step_name='post_trade_risk' AND message LIKE 'Regime label:%'
              AND run_date=:d
            ORDER BY id DESC LIMIT 1
        """), {'d': TODAY}).fetchone()
        # Bug fix (2026-08-20): this used to be stocks-only (SUM(value_eur)
        # from positions_history), while step_performance_log() reports
        # stocks+cash — the digest showed two contradictory "portfolio value"
        # numbers for the same run. Add cash here so both figures agree.
        cash_row = session.execute(text(
            "SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1"
        )).fetchone()
        session.close()
        m = {r[0]: r[1] for r in metrics_rows}
        stock_value = float(val_row[0] or 0)
        cash_value = float(cash_row[0] if cash_row else 0)
        return {
            'var_95': m.get('var_95'),
            'regime': regime_row[0] if regime_row else 'unknown',
            'pre_trade_violations': int(violations[0]) if violations else 0,
            'orders_blocked': int(violations[0] or 0) > 0,
            'stock_value_eur': stock_value,
            'cash_eur': cash_value,
            'portfolio_value_eur': stock_value + cash_value,
        }
    except Exception as e:
        logger.warning(f"Risk summary failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _is_system_halted() -> bool:
    from engine.db.db import get_session
    from sqlalchemy import text
    session = get_session()
    try:
        row = session.execute(text("SELECT is_halted FROM system_halt WHERE id = 1")).fetchone()
        return bool(row[0]) if row else False
    except Exception:
        return False
    finally:
        session.close()

def run_pipeline(dry_run: bool = False):
    global _step_results
    _step_results = []

    logger.info(
        f"{'='*60}\n  Pipeline: {TODAY} (weekday={WEEKDAY})"
        f" {'[DRY RUN]' if dry_run else ''}\n  Tickers: {len(TICKERS)}\n{'='*60}"
    )

    if _is_system_halted():
        logger.warning("[SOS] System is HALTED — skipping pipeline run entirely")
        send_alert("⚠️ Pipeline run skipped — system is in SOS halt state")
        return

    # ── Mirror state files first — ensures shared/state/ is populated even if
    #    regime/PEAD engines haven't run yet (uses last known-good files)
    if not dry_run:
        _mirror_all_state_files()

    # ── Daily steps ───────────────────────────────────────────────────────────
    _run_step('0.  Ledger import',           step_ledger_import,                 dry_run)  # Stream 8
    _run_step('1.  Data ingestion',          step_ingest,                        dry_run)
    _run_step('2.  Macro regime refresh',    step_regime_refresh,                dry_run)
    _run_step('3.  Feature pipeline',        step_features,                      dry_run)
    _run_step('4.  Alpha: momentum',         lambda: step_alpha('momentum'),     dry_run)
    _run_step('4b. Alpha: sector momentum',  lambda: step_alpha('sector_momentum'), dry_run)  # J5
    _run_step('5.  Alpha: mean reversion',   lambda: step_alpha('mean_reversion'),dry_run)
    _run_step('6.  Alpha: vol timing',       lambda: step_alpha('vol_timing'),   dry_run)
    _run_step('8.  Alpha: ML signals',       lambda: step_alpha('ml_model'),     dry_run)
    _run_step('9.  ETF divergence scan',     step_divergence_scan,               dry_run)
    _run_step('10. Outcome fill',            step_outcome_fill,                  dry_run)
    _run_step('11. Portfolio construction',  step_portfolio_construction,        dry_run)
    _run_step('12. Price targets',           step_price_targets,                 dry_run)  # Stream 3
    _run_step('13. Performance logging',      step_performance_log,               dry_run)
    _run_step('14. Signal queue push',         step_push_signals_to_queue,         dry_run)
    _run_step('15. Daily reconciliation',      step_reconciliation,                dry_run)

    _run_step('16. Liquidity classification', step_liquidity_classification, dry_run)
    _run_step('17. ML pipeline refresh',      step_ml_refresh,  dry_run)
    _run_step('18. LSTM train all',           step_lstm_train,  dry_run)

    logger.info(f"{'='*60}\n  Pipeline complete: {TODAY}\n{'='*60}")

    # ── End-of-run digest (Stream 9) ─────────────────────────────────────────
    if not dry_run:
        if os.getenv("SANDBOX_MODE") == "1":
            logger.info("🧪 Sandbox mode: skipping email/slack digest.")
        else:
            try:
                from engine.alerting.digest import send_digest
                send_digest(step_results=_step_results, date=TODAY,
                            risk_summary=_build_risk_summary())
            except Exception as e:
                logger.warning(f"Digest send failed (non-fatal): {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hedge Fund daily pipeline scheduler')
    parser.add_argument('--test', '--dry-run', action='store_true',
                        help='Dry run — logs steps without executing them')
    parser.add_argument('--pipeline-only', action='store_true',
                        help='Run pipeline only (same as default — accepted for BAT compatibility)')
    args = parser.parse_args()
    run_pipeline(dry_run=args.test)
