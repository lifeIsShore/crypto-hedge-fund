# engine/alpha/mean_reversion.py
"""
Alpha Model 2 — Short-term mean reversion via RSI(14).
RSI < 30 → oversold → positive expected return (bounce)
RSI > 70 → overbought → negative expected return (pullback)
Return scale: ±2.5% annualised excess (weaker signal than momentum).
"""

import pandas as pd
from sqlalchemy import text
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)

RETURN_SCALE = 0.025   # 2.5% — weaker signal, shorter horizon


class MeanReversionAlpha(AlphaModel):
    name = 'mean_reversion'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Loads rsi_14 from feature_store.
        RSI normalised to [-1, +1]: oversold=+1 (buy signal), overbought=-1 (sell).
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
                  AND feature_name = 'rsi_14'
                  AND ticker IN ({placeholders})
            """), params)
            rows = result.fetchall()
        finally:
            session.close()

        if not rows:
            logger.warning(f"[mean_reversion] No rsi_14 features for {date}")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['ticker', 'raw_score'])
        ic = self.compute_rolling_ic()

        # RSI 0–100 → normalise to [-1, +1]
        # RSI=30 (oversold) → (50-30)/50 = +0.40 → positive expected return
        # RSI=70 (overbought) → (50-70)/50 = -0.40 → negative expected return
        df['rsi_norm']       = (50 - df['raw_score']) / 50
        df['expected_return'] = df['rsi_norm'] * RETURN_SCALE
        # IC can be negative (model actively wrong); clamp to 0.01 floor for BL omega.
        df['confidence']      = max(0.01, ic)

        logger.info(f"[mean_reversion] {len(df)} signals, IC={ic:.4f}, date={date}")
        return df[['ticker', 'expected_return', 'confidence', 'raw_score']]
