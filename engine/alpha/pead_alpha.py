# engine/alpha/pead_alpha.py
"""
Alpha Model 4 — Post-Earnings Announcement Drift (PEAD).
Wraps the existing quant_research/pead_engine/ — reads pead_setups.csv daily.
Full engine refresh runs weekly (Monday) via run_pead_engine_weekly().

Quality → expected return calibration:
  High:   +3.5% (71% historical hit rate per pead_state.json performance block)
  Medium: +1.5% (57% historical hit rate)
  Low:    excluded (no edge above random)
"""

import os
import sys
import pandas as pd
import logging
from engine.alpha.base import AlphaModel

logger = logging.getLogger(__name__)

# Path to the PEAD engine data file (written by run_engine.py)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
PEAD_SETUPS_PATH = os.path.join(
    _PROJECT_ROOT,
    'ml_quant_finance_research', 'quant_research', 'pead_engine', 'data', 'pead_setups.csv'
)

QUALITY_RETURN_MAP = {
    'High':          0.035,
    'Medium':        0.015,
    'Low':           0.000,
    'Disqualified':  0.000,
}
DIRECTION_SIGN = {'bullish': 1, 'bearish': -1}
ACTIVE_WINDOW_DAYS = 7   # only use setups entered in last 7 days


class PEADAlpha(AlphaModel):
    name = 'pead'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Reads pead_setups.csv and converts active High/Medium quality setups
        into standardised alpha signals.
        """
        if not os.path.exists(PEAD_SETUPS_PATH):
            logger.warning(
                f"[pead] pead_setups.csv not found at {PEAD_SETUPS_PATH} — "
                "run the PEAD engine weekly refresh first"
            )
            return pd.DataFrame()

        try:
            setups = pd.read_csv(PEAD_SETUPS_PATH)
        except Exception as e:
            logger.warning(f"[pead] Failed to read pead_setups.csv: {e}")
            return pd.DataFrame()

        if setups.empty:
            logger.info(f"[pead] pead_setups.csv is empty")
            return pd.DataFrame()

        # Normalise column names (the PEAD engine uses 'pead_setup_quality')
        qual_col = next(
            (c for c in setups.columns if 'quality' in c.lower()), None
        )
        ticker_col = next(
            (c for c in ['ticker', 'symbol', 'Ticker'] if c in setups.columns), None
        )
        if qual_col is None or ticker_col is None:
            logger.warning(f"[pead] Unexpected column structure: {list(setups.columns)}")
            return pd.DataFrame()

        setups = setups.rename(columns={ticker_col: 'ticker', qual_col: 'quality'})

        # Filter: active (entry_date within last ACTIVE_WINDOW_DAYS), in universe, quality > Low
        if 'entry_date' in setups.columns:
            setups['entry_date'] = pd.to_datetime(setups['entry_date'], errors='coerce')
            current_date   = pd.Timestamp(date)
            active_cutoff  = current_date - pd.Timedelta(days=ACTIVE_WINDOW_DAYS)
            setups = setups[
                (setups['entry_date'] >= active_cutoff) &
                (setups['entry_date'] <= current_date)
            ]

        setups = setups[
            setups['ticker'].isin(tickers) &
            setups['quality'].isin(['High', 'Medium'])
        ].copy()

        if setups.empty:
            logger.info(f"[pead] No active High/Medium quality setups for {date}")
            return pd.DataFrame()

        ic = self.compute_rolling_ic()
        rows = []

        for _, row in setups.iterrows():
            quality   = row.get('quality', 'Low')
            direction = row.get('direction', 'bullish')
            surprise  = float(row.get('surprise_pct', 0)) if pd.notna(row.get('surprise_pct')) else 0.0
            underreact = bool(row.get('underreaction_flag', False))

            base_return = QUALITY_RETURN_MAP.get(quality, 0.0)
            if base_return == 0.0:
                continue

            sign       = DIRECTION_SIGN.get(direction, 1)
            multiplier = 1.3 if underreact else 1.0
            expected   = sign * base_return * multiplier

            # raw_score: normalised surprise (bounded [0, 1])
            raw_score = min(abs(surprise) / 20.0, 1.0) * sign

            rows.append({
                'ticker':          row['ticker'],
                'expected_return': round(expected, 4),
                'confidence':      ic,
                'raw_score':       raw_score,
            })

        result = pd.DataFrame(rows)
        if not result.empty:
            logger.info(f"[pead] {len(result)} signals generated for {date}")
        return result


def run_pead_engine_weekly():
    """
    Runs the full PEAD engine to refresh pead_setups.csv.
    Call from scheduler on Mondays only — takes several minutes.
    """
    pead_dir = os.path.join(
        _PROJECT_ROOT,
        'ml_quant_finance_research', 'quant_research', 'pead_engine'
    )
    original_dir = os.getcwd()
    try:
        os.chdir(pead_dir)
        sys.path.insert(0, '.')
        from run_engine import run
        state = run(force_refresh=False, lookback_days=90, backfill_models=False)
        n_active = len(state.get('active_setups', []))
        logger.info(f"[pead] Weekly refresh complete: {n_active} active setups")
        return state
    except Exception as e:
        logger.error(f"[pead] Weekly engine refresh failed: {e}")
        return {}
    finally:
        os.chdir(original_dir)
        if '.' in sys.path:
            sys.path.remove('.')
