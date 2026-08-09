# engine/alpha/sector_momentum.py
"""
Alpha Model — Sector-Relative Momentum (J5).
Signal: 12M momentum rank WITHIN sector, not across the whole universe.

Distinct from MomentumAlpha (universe-wide rank). Both run simultaneously —
BL treats them as independent views. In a sector-rotation regime (e.g. tech
selling off broadly while value/energy leads), this model can flag the
strongest semiconductor even while universe-wide momentum flags it as
mediocre. Correlation with MomentumAlpha will be moderate (~0.4-0.6) —
they agree when one sector dominates the whole tape, diverge during
rotations, which is exactly when the divergence is informative.

See before-go-live/J5-sector-relative-momentum.md for design rationale.
"""
import pandas as pd
from sqlalchemy import text
from engine.alpha.base import AlphaModel
import logging

logger = logging.getLogger(__name__)

RETURN_SCALE = 0.03   # slightly lower than universe momentum (0.04) — this is
                       # a rotation/timing signal, not a pure trend signal


class SectorMomentumAlpha(AlphaModel):
    name = 'sector_momentum'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
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
                  AND feature_name = 'sector_mom_12m'
                  AND ticker IN ({placeholders})
            """), params)
            rows = result.fetchall()
        finally:
            session.close()

        if not rows:
            logger.warning(f"[sector_momentum] No sector_mom_12m features for {date}")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['ticker', 'raw_score'])
        ic = self.compute_rolling_ic()

        df['expected_return'] = (df['raw_score'] - 0.5) * 2 * RETURN_SCALE
        df['confidence']      = max(0.01, ic)

        logger.info(f"[sector_momentum] {len(df)} signals, IC={ic:.4f}, date={date}")
        return df[['ticker', 'expected_return', 'confidence', 'raw_score']]
