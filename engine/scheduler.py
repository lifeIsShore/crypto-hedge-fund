# engine/scheduler.py
"""
Daily pipeline scheduler.

Usage:
  python -m engine.scheduler            # run now
  python -m engine.scheduler --test     # dry run (skips actual ingestion/BL)

Schedule (cron example — 22:00 UTC = after US market close Mon-Fri):
  0 22 * * 1-5 cd /path/to/hedge-fund && python -m engine.scheduler

Step frequencies:
  Daily (every trading day):
    data ingestion, features, alpha signals, divergence scan,
    portfolio construction (BL → optimizer → pre-trade → orders → post-trade risk),
    regime engine refresh (writes shared/state/regime_state.json)

  Weekly (Monday):
    PEAD engine full refresh (writes shared/state/pead_setups.csv)

  Weekend (Saturday):
    ML pipeline full refresh (writes shared/state/ml_state.json)
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
    TICKERS = ASSET_UNIVERSE[:50]
except Exception as e:
    logger.error(f"Could not import ASSET_UNIVERSE from portfolio/src/config.py: {e}")
    TICKERS = ['APC.DE', 'MSF.DE', 'NVDA', 'SAP.DE', 'EUNL.DE']

TODAY   = str(datetime.date.today())
WEEKDAY = datetime.date.today().weekday()   # 0=Mon, 5=Sat, 6=Sun
HISTORY_START = '2022-01-01'


# ─────────────────────────────────────────────────────────────────────────────
# STEP RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def _run_step(name: str, fn, dry_run: bool = False):
    import time
    logger.info(f"▶ {name}")
    start = time.time()

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
        pass


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STEPS
# ─────────────────────────────────────────────────────────────────────────────

def step_ingest():
    from engine.data.ingestion import run_ingestion
    run_ingestion(TICKERS, HISTORY_START, TODAY)


def step_regime_refresh():
    """
    Runs the macro regime engine to refresh shared/state/regime_state.json.
    Must run BEFORE step_features so the macro features are available.
    Non-fatal: if regime_engine is not set up the feature store continues
    without macro features (statistical regime still computed from prices).
    """
    import subprocess
    _HERE_SCHED = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(_HERE_SCHED, '..'))
    regime_dir = os.path.join(
        project_root, 'ml_quant_finance_research', 'quant_research', 'regime_engine'
    )

    if not os.path.isdir(regime_dir):
        logger.warning(f"[regime] regime_engine dir not found: {regime_dir} — skipping")
        return

    try:
        result = subprocess.run(
            [sys.executable, 'run_engine.py'],
            cwd=regime_dir,
            capture_output=True,
            text=True,
            timeout=300,   # 5 minute cap — FRED data + classification
        )
        if result.returncode != 0:
            logger.warning(f"[regime] Engine returned non-zero:\n{result.stderr[-500:]}")
        else:
            logger.info("[regime] regime_state.json updated successfully")
            # Copy output to shared/state (regime_engine writes to its own data/ dir;
            # we mirror it to shared/state/ so the engine can read from one location)
            _mirror_regime_to_shared(regime_dir, project_root)
    except subprocess.TimeoutExpired:
        logger.error("[regime] Engine timed out after 5 minutes")
    except Exception as e:
        logger.error(f"[regime] Engine failed: {e}")


def _mirror_regime_to_shared(regime_dir: str, project_root: str):
    """
    Copies regime_state.json and regime_history.csv from the regime_engine's
    own data/ directory into shared/state/ so the engine reads from one place.
    """
    import shutil
    from shared.state_paths import REGIME_STATE_PATH, REGIME_HISTORY_PATH, ensure_state_dir
    ensure_state_dir()

    src_state   = os.path.join(regime_dir, 'data', 'regime_state.json')
    src_history = os.path.join(regime_dir, 'data', 'regime_history.csv')

    if os.path.exists(src_state):
        shutil.copy2(src_state, REGIME_STATE_PATH)
        logger.info(f"[regime] regime_state.json → shared/state/")
    if os.path.exists(src_history):
        shutil.copy2(src_history, REGIME_HISTORY_PATH)
        logger.info(f"[regime] regime_history.csv → shared/state/")


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
    Full portfolio construction loop:
      1. Load covariance matrix and current weights from DB
      2. Load regime info — BOTH statistical (stress_score) and macro (composite label)
      3. Run Black-Litterman → posterior expected returns
      4. Run constrained optimizer → suggested weights
      5. Persist model outputs (suggested vs current weights)
      6. Run pre-trade risk checks → block if violations
      7. Generate order queue and persist to DB
      8. Run post-trade risk snapshot
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

    # ── 1. Covariance matrix ─────────────────────────────────────────────────
    log_returns = load_returns_from_db(TICKERS, lookback_days=252)
    if log_returns.empty:
        logger.error("[portfolio] No returns in DB — skipping portfolio construction")
        return

    available_tickers = [t for t in TICKERS if t in log_returns.columns]
    if len(available_tickers) < 2:
        logger.error("[portfolio] Fewer than 2 tickers with data — skipping")
        return

    cov_matrix = log_returns[available_tickers].cov() * 252

    # ── 2. Current weights from DB ───────────────────────────────────────────
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

    market_weights = pd.Series(
        1.0 / len(available_tickers), index=available_tickers
    )

    # ── 3. Regime info — merged from feature_store ───────────────────────────
    #
    # The feature store now holds BOTH:
    #   - Statistical regime: stress_score, regime_high/medium/low
    #   - Macro regime: macro_risk_on/off, macro_expansion/slowdown, macro_ew_transition
    #
    # We load all and build a unified regime_info dict for Black-Litterman.
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

            # Statistical regime (vol + correlation)
            if feat.get('regime_high', 0):
                stat_regime = 'high_stress'
            elif feat.get('regime_low', 0):
                stat_regime = 'low_stress'
            else:
                stat_regime = 'medium'

            # Macro regime (3-axis)
            macro_composite = []
            if feat.get('macro_risk_on', 0):   macro_composite.append('RiskOn')
            elif feat.get('macro_risk_off', 0): macro_composite.append('RiskOff')
            else:                               macro_composite.append('Neutral')
            if feat.get('macro_easing', 0):     macro_composite.append('Easing')
            elif feat.get('macro_tightening',0): macro_composite.append('Tightening')
            else:                               macro_composite.append('Neutral')
            if feat.get('macro_expansion', 0):  macro_composite.append('Expansion')
            elif feat.get('macro_contraction',0):macro_composite.append('Contraction')
            elif feat.get('macro_recovery', 0): macro_composite.append('Recovery')
            else:                               macro_composite.append('Slowdown')

            regime_info = {
                # Statistical regime fields (used by build_regime_views)
                'regime':       stat_regime,
                'stress_score': feat.get('stress_score', 0.5),
                # Macro regime fields (informational + used for BL scaling)
                'macro_composite':    '_'.join(macro_composite),
                'macro_risk_on':      bool(feat.get('macro_risk_on', 0)),
                'macro_risk_off':     bool(feat.get('macro_risk_off', 0)),
                'macro_expansion':    bool(feat.get('macro_expansion', 0)),
                'macro_ew_transition': bool(feat.get('macro_ew_transition', 0)),
                'macro_ew_count':     int(feat.get('macro_ew_count', 0)),
                'macro_vix':          feat.get('macro_vix', 20.0),
            }

            logger.info(
                f"[portfolio] Statistical regime: {stat_regime} "
                f"(stress={regime_info['stress_score']:.2f}) | "
                f"Macro: {regime_info['macro_composite']} | "
                f"EW={regime_info['macro_ew_transition']}"
            )
    except Exception as e:
        logger.warning(f"[portfolio] Could not load regime features: {e}")

    # ── 4. Instantiate alpha models ──────────────────────────────────────────
    from engine.alpha.momentum       import MomentumAlpha
    from engine.alpha.mean_reversion import MeanReversionAlpha
    from engine.alpha.vol_timing     import VolTimingAlpha
    from engine.alpha.pead_alpha     import PEADAlpha
    from engine.alpha.ml_alpha       import MLAlpha
    models_dict = {
        'momentum':       MomentumAlpha(),
        'mean_reversion': MeanReversionAlpha(),
        'vol_timing':     VolTimingAlpha(),
        'pead':           PEADAlpha(),
        'ml_model':       MLAlpha(),
    }

    # ── 5. Black-Litterman → posterior expected returns ──────────────────────
    mu_bl = run_black_litterman(
        tickers=available_tickers,
        cov_matrix=cov_matrix,
        market_weights=market_weights,
        date=TODAY,
        regime_info=regime_info,
        models_dict=models_dict,
    )
    logger.info(f"[portfolio] BL returns computed for {len(mu_bl)} tickers")

    # ── 6. Optimizer → suggested weights ────────────────────────────────────
    suggested_weights = optimize_with_bl(
        mu_bl=mu_bl,
        cov_matrix=cov_matrix,
        current_weights=current_weights,
    )
    logger.info(
        f"[portfolio] Optimized weights: "
        f"top5={suggested_weights.nlargest(5).to_dict()}"
    )

    persist_model_outputs(TODAY, suggested_weights, current_weights, mu_bl)

    # ── 7. Pre-trade risk checks ─────────────────────────────────────────────
    pre_trade = run_pre_trade_checks(suggested_weights)
    if not pre_trade['passed']:
        logger.warning(
            f"[portfolio] Pre-trade checks FAILED — order queue blocked.\n"
            f"Violations: {pre_trade['violations']}"
        )
        send_alert(f"Pre-trade checks failed:\n" + "\n".join(pre_trade['violations']))
        run_post_trade_risk(
            weights=current_weights.to_dict(),
            tickers=available_tickers,
        )
        return

    # ── 8. Generate order queue ──────────────────────────────────────────────
    session3 = get_session()
    val_row = session3.execute(text("""
        SELECT SUM(value_eur) FROM positions_history p
        INNER JOIN (
            SELECT ticker, MAX(date) AS max_date
            FROM positions_history GROUP BY ticker
        ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
    """)).fetchone()
    cash_row = session3.execute(text("""
        SELECT cash_eur FROM cash_history ORDER BY date DESC, id DESC LIMIT 1
    """)).fetchone()
    session3.close()

    portfolio_value = float(val_row[0] or 0) + float(cash_row[0] if cash_row else 0)
    if portfolio_value < 100:
        logger.warning("[portfolio] Portfolio value too low — using €10,000 default")
        portfolio_value = 10_000.0

    orders = generate_order_queue(
        suggested_weights=suggested_weights,
        current_weights=current_weights,
        total_portfolio_eur=portfolio_value,
    )
    logger.info(f"[portfolio] Order queue: {len(orders)} orders (portfolio=€{portfolio_value:,.0f})")
    for o in orders:
        logger.info(f"  {o.action:4s} {o.ticker:12s} €{o.value_eur:>8.2f}")

    # ── 9. Post-trade risk snapshot ──────────────────────────────────────────
    run_post_trade_risk(
        weights=suggested_weights.to_dict(),
        tickers=available_tickers,
    )


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
    logger.critical(f"🚨 ALERT: {message}")

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
    #
    # IMPORTANT: regime refresh runs BEFORE features so that macro regime
    # features (from regime_state.json) are available when feature_store runs.
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
