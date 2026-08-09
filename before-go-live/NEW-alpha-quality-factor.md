> **STATUS (2026-08-09, verified by Claude): NOT IMPLEMENTED.** Same situation as the earnings-revision doc — archived without being built. No `quality_factor.py` exists in `engine/alpha/`. This model depends on `fundamental_ingestion.py` / the `fundamental_data` table from `NEW-alpha-earnings-revision.md`, which is also not built — build that one first. Verify against the live repo again before starting.

# New Alpha Model: Quality Factor
# `engine/alpha/quality_factor.py`
# Estimated time: 1 day. Requires fundamental_ingestion.py (see earnings-revision doc)

---

## What this model does

The Quality factor is one of the five canonical Fama-French factors. High-quality
companies — defined as high Return on Equity, low Debt/Equity, and stable earnings —
systematically outperform on a risk-adjusted basis over long horizons.

More importantly for your setup: Quality performs best in Risk-Off regimes.
When your regime engine signals Risk-Off, this model should get HIGHER weight
in the BL objective function. It is an explicitly regime-conditional signal.

Academic source: Novy-Marx (2013) "The Other Side of Value: The Gross
Profitability Premium." Asness, Frazzini, Pedersen (2019) "Quality Minus Junk."

---

## Signal construction

Three sub-signals combined into one quality score:

```
quality_score = (0.4 × roe_rank) + (0.4 × low_leverage_rank) + (0.2 × earnings_stability_rank)
```

Where:
- `roe_rank` = cross-sectional rank of Return on Equity (within sector)
- `low_leverage_rank` = cross-sectional rank of (1 / debt_to_equity), so low debt = high rank
- `earnings_stability_rank` = cross-sectional rank of consistency of earnings_growth (lower variance = better)

---

## Implementation

Create `engine/alpha/quality_factor.py`:

```python
"""
Alpha Model 7 — Quality Factor (ROE + Low Leverage + Earnings Stability).

Reads from fundamental_data table (populated by fundamental_ingestion.py).
High quality = high ROE + low debt + stable earnings.

This is a SLOW signal. Quality companies re-rate over quarters, not weeks.
Set BL tau lower for this model (less aggressive weight), OR use it as
a conviction filter: only buy signals that also have quality >= 0.6 rank.

Return scale: ±2.5% annualised excess (conservative — quality is a
risk-adjusted return story, not raw return).

Regime integration:
  - Risk-Off: scale by 1.4 (quality shines when markets fear)
  - Risk-On:  scale by 0.7 (quality underperforms in momentum rallies)
"""
import pandas as pd
import numpy as np
import logging
from sqlalchemy import text
from engine.alpha.base import AlphaModel
from engine.db.db import get_session

logger = logging.getLogger(__name__)

RETURN_SCALE = 0.025

QUALITY_WEIGHTS = {
    'roe':             0.40,
    'low_leverage':    0.40,
    'earnings_growth': 0.20,
}


def _load_regime() -> str:
    """Load current risk regime from DB. Returns 'risk_on', 'risk_off', or 'neutral'."""
    try:
        import json, os
        from shared.state_paths import REGIME_STATE_PATH
        with open(REGIME_STATE_PATH) as f:
            state = json.load(f)
        risk = state.get('regime_risk', 'Neutral').lower().replace('-', '_')
        return risk
    except Exception:
        return 'neutral'


class QualityFactorAlpha(AlphaModel):
    name = 'quality_factor'

    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        session = get_session()
        try:
            rows = session.execute(text("""
                SELECT ticker, field, value
                FROM fundamental_data
                WHERE date = (
                    SELECT MAX(date) FROM fundamental_data
                    WHERE date <= :date
                )
                AND ticker IN ({})
                AND field IN ('roe', 'debt_to_equity', 'earnings_growth', 'forward_pe')
            """.format(','.join([f"'{t}'" for t in tickers]))), {'date': date}).fetchall()
        finally:
            session.close()

        if not rows:
            logger.warning("[quality] No fundamental data — run fundamental ingestion first")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=['ticker', 'field', 'value'])
        pivot = df.pivot(index='ticker', columns='field', values='value')

        # Load regime for scaling
        regime = _load_regime()
        regime_scalar = {'risk_off': 1.4, 'neutral': 1.0, 'risk_on': 0.7}.get(regime, 1.0)
        logger.info(f"[quality] Regime={regime}, scale={regime_scalar}")

        composite = pd.DataFrame(index=pivot.index)

        # ROE rank (within sector where possible, else universe)
        if 'roe' in pivot.columns:
            roe = pivot['roe'].dropna()
            composite['roe_rank'] = roe.rank(pct=True)

        # Leverage rank — inverted (low debt = high rank)
        if 'debt_to_equity' in pivot.columns:
            dte = pivot['debt_to_equity'].dropna()
            # Cap extreme leverage (banks can have D/E > 10 structurally)
            dte_capped = dte.clip(upper=dte.quantile(0.95))
            composite['low_leverage_rank'] = (1 / dte_capped.replace(0, np.nan)).rank(pct=True)

        # Earnings growth rank (positive growth = quality)
        if 'earnings_growth' in pivot.columns:
            eg = pivot['earnings_growth'].dropna()
            composite['earnings_growth_rank'] = eg.rank(pct=True)

        if composite.empty or len(composite.columns) == 0:
            return pd.DataFrame()

        # Composite score — weighted average of available sub-scores
        weight_map = {
            'roe_rank':             QUALITY_WEIGHTS['roe'],
            'low_leverage_rank':    QUALITY_WEIGHTS['low_leverage'],
            'earnings_growth_rank': QUALITY_WEIGHTS['earnings_growth'],
        }
        available_cols = [c for c in weight_map if c in composite.columns]
        if not available_cols:
            return pd.DataFrame()

        total_weight = sum(weight_map[c] for c in available_cols)
        composite['quality_score'] = sum(
            composite[c] * weight_map[c] / total_weight
            for c in available_cols
        )
        composite = composite.dropna(subset=['quality_score'])

        if composite.empty:
            return pd.DataFrame()

        ic = self.compute_rolling_ic()
        result_rows = []

        for ticker in composite.index:
            score = float(composite.loc[ticker, 'quality_score'])
            # Centre at 0 (score=0.5 → no expected return)
            expected_return = (score - 0.5) * 2 * RETURN_SCALE * regime_scalar

            result_rows.append({
                'ticker':          ticker,
                'expected_return': round(expected_return, 4),
                'confidence':      max(0.01, ic),
                'raw_score':       round(score, 4),
            })

        result = pd.DataFrame(result_rows)
        if not result.empty:
            logger.info(
                f"[quality] {len(result)} signals, regime={regime}, "
                f"scale={regime_scalar}, date={date}"
            )
        return result
```

---

## Wire into scheduler

In `step_alpha_signals()`:
```python
from engine.alpha.quality_factor import QualityFactorAlpha

models = [
    ...
    QualityFactorAlpha(),    # NEW — needs fundamental_ingestion to run first
]
```

---

## Regime integration (the key power of this model)

Quality is regime-conditional. The `regime_scalar` in the code above
does this automatically: in Risk-Off, quality signals are amplified 40%.
In Risk-On momentum rallies, they're reduced 30%.

This means your BL views will automatically tilt toward high-quality,
low-debt companies when the regime engine signals stress. This is exactly
what a defensive portfolio rotation should look like.

**Combined with your existing regime BL view:**
- Current setup: regime injects one portfolio-level view on the benchmark
- Quality adds: per-ticker rotation toward quality within each regime

These are additive and complementary. Do not choose between them.

---

## Expected characteristics

- Coverage: ~80–100 tickers (needs ROE + D/E data from yfinance)
- IC expectation: 0.04–0.07 (slow signal, lower IC on short windows)
- Horizon: 6–12 months
- Best use: Risk-Off regime rotation + portfolio stress testing
- Sectors to avoid applying: Financials (high D/E is structural — banks)
  Consider excluding `TICKER_SECTORS[t] == 'Financials'` from leverage scoring

---

## Optional enhancement: Quality + Value combo

In a future iteration, combine Quality with a Value signal:

```
quality_value_score = quality_score * 0.5 + (1 - forward_pe_rank) * 0.5
```

High quality + cheap price = the "Quality Minus Junk at a Reasonable Price"
(QARP) signal that consistently outperforms in academic studies.
Only implement after the basic Quality model has 21+ days of IC history.
