# engine/alpha/ml_alpha.py
"""
Alpha Model 5 — ML ensemble from stock_ml_lab.
Reads shared/state/ml_state.json (written by run_ml_pipeline.py).
Full pipeline refresh runs on Saturdays via run_ml_pipeline_refresh().

Signal logic:
  up_proba_21d > 0.5 → positive expected return
  AUC < 0.53 → model has no meaningful edge → signal excluded
  AUC used directly as confidence (scaled to [0, 1]).
"""

import os
import json
import subprocess
import pandas as pd
import logging
from datetime import datetime
from engine.alpha.base import AlphaModel
from shared.state_paths import ML_STATE_PATH, ensure_state_dir

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))

ML_LAB_PATH = os.path.join(
    _PROJECT_ROOT,
    'ml_quant_finance_research', 'ml_research', 'stock_ml_lab'
)

MIN_AUC         = 0.53    # below this = no meaningful edge
RETURN_SCALE    = 0.04    # 4% scale for up_proba extremes
MAX_STALE_DAYS  = 8       # warn if ml_state.json older than this


class MLAlpha(AlphaModel):
    name = 'ml_model'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Reads shared/state/ml_state.json model_signals block.
        up_proba_21d drives expected_return; AUC drives confidence.
        """
        if not os.path.exists(ML_STATE_PATH):
            logger.warning(
                f"[ml] ml_state.json not found at {ML_STATE_PATH} — "
                "run Saturday ML pipeline refresh first"
            )
            return pd.DataFrame()

        try:
            with open(ML_STATE_PATH, 'r') as f:
                state = json.load(f)
        except Exception as e:
            logger.warning(f"[ml] Failed to read ml_state.json: {e}")
            return pd.DataFrame()

        # Staleness check
        generated_at = state.get('generated_at', '')
        if generated_at:
            try:
                age_days = (datetime.now() - datetime.fromisoformat(generated_at)).days
                if age_days > MAX_STALE_DAYS:
                    logger.warning(
                        f"[ml] ml_state.json is {age_days} days old — "
                        "consider running the ML pipeline refresh"
                    )
            except Exception:
                pass

        model_signals = state.get('model_signals', {})
        if not model_signals:
            logger.warning("[ml] model_signals is empty in ml_state.json")
            return pd.DataFrame()

        ic = self.compute_rolling_ic()
        rows = []

        for ticker, signal in model_signals.items():
            if ticker not in tickers:
                continue

            up_proba = float(signal.get('up_proba_21d', 0.5))
            auc      = float(signal.get('auc', 0.5))

            # Gate: exclude low-AUC models
            if auc < MIN_AUC:
                logger.debug(f"[ml] Skipping {ticker}: AUC {auc:.3f} < {MIN_AUC}")
                continue

            # Expected return: centred at 0 for up_proba=0.5
            prob_edge       = (up_proba - 0.5) * 2   # [-1, +1]
            expected_return = prob_edge * RETURN_SCALE

            # Confidence: rescale AUC [0.5, 0.75] → [0, 1]
            confidence = min(max((auc - 0.5) * 4, 0.01), 1.0)

            rows.append({
                'ticker':          ticker,
                'expected_return': round(expected_return, 4),
                'confidence':      round(confidence, 4),
                'raw_score':       round(up_proba, 4),
            })

        result = pd.DataFrame(rows)
        if not result.empty:
            logger.info(
                f"[ml] {len(result)} signals generated "
                f"(of {len(model_signals)} in state), date={date}"
            )
        return result


def run_ml_pipeline_refresh():
    """
    Runs the full ML pipeline to refresh shared/state/ml_state.json.
    Call from scheduler on Saturdays only — takes 20-40 minutes.
    """
    ensure_state_dir()

    if not os.path.isdir(ML_LAB_PATH):
        logger.error(f"[ml] ML lab directory not found: {ML_LAB_PATH}")
        return

    try:
        logger.info("[ml] Starting ML pipeline refresh (this takes 20-40 minutes)...")
        result = subprocess.run(
            ['python', 'run_ml_pipeline.py'],
            cwd=ML_LAB_PATH,
            capture_output=True,
            text=True,
            timeout=3600,  # 60 minute hard cap
        )
        if result.returncode != 0:
            logger.error(f"[ml] Pipeline failed:\n{result.stderr[-1000:]}")
        else:
            logger.info(f"[ml] ML pipeline complete — ml_state.json updated at {ML_STATE_PATH}")
    except subprocess.TimeoutExpired:
        logger.error("[ml] ML pipeline timed out after 60 minutes")
    except Exception as e:
        logger.error(f"[ml] ML pipeline refresh error: {e}")
