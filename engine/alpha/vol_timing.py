# engine/alpha/vol_timing.py
"""
Alpha Model 3 — Volatility regime timing.
Compares 21D vs 63D realised vol:
  vol compressing (21D < 63D) → risk-on → higher expected returns
  vol expanding   (21D > 63D) → risk-off → lower expected returns
Return scale: ±2% annualised excess.
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)

RETURN_SCALE = 0.02   # 2% — vol timing is a portfolio-level tilt, not stock-picking


class VolTimingAlpha(AlphaModel):
    name = 'vol_timing'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Loads vol_21d and vol_63d from feature_store.
        vol_ratio = vol_21d / vol_63d
          < 1: vol compressing → positive signal (lower rank = better)
          > 1: vol expanding   → negative signal
        """
        from engine.db.db import get_session

        session = get_session()
        try:
            placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
            params = {f't{i}': t for i, t in enumerate(tickers)}
            params['date'] = date
            result = session.execute(text(f"""
                SELECT ticker, feature_name, feature_value
                FROM feature_store
                WHERE date = :date
                  AND feature_name IN ('vol_21d', 'vol_63d')
                  AND ticker IN ({placeholders})
            """), params)
            rows = result.fetchall()
        finally:
            session.close()


        if not rows:
            logger.warning(f"[vol_timing] No vol features for {date}")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['ticker', 'feature_name', 'feature_value'])
        pivot = df.pivot(index='ticker', columns='feature_name', values='feature_value')

        # Need both vol columns
        if 'vol_21d' not in pivot.columns or 'vol_63d' not in pivot.columns:
            logger.warning(f"[vol_timing] Missing vol_21d or vol_63d features")
            return pd.DataFrame()

        pivot = pivot.dropna(subset=['vol_21d', 'vol_63d'])

        ic = self.compute_rolling_ic()

        pivot['vol_ratio'] = pivot['vol_21d'] / pivot['vol_63d'].replace(0, np.nan)
        pivot['raw_score'] = pivot['vol_ratio']

        # Cross-sectional rank: low vol_ratio (compressing) → high rank → positive signal
        pivot['rank'] = (1 - pivot['vol_ratio'].rank(pct=True))
        pivot['expected_return'] = (pivot['rank'] - 0.5) * 2 * RETURN_SCALE
        # IC can be negative (model actively wrong); clamp to 0.01 floor for BL omega.
        pivot['confidence']      = max(0.01, ic)

        pivot = pivot.reset_index()

        logger.info(f"[vol_timing] {len(pivot)} signals, IC={ic:.4f}, date={date}")
        return pivot[['ticker', 'expected_return', 'confidence', 'raw_score']]
