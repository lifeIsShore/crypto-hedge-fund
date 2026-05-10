# engine/alpha/base.py
"""
Abstract base class for all alpha models.
Every model produces a standard signal DataFrame:
  ticker | expected_return | confidence | raw_score

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
        """Write signals to the signals table (upsert on conflict)."""
        if signals_df is None or signals_df.empty:
            return

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
        """
        try:
            from engine.db.db import get_session
            from scipy.stats import pearsonr

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
                  AND s.date >= CURRENT_DATE - INTERVAL ':days days'
                  AND p_curr.adj_close IS NOT NULL
                  AND p_next.adj_close IS NOT NULL
                ORDER BY s.date
            """.replace(':days', str(lookback_days + 5)), {'model': self.name}))
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
            return max(0.01, ic)  # floor at 1% — never return 0 (breaks BL omega)

        except Exception as e:
            logger.warning(f"[{self.name}] IC computation failed ({e}) — using default 0.05")
            return 0.05

    def is_live_approved(self) -> bool:
        """
        Returns True only if this model has maintained IC >= MIN_IC_TO_LIVE
        for at least MIN_LIVE_DAYS consecutive trading days.

        Models that fail this gate get omega=999 in BL (effectively ignored).
        Prevents untested models from influencing real portfolio weights.
        """
        try:
            from engine.db.db import get_session

            session = get_session()
            result = session.execute(text("""
                SELECT date, AVG(confidence) AS avg_ic
                FROM signals
                WHERE model_name = :model
                  AND date >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY date
                ORDER BY date DESC
                LIMIT :days
            """), {'model': self.name, 'days': MIN_LIVE_DAYS + 5})
            rows = result.fetchall()
            session.close()

            if len(rows) < MIN_LIVE_DAYS:
                logger.debug(f"[{self.name}] Not live-approved: only {len(rows)} days of history")
                return False

            recent_ics = [float(r[1]) for r in rows[:MIN_LIVE_DAYS]]
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
