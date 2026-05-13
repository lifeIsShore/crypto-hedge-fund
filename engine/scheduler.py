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
    from engine.data.ingestion import run_ingestion
    run_ingestion(TICKERS, HISTORY_START, TODAY)


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

    copied, skipped = 0, 0
    seen_dest = set()
    for src, dst in copies:
        if dst in seen_dest:          # don't overwrite with a less-preferred source
            continue
        if os.path.exists(src):
            shutil.copy2(src, dst)
            seen_dest.add(dst)
            copied += 1
            logger.info(f"[mirror] {os.path.basename(src)} → shared/state/")
        else:
            skipped += 1

    logger.info(f"[mirror] {copied} files copied, {skipped} sources not found")


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
            [sys.executable, 'run_engine.py'],
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
                        (date, regime_risk, regime_rates, regime_growth, regime_composite,
                         transition_warning, ew_active_count,
                         vix, yield_spread, hy_spread, fed_funds, computed_at)
                    VALUES (:date,:risk,:rates,:growth,:composite,:ew_flag,:ew_count,
                            :vix,:yield_spread,:hy_spread,:fed_funds,datetime('now'))
                    ON CONFLICT(date) DO UPDATE SET
                        regime_risk=:risk, regime_rates=:rates, regime_growth=:growth,
                        regime_composite=:composite, transition_warning=:ew_flag,
                        ew_active_count=:ew_count, vix=:vix,
                        yield_spread=:yield_spread, hy_spread=:hy_spread, fed_funds=:fed_funds
                """), {
                    'date': str(row.get('date', '')),
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


def step_alpha(model_name: str):
    from engine.alpha.momentum       import MomentumAlpha
    from engine.alpha.mean_reversion import MeanReversionAlpha
    from engine.alpha.vol_timing     import VolTimingAlpha
    from engine.alpha.pead_alpha     import PEADAlpha
    from engine.alpha.ml_alpha       import MLAlpha

    model_map = {
        'momentum':       MomentumAlpha(),
        'mean_reversion': MeanReversionAlpha(),
        'vol_timing':     VolTimingAlpha(),
        'pead':           PEADAlpha(),
        'ml_model':       MLAlpha(),
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

    from engine.alpha.momentum       import MomentumAlpha
    from engine.alpha.mean_reversion import MeanReversionAlpha
    from engine.alpha.vol_timing     import VolTimingAlpha
    from engine.alpha.pead_alpha     import PEADAlpha
    from engine.alpha.ml_alpha       import MLAlpha
    models_dict = {
        'momentum': MomentumAlpha(), 'mean_reversion': MeanReversionAlpha(),
        'vol_timing': VolTimingAlpha(), 'pead': PEADAlpha(), 'ml_model': MLAlpha(),
    }

    mu_bl = run_black_litterman(
        tickers=available_tickers, cov_matrix=cov_matrix,
        market_weights=market_weights, date=TODAY,
        regime_info=regime_info, models_dict=models_dict,
    )

    suggested_weights = optimize_with_bl(
        mu_bl=mu_bl, cov_matrix=cov_matrix, current_weights=current_weights,
    )
    persist_model_outputs(TODAY, suggested_weights, current_weights, mu_bl)

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
    for o in orders:
        logger.info(f"  {o.action:4s} {o.ticker:12s} €{o.value_eur:>8.2f}")

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


def step_lstm_train():
    """Saturday — walk-forward train LSTM for all tickers and save models."""
    from engine.alpha.lstm_model import LSTMAlpha
    model = LSTMAlpha()
    summary = model.train_all(tickers=TICKERS, date=TODAY)
    passed = sum(1 for v in summary.values() if v.get('auc', 0) >= 0.53)
    logger.info(f"[lstm_train] {passed}/{len(summary)} tickers above AUC gate")


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
        session.close()
        m = {r[0]: r[1] for r in metrics_rows}
        return {
            'var_95': m.get('var_95'), 'regime': m.get('regime', 'unknown'),
            'pre_trade_violations': int(violations[0]) if violations else 0,
            'orders_blocked': int(violations[0] or 0) > 0,
            'portfolio_value_eur': float(val_row[0] or 0),
        }
    except Exception as e:
        logger.warning(f"Risk summary failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False):
    global _step_results
    _step_results = []

    logger.info(
        f"{'='*60}\n  Pipeline: {TODAY} (weekday={WEEKDAY})"
        f" {'[DRY RUN]' if dry_run else ''}\n  Tickers: {len(TICKERS)}\n{'='*60}"
    )

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
    _run_step('5.  Alpha: mean reversion',   lambda: step_alpha('mean_reversion'),dry_run)
    _run_step('6.  Alpha: vol timing',       lambda: step_alpha('vol_timing'),   dry_run)
    _run_step('7.  Alpha: PEAD signals',     lambda: step_alpha('pead'),         dry_run)
    _run_step('8.  Alpha: ML signals',       lambda: step_alpha('ml_model'),     dry_run)
    _run_step('9.  ETF divergence scan',     step_divergence_scan,               dry_run)
    _run_step('10. Outcome fill',            step_outcome_fill,                  dry_run)
    _run_step('11. Portfolio construction',  step_portfolio_construction,        dry_run)
    _run_step('12. Price targets',           step_price_targets,                 dry_run)  # Stream 3

    # ── Weekly steps (Monday) ─────────────────────────────────────────────────
    if WEEKDAY == 0:
        _run_step('W1. PEAD weekly refresh', step_pead_refresh, dry_run)

    # ── Weekend steps (Saturday) ──────────────────────────────────────────────
    if WEEKDAY == 5:
        _run_step('WE1. ML pipeline refresh', step_ml_refresh,  dry_run)
        _run_step('WE2. LSTM train all',       step_lstm_train,  dry_run)

    logger.info(f"{'='*60}\n  Pipeline complete: {TODAY}\n{'='*60}")

    # ── End-of-run digest (Stream 9) ─────────────────────────────────────────
    if not dry_run:
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
