# engine/alpha/momentum.py
"""
Alpha Model 1 — Cross-sectional momentum.
Signal: 12M momentum rank (skipping last 21 days to avoid reversal).
Expected return: top-ranked stocks expected to continue outperforming.
Return scale: ±4% annualised excess for rank extremes.
"""

import pandas as pd
from sqlalchemy import text
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)

RETURN_SCALE = 0.04   # 4% annualised excess return at rank=1.0


class MomentumAlpha(AlphaModel):
    name = 'momentum'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Loads mom_12m rank from feature_store, converts to expected returns.
        rank=1.0 (top) → +RETURN_SCALE expected excess
        rank=0.0 (bottom) → -RETURN_SCALE expected excess
        """
        from engine.db.db import get_session

        session = get_session()
        try:
            placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
            params = {f't{i}': t for i, t in enumerate(tickers)}
            params['date'] = date
            result = session.execute(text(f"""
                SELECT ticker, feature_value AS raw_score
                FROM feature_store
                WHERE date = :date
                  AND feature_name = 'mom_12m'
                  AND ticker IN ({placeholders})
            """), params)
            rows = result.fetchall()
        finally:
            session.close()

        if not rows:
            logger.warning(f"[momentum] No mom_12m features for {date} — run feature pipeline first")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['ticker', 'raw_score'])
        ic = self.compute_rolling_ic()

        # rank [0, 1] → expected return: rank=0.5 = neutral (0 excess), extremes = ±scale
        df['expected_return'] = (df['raw_score'] - 0.5) * 2 * RETURN_SCALE
        df['confidence']      = ic

        logger.info(f"[momentum] {len(df)} signals, IC={ic:.4f}, date={date}")
        return df[['ticker', 'expected_return', 'confidence', 'raw_score']]
