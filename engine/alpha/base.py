# engine/alpha/base.py
"""
Abstract base class for all alpha models.
Every model produces a standard signal DataFrame:
  ticker | expected_return | confidence | raw_score | up_proba

CONTRACT (enforced by validate_signals()):
  up_proba   : float in [0.0, 1.0]  — probability ticker is up in 21d
  confidence : float in [0.0, 1.0]  — model quality (AUC rescaled or IC)
  expected_return: float, centred at 0 for up_proba=0.5
  raw_score  : float, model-specific pre-scaling score

confidence = Information Coefficient (IC) or AUC — controls BL view weight.
Models with IC < 0.05 for < 21 consecutive days are gated from influencing weights.
"""

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

MIN_IC_TO_LIVE     = 0.05   # IC threshold for live approval
MIN_LIVE_DAYS      = 21     # must sustain MIN_IC for this many consecutive trading days


def validate_signals(df: pd.DataFrame, model_name: str = 'unknown') -> pd.DataFrame:
    """
    Enforces the up_proba contract on any signal DataFrame before it is
    persisted or used for portfolio construction.

    Rules:
      - up_proba column added if missing (defaults to 0.5 = no view)
      - up_proba clipped to [0.0, 1.0]  — hard contract
      - confidence clipped to [0.0, 1.0]
      - expected_return filled to 0.0 if missing
      - NaN rows dropped with a warning

    Returns a clean copy of the DataFrame.
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # Ensure required columns exist
    if 'up_proba' not in df.columns:
        # Back-fill from raw_score if available (raw_score is often already [0,1])
        if 'raw_score' in df.columns:
            df['up_proba'] = df['raw_score'].clip(0.0, 1.0)
        else:
            df['up_proba'] = 0.5
        logger.debug(f"[{model_name}] validate_signals: added up_proba column")

    if 'expected_return' not in df.columns:
        df['expected_return'] = 0.0

    if 'confidence' not in df.columns:
        df['confidence'] = 0.05

    # Clip to contract bounds
    df['up_proba']   = df['up_proba'].clip(0.0, 1.0).astype(float)
    df['confidence'] = df['confidence'].clip(0.0, 1.0).astype(float)

    # Drop NaN rows
    before = len(df)
    df = df.dropna(subset=['ticker', 'up_proba', 'confidence'])
    if len(df) < before:
        logger.warning(
            f"[{model_name}] validate_signals: dropped {before - len(df)} NaN rows"
        )

    return df


class AlphaModel(ABC):
    name: str = 'base'

    @abstractmethod
    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Must return DataFrame with columns:
            ticker, expected_return, confidence, raw_score
        or empty DataFrame if no signals.
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # PERSISTENCE
    # ─────────────────────────────────────────────────────────────────────────

    def persist_signals(self, date: str, signals_df: pd.DataFrame):
        """Validate contract, then write signals to the signals table (upsert on conflict)."""
        if signals_df is None or signals_df.empty:
            return

        # Enforce up_proba contract before any DB write
        signals_df = validate_signals(signals_df, model_name=self.name)

        from engine.db.db import get_session

        session = get_session()
        try:
            for _, row in signals_df.iterrows():
                session.execute(text("""
                    INSERT INTO signals
                        (date, ticker, model_name, expected_return, confidence, raw_score, computed_at)
                    VALUES
                        (:date, :ticker, :model_name, :expected_return, :confidence, :raw_score, datetime('now'))
                    ON CONFLICT (date, ticker, model_name) DO UPDATE SET
                        expected_return = :expected_return,
                        confidence      = :confidence,
                        raw_score       = :raw_score,
                        computed_at     = datetime('now')
                """), {
                    'date':            date,
                    'ticker':          row['ticker'],
                    'model_name':      self.name,
                    'expected_return': float(row['expected_return']),
                    'confidence':      float(row['confidence']),
                    'raw_score':       float(row['raw_score']),
                })
            session.commit()
            logger.info(f"[{self.name}] Persisted {len(signals_df)} signals for {date}")
        except Exception as e:
            session.rollback()
            logger.error(f"[{self.name}] persist_signals failed: {e}")
            raise
        finally:
            session.close()

    # ─────────────────────────────────────────────────────────────────────────
    # IC TRACKING
    # ─────────────────────────────────────────────────────────────────────────

    def compute_rolling_ic(self, lookback_days: int = 63) -> float:
        """
        Information Coefficient: Pearson correlation between yesterday's
        raw_score and next-day actual return, rolled over lookback_days.

        Returns IC as a float. Defaults to 0.05 when insufficient history
        (forces moderate uncertainty — model not penalised but not trusted).
        Returns the raw IC (can be negative) so callers can detect bad models;
        use max(0.01, ic) only when feeding into BL omega.
        """
        try:
            from engine.db.db import get_session
            from scipy.stats import pearsonr
            import datetime

            cutoff = (datetime.date.today() - datetime.timedelta(days=lookback_days + 5)).isoformat()

            session = get_session()
            result = session.execute(text("""
                SELECT s.date, s.ticker, s.raw_score,
                       p_next.adj_close / NULLIF(p_curr.adj_close, 0) - 1 AS fwd_return
                FROM signals s
                JOIN prices p_curr ON s.date    = p_curr.date AND s.ticker = p_curr.ticker
                JOIN prices p_next ON p_next.ticker = s.ticker
                    AND p_next.date = (
                        SELECT MIN(pp.date) FROM prices pp
                        WHERE pp.ticker = s.ticker AND pp.date > s.date
                    )
                WHERE s.model_name = :model
                  AND s.date >= :cutoff
                  AND p_curr.adj_close IS NOT NULL
                  AND p_next.adj_close IS NOT NULL
                ORDER BY s.date
            """), {'model': self.name, 'cutoff': cutoff})
            rows = result.fetchall()
            session.close()

            if len(rows) < 20:
                logger.debug(f"[{self.name}] IC: insufficient history ({len(rows)} rows) — using default 0.05")
                return 0.05

            df = pd.DataFrame(rows, columns=['date', 'ticker', 'raw_score', 'fwd_return'])
            df = df.dropna()

            if len(df) < 10:
                return 0.05

            ic, pvalue = pearsonr(df['raw_score'], df['fwd_return'])
            ic = float(np.clip(ic, -1.0, 1.0))
            logger.debug(f"[{self.name}] Rolling IC({lookback_days}d): {ic:.4f} (p={pvalue:.3f})")
            # Return raw IC — negative IC is meaningful (model is actively wrong).
            # Callers that feed this into BL omega should apply max(0.01, ic) themselves.
            return ic

        except Exception as e:
            logger.warning(f"[{self.name}] IC computation failed ({e}) — using default 0.05")
            return 0.05

    def is_live_approved(self) -> bool:
        """
        Returns True only if this model has sustained IC >= MIN_IC_TO_LIVE
        for at least MIN_LIVE_DAYS consecutive trading days.

        Uses compute_rolling_ic() over a short 21-day window per day, which
        is approximated here by reading raw_score vs forward returns directly
        from the DB — same query as compute_rolling_ic but grouped by date.

        Models that fail this gate get omega=999 in BL (effectively ignored).
        Prevents untested models from influencing real portfolio weights.
        """
        try:
            from engine.db.db import get_session
            import datetime

            cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()

            session = get_session()
            # Pull daily IC values: for each date, compute Pearson(raw_score, fwd_return)
            # via a per-date grouping of the same signal/price join used in compute_rolling_ic.
            result = session.execute(text("""
                SELECT s.date,
                       s.raw_score,
                       p_next.adj_close / NULLIF(p_curr.adj_close, 0) - 1 AS fwd_return
                FROM signals s
                JOIN prices p_curr ON s.date    = p_curr.date AND s.ticker = p_curr.ticker
                JOIN prices p_next ON p_next.ticker = s.ticker
                    AND p_next.date = (
                        SELECT MIN(pp.date) FROM prices pp
                        WHERE pp.ticker = s.ticker AND pp.date > s.date
                    )
                WHERE s.model_name = :model
                  AND s.date >= :cutoff
                  AND p_curr.adj_close IS NOT NULL
                  AND p_next.adj_close IS NOT NULL
                ORDER BY s.date
            """), {'model': self.name, 'cutoff': cutoff})
            rows = result.fetchall()
            session.close()

            if not rows:
                logger.debug(f"[{self.name}] Not live-approved: no IC history")
                return False

            # Compute daily IC (Pearson per date) using pandas groupby
            from scipy.stats import pearsonr
            df = pd.DataFrame(rows, columns=['date', 'raw_score', 'fwd_return']).dropna()
            if df.empty:
                return False

            def _safe_pearsonr(g):
                if len(g) < 5:
                    return np.nan
                try:
                    ic, _ = pearsonr(g['raw_score'], g['fwd_return'])
                    return float(ic)
                except Exception:
                    return np.nan

            daily_ic = (
                df.groupby('date')
                  .apply(_safe_pearsonr)
                  .dropna()
                  .sort_index(ascending=False)
            )

            if len(daily_ic) < MIN_LIVE_DAYS:
                logger.debug(f"[{self.name}] Not live-approved: only {len(daily_ic)} days of IC history")
                return False

            recent_ics = daily_ic.iloc[:MIN_LIVE_DAYS].tolist()
            approved = all(ic >= MIN_IC_TO_LIVE for ic in recent_ics)

            if not approved:
                failing = [ic for ic in recent_ics if ic < MIN_IC_TO_LIVE]
                logger.debug(
                    f"[{self.name}] Not live-approved: "
                    f"{len(failing)}/{MIN_LIVE_DAYS} days below IC={MIN_IC_TO_LIVE}"
                )
            return approved

        except Exception as e:
            logger.warning(f"[{self.name}] is_live_approved check failed ({e}) — defaulting to False")
            return False
