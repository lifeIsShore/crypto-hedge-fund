# engine/scheduler.py
"""
Daily pipeline scheduler.

Usage:
  python -m engine.scheduler            # run now
  python -m engine.scheduler --test     # dry run (skips actual ingestion/BL)

Schedule (cron example — 22:00 UTC = after US market close Mon–Fri):
  0 22 * * 1-5 cd /path/to/hedge-fund && python -m engine.scheduler

Step frequencies:
  Daily (every trading day):    data ingestion, features, alpha signals, divergence scan
  Weekly (Monday):              PEAD engine full refresh
  Weekend (Saturday):           ML pipeline full refresh
"""

import logging
import datetime
import traceback
import argparse
import sys
import os

# Ensure project root is on sys.path when run as a script
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
    # Cap at 50 for initial runs — expand as DB fills with history
    TICKERS = ASSET_UNIVERSE[:50]
except Exception as e:
    logger.error(f"Could not import ASSET_UNIVERSE from portfolio/src/config.py: {e}")
    TICKERS = ['APC.DE', 'MSF.DE', 'NVDA', 'SAP.DE', 'EUNL.DE']  # fallback for testing

TODAY   = str(datetime.date.today())
WEEKDAY = datetime.date.today().weekday()   # 0=Mon, 5=Sat, 6=Sun

# How many years of history to load on first run
HISTORY_START = '2022-01-01'


# ─────────────────────────────────────────────────────────────────────────────
# STEP RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def _run_step(name: str, fn, dry_run: bool = False):
    """Runs a pipeline step, logs duration, catches and logs errors."""
    import time
    logger.info(f"▶ {name}")
    start = time.time()
    status = 'success'

    if dry_run:
        logger.info(f"  [DRY RUN] Skipped")
        _log_pipeline_run(name, 'skipped', 0)
        return

    try:
        fn()
        elapsed = round(time.time() - start, 1)
        logger.info(f"✅ {name} ({elapsed}s)")
        _log_pipeline_run(name, 'success', elapsed)
    except Exception as e:
        elapsed = round(time.time() - start, 1)
        logger.error(f"❌ {name} FAILED after {elapsed}s: {e}")
        logger.error(traceback.format_exc())
        _log_pipeline_run(name, 'failed', elapsed, str(e)[:500])
        send_alert(f"Pipeline step FAILED: {name}\n{e}")


def _log_pipeline_run(step_name: str, status: str, duration_sec: float, error_msg: str = None):
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        session.execute(text("""
            INSERT INTO pipeline_runs (run_date, step_name, status, duration_sec, error_msg)
            VALUES (CURRENT_DATE, :step, :status, :duration, :error)
        """), {
            'step':     step_name,
            'status':   status,
            'duration': duration_sec,
            'error':    error_msg,
        })
        session.commit()
        session.close()
    except Exception:
        pass  # don't let audit logging crash the pipeline


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────────────────────────────────────

def step_ingest():
    from engine.data.ingestion import run_ingestion
    run_ingestion(TICKERS, HISTORY_START, TODAY)


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
        'momentum':      MomentumAlpha(),
        'mean_reversion': MeanReversionAlpha(),
        'vol_timing':    VolTimingAlpha(),
        'pead':          PEADAlpha(),
        'ml_model':      MLAlpha(),
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


def step_pead_refresh():
    from engine.alpha.pead_alpha import run_pead_engine_weekly
    run_pead_engine_weekly()


def step_ml_refresh():
    from engine.alpha.ml_alpha import run_ml_pipeline_refresh
    run_ml_pipeline_refresh()


# ─────────────────────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────────────────────

def send_alert(message: str):
    """
    Logs a CRITICAL alert. Extend with smtplib or slack_sdk for real alerts.
    """
    logger.critical(f"🚨 ALERT: {message}")

    # Optional: Slack webhook
    slack_url = os.getenv('SLACK_WEBHOOK_URL', '')
    if slack_url:
        try:
            import urllib.request
            import json as _json
            data = _json.dumps({'text': f'🚨 Hedge Fund Alert:\n{message}'}).encode()
            req  = urllib.request.Request(slack_url, data=data,
                                          headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.warning(f"Slack alert failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(dry_run: bool = False):
    logger.info(
        f"{'='*60}\n"
        f"  Pipeline: {TODAY} (weekday={WEEKDAY}) "
        f"{'[DRY RUN]' if dry_run else ''}\n"
        f"  Tickers: {len(TICKERS)}\n"
        f"{'='*60}"
    )

    # ── Daily steps ───────────────────────────────────────────────────────────
    _run_step('1. Data ingestion',          step_ingest,                   dry_run)
    _run_step('2. Feature pipeline',        step_features,                 dry_run)
    _run_step('3. Alpha: momentum',         lambda: step_alpha('momentum'),      dry_run)
    _run_step('4. Alpha: mean reversion',   lambda: step_alpha('mean_reversion'),dry_run)
    _run_step('5. Alpha: vol timing',       lambda: step_alpha('vol_timing'),    dry_run)
    _run_step('6. Alpha: PEAD signals',     lambda: step_alpha('pead'),          dry_run)
    _run_step('7. Alpha: ML signals',       lambda: step_alpha('ml_model'),      dry_run)
    _run_step('8. ETF divergence scan',     step_divergence_scan,          dry_run)
    _run_step('9. Outcome fill',            step_outcome_fill,             dry_run)

    # ── Weekly steps (Monday) ─────────────────────────────────────────────────
    if WEEKDAY == 0:
        _run_step('W1. PEAD weekly refresh', step_pead_refresh, dry_run)

    # ── Weekend steps (Saturday) ──────────────────────────────────────────────
    if WEEKDAY == 5:
        _run_step('WE1. ML pipeline refresh', step_ml_refresh, dry_run)

    logger.info(f"{'='*60}\n  Pipeline complete: {TODAY}\n{'='*60}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hedge Fund daily pipeline scheduler')
    parser.add_argument('--test', '--dry-run', action='store_true',
                        help='Dry run — logs steps without executing them')
    args = parser.parse_args()
    run_pipeline(dry_run=args.test)
