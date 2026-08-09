> **STATUS (2026-08-10): IMPLEMENTED — see PROJECT-STATE.md session-5 changelog.**
> `compute_sector_relative_features()` added to `feature_store.py` and wired
> into `run_feature_pipeline()`. New `engine/alpha/sector_momentum.py` —
> `SectorMomentumAlpha` — wired into both `step_alpha()`'s model_map and
> `step_portfolio_construction()`'s `models_dict` in `scheduler.py`, so it
> gates through `is_live_approved()` and feeds Black-Litterman exactly like
> the other alpha models. Step 4 (dashboard divergence display) NOT built —
> the feature and signal exist and are usable, but no ticker-detail page UI
> shows the universe-vs-sector divergence yet.
> This doc is kept as design rationale.

# J5 — Sector-Relative Momentum Ranking
# Edit `engine/features/feature_store.py` + add a new alpha model variant
# Estimated time: 3 hours (your own BRAINSTORM doc estimated 2 — I've added the
# alpha-model wiring on top of just the feature, which is the part that actually
# changes behavior).

---

## The problem this closes

`engine/alpha/momentum.py` (checked directly) ranks `mom_12m` across the
**entire universe** — a semiconductor competes against a European utility
and a consumer staple in the same percentile rank. In a broad market
downturn, a semiconductor that's merely *the best-performing semiconductor*
still looks terrible on a universe-wide rank, even though it's exactly the
name you'd want to rotate into once semis turn. This is Gap 4 in
`BRAINSTORM-new-features-and-gaps.md` — speced conceptually, not built
(confirmed: `feature_store.py` has no sector-grouping logic anywhere).

---

## Design

Two deliverables, not one — the feature alone doesn't change any trading
behavior until something consumes it:

1. **The feature** (`sector_mom_1m/3m/6m/12m`) — intra-sector percentile rank,
   computed in `feature_store.py`. This part is directly from your own
   `NEW-feature-expansion-8-to-24.md` doc (§3, `compute_sector_relative_features`)
   — that function is copied below unchanged since it was already correctly
   speced there, just never wired to anything.
2. **A second momentum alpha model variant** that actually *uses* the sector-
   relative feature to generate views — without this, the feature just sits
   in `feature_store` unused, the same trap J3 found with `kelly_half`.

---

## Implementation

### Step 1 — Add the feature function (from `NEW-feature-expansion-8-to-24.md`, unchanged)

```python
# engine/features/feature_store.py

def compute_sector_relative_features(prices: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
    """
    Computes intra-sector ranks for the 4 core momentum windows.
    A rank of 1.0 means this ticker is the top momentum stock in its sector.
    """
    skip = 21
    windows = {
        'sector_mom_1m':  21,
        'sector_mom_3m':  63,
        'sector_mom_6m':  126,
        'sector_mom_12m': 252,
    }
    features = {}

    for feat_name, lookback in windows.items():
        required_len = lookback + skip
        if len(prices) < required_len:
            continue

        raw = prices.shift(skip) / prices.shift(lookback + skip) - 1
        latest = raw.iloc[-1].dropna()

        sector_ranks = {}
        for ticker in latest.index:
            sector = sector_map.get(ticker, 'other')
            sector_ranks.setdefault(sector, {})[ticker] = latest[ticker]

        result_ranks = {}
        for sector, ticker_vals in sector_ranks.items():
            if len(ticker_vals) < 2:
                for t in ticker_vals:
                    result_ranks[t] = 0.5   # only 1 ticker in sector — neutral rank
                continue
            vals_series = pd.Series(ticker_vals)
            result_ranks.update(vals_series.rank(pct=True).to_dict())

        features[feat_name] = pd.Series(result_ranks)

    if not features:
        return pd.DataFrame()
    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result
```

Wire into `run_feature_pipeline()`:

```python
from portfolio.src.config import TICKER_SECTORS

sector_rel = compute_sector_relative_features(prices, TICKER_SECTORS)
if not sector_rel.empty:
    frames.append(sector_rel)
    logger.info(f"Sector-relative features: {sector_rel.shape[1]} cols")
```

### Step 2 — New alpha model: `SectorMomentumAlpha`

This is the part that actually makes the feature matter. Same structure as
`momentum.py`, reads `sector_mom_12m` instead of `mom_12m`:

```python
# engine/alpha/sector_momentum.py
"""
Alpha Model — Sector-Relative Momentum.
Signal: 12M momentum rank WITHIN sector, not across the whole universe.

Distinct from MomentumAlpha (universe-wide rank). Both run simultaneously —
BL treats them as independent views. In a sector-rotation regime (e.g. tech
selling off broadly while value/energy leads), this model can flag the
strongest semiconductor even while universe-wide momentum flags it as
mediocre. Correlation with MomentumAlpha will be moderate (~0.4-0.6) —
they agree when one sector dominates the whole tape, diverge during
rotations, which is exactly when the divergence is informative.
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
```

### Step 3 — Wire into `step_alpha_signals()` in `engine/scheduler.py`

```python
from engine.alpha.sector_momentum import SectorMomentumAlpha

models = [
    MomentumAlpha(),
    SectorMomentumAlpha(),   # NEW
    MeanReversionAlpha(),
    VolTimingAlpha(),
    PEADAlpha(),
    MLAlpha(),
    LSTMAlpha(),
]
```

Both `MomentumAlpha` and `SectorMomentumAlpha` will independently gate
through the same `is_live_approved()` IC check already in `base.py` — no
special handling needed, this fits your existing multi-model architecture
exactly as designed.

### Step 4 — Surface the divergence, not just the two scores

The single most useful dashboard addition here isn't showing both numbers
separately — it's flagging **when they disagree**, since that's the signal
this model exists to catch. Add to the ticker detail page:

```
NVDA:  Universe momentum rank: 0.38 (below median)
       Sector momentum rank:   0.91 (top decile within Semiconductors)
       ⚠ Divergence: strong within-sector leader, weak vs. whole market
         → sector rotation candidate, watch for sector-wide turn
```

This is directly actionable per your `laggard_screen_strategy.md` and
`etf_component_divergence_strategy.md` logic (Scenario 1 — Temporary
Rotation) — this feature is effectively a cheap, automated first-pass
detector for exactly the divergence those two docs describe manually
screening for. Worth cross-referencing when you build J6/J7 below.

---

## Tuning notes

- `RETURN_SCALE = 0.03` vs momentum's `0.04` is a starting guess reflecting
  that sector-relative signals are inherently noisier in small sectors
  (some of your `TICKER_SECTORS` groups may only have 3-5 tickers) — watch
  the IC once this has 21+ days of history and adjust.
- Sectors with fewer than 2 tickers get a neutral 0.5 rank (see the code
  comment) — check `TICKER_SECTORS` in `portfolio/src/config.py` for any
  singleton sectors before deploying; if you have several, consider merging
  small related sectors (e.g. "Aerospace" + "Industrials") so the ranking
  has enough peers to be meaningful.
