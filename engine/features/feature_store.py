# engine/features/feature_store.py
"""
Feature store — computes and persists all alpha signals to the feature_store table.

Features computed per ticker:
  Momentum:    mom_1m, mom_3m, mom_6m, mom_12m  (cross-sectional percentile rank)
  Volatility:  vol_21d, vol_63d, vol_of_vol     (annualised)
  Technical:   rsi_14                           (0-100)

Portfolio-level features (stored with ticker='_PORTFOLIO'):
  Statistical regime  (from general_research/src/regime.py):
      stress_score, vol_component, corr_component
      regime_low, regime_medium, regime_high       (one-hot)

  Macro regime  (from shared/state/regime_state.json, written by regime_engine):
      macro_risk_on, macro_risk_off, macro_neutral (one-hot, risk axis)
      macro_easing, macro_tightening               (one-hot, rates axis)
      macro_expansion, macro_slowdown, macro_contraction, macro_recovery (one-hot, growth axis)
      macro_ew_transition                          (0/1 early-warning flag)
      macro_ew_count                               (0-4 count of active EW signals)
      macro_vix, macro_yield_spread, macro_hy_spread, macro_fed_funds (raw macro snapshot)
      macro_streak_days                            (days in current macro regime)

Both regime signals feed into Black-Litterman via the portfolio construction step.
"""

import numpy as np
import pandas as pd
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING FROM DB
# ─────────────────────────────────────────────────────────────────────────────

def load_returns_from_db(tickers: list, lookback_days: int = 504) -> pd.DataFrame:
    """
    Loads adj_close from the prices table and computes log returns.
    Returns a DataFrame indexed by date, columns = tickers.
    """
    from engine.db.db import get_session

    session = get_session()
    try:
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        result = session.execute(text(f"""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE ticker IN ({placeholders})
            ORDER BY date ASC
        """), params)
        rows = result.fetchall()
    finally:
        session.close()

    if not rows:
        logger.warning("load_returns_from_db: no price data found in DB")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=['date', 'ticker', 'adj_close'])
    pivot = df.pivot(index='date', columns='ticker', values='adj_close')
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index().tail(lookback_days)

    # Forward-fill gaps up to 5 days (weekends, bank holidays)
    pivot = pivot.ffill(limit=5)

    log_returns = np.log(pivot / pivot.shift(1)).dropna(how='all')
    logger.debug(f"Loaded {len(log_returns)} return observations for {len(pivot.columns)} tickers")
    return log_returns


def load_prices_from_db(tickers: list, lookback_days: int = 504) -> pd.DataFrame:
    """Returns raw adj_close price DataFrame (not log returns)."""
    log_returns = load_returns_from_db(tickers, lookback_days)
    if log_returns.empty:
        return pd.DataFrame()
    prices = np.exp(log_returns.cumsum())
    return prices


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_momentum_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-sectional momentum ranks: 1M, 3M, 6M, 12M.
    Skips last 21 days to avoid short-term reversal (standard in literature).
    Returns DataFrame: index=tickers, columns=feature_names, values=rank [0,1].
    """
    skip = 21
    windows = {
        'mom_1m':  21,
        'mom_3m':  63,
        'mom_6m':  126,
        'mom_12m': 252,
    }
    features = {}

    for name, lookback in windows.items():
        required_len = lookback + skip
        if len(prices) < required_len:
            logger.debug(f"Not enough history for {name} (need {required_len}, have {len(prices)})")
            continue
        raw    = prices.shift(skip) / prices.shift(lookback + skip) - 1
        latest = raw.iloc[-1].dropna()
        features[name] = latest.rank(pct=True)

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result


def compute_sector_relative_features(prices: pd.DataFrame, sector_map: dict) -> pd.DataFrame:
    """
    J5 — Sector-relative momentum. Computes intra-sector percentile ranks for
    the 4 core momentum windows, so a ticker is ranked against its sector
    peers rather than the whole universe. A rank of 1.0 means this ticker is
    the top momentum stock in its sector.

    Distinct from compute_momentum_features() above (universe-wide rank).
    See before-go-live/J5-sector-relative-momentum.md for design rationale.

    Sectors with fewer than 2 tickers get a neutral 0.5 rank — no peers to
    rank against.
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


def compute_volatility_features(log_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Realised vol (21D, 63D annualised) and vol-of-vol.
    """
    features = {}

    if len(log_returns) >= 21:
        features['vol_21d'] = log_returns.tail(21).std() * np.sqrt(252)

    if len(log_returns) >= 63:
        features['vol_63d'] = log_returns.tail(63).std() * np.sqrt(252)

    if len(log_returns) >= 126:
        vol_short = log_returns.rolling(21).std() * np.sqrt(252)
        vol_long  = log_returns.rolling(63).std() * np.sqrt(252)
        vol_ratio = (vol_short - vol_long) / vol_long.replace(0, np.nan)
        features['vol_of_vol'] = vol_ratio.iloc[-1]

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result


def compute_technical_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    RSI(14) for each ticker using Wilder's EMA smoothing.
    Values: 0-100. Oversold < 30, Overbought > 70.
    """
    rsi_values = {}

    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 20:
            continue
        delta  = series.diff()
        gain   = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss   = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs     = gain / loss.replace(0, np.nan)
        rsi    = 100 - (100 / (1 + rs))
        rsi_values[ticker] = float(rsi.iloc[-1])

    if not rsi_values:
        return pd.DataFrame()

    result = pd.DataFrame({'rsi_14': rsi_values})
    result.index.name = 'ticker'
    return result


def compute_statistical_regime_features(log_returns: pd.DataFrame) -> dict:
    """
    Computes portfolio-level STATISTICAL regime features using
    general_research/src/regime.py (vol + correlation compression).

    Returns dict of scalar features for ticker='_PORTFOLIO'.
    Keys are prefixed with nothing (they were here first).
    """
    try:
        import sys
        import os
        root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        if root not in sys.path:
            sys.path.insert(0, root)

        from ml_quant_finance_research.general_research.src.regime import (
            compute_composite_regime,
        )

        portfolio_returns = log_returns.mean(axis=1)
        regime_df = compute_composite_regime(portfolio_returns, log_returns)
        latest = regime_df.iloc[-1]

        return {
            'stress_score':   float(latest.get('stress_score', 0.5)),
            'vol_component':  float(latest.get('vol_component', 0.5)),
            'corr_component': float(latest.get('corr_component', 0.5)),
            'regime_low':     1.0 if latest.get('regime') == 'low_stress'  else 0.0,
            'regime_medium':  1.0 if latest.get('regime') == 'medium'      else 0.0,
            'regime_high':    1.0 if latest.get('regime') == 'high_stress' else 0.0,
        }

    except ImportError as e:
        logger.warning(f"regime.py not importable ({e}) — skipping statistical regime features")
        return {}
    except Exception as e:
        logger.warning(f"Statistical regime feature computation failed: {e}")
        return {}


def compute_macro_regime_features() -> dict:
    """
    Loads macro regime features from shared/state/regime_state.json
    (written daily by regime_engine/run_engine.py).

    Returns dict of scalar features for ticker='_PORTFOLIO'.
    All keys are prefixed with 'macro_' to avoid collision with the
    statistical regime features above.

    Returns empty dict if the state file is missing or stale (> 3 days).
    """
    import json
    import os
    import time

    try:
        from shared.state_paths import REGIME_STATE_PATH
    except ImportError:
        # Fallback: resolve relative to this file
        here = os.path.dirname(os.path.abspath(__file__))
        REGIME_STATE_PATH = os.path.normpath(
            os.path.join(here, '..', '..', 'shared', 'state', 'regime_state.json')
        )

    if not os.path.exists(REGIME_STATE_PATH):
        logger.info(
            "[feature_store] regime_state.json not found — "
            "run regime_engine first, or add step_regime_refresh() to scheduler"
        )
        return {}

    # Staleness guard: 3 days = 72 hours
    age_hours = (time.time() - os.path.getmtime(REGIME_STATE_PATH)) / 3600
    if age_hours > 72:
        logger.warning(
            f"[feature_store] regime_state.json is {age_hours:.1f}h old — "
            "macro regime features may be stale"
        )

    try:
        with open(REGIME_STATE_PATH, 'r') as f:
            rs = json.load(f)
    except Exception as e:
        logger.warning(f"[feature_store] Failed to read regime_state.json: {e}")
        return {}

    risk    = rs.get('regime_risk',   'Neutral')
    rates   = rs.get('regime_rates',  'Neutral')
    growth  = rs.get('regime_growth', 'Slowdown')
    macro   = rs.get('macro_snapshot', {})

    features = {
        # ── Risk axis (one-hot) ───────────────────────────────────────────────
        'macro_risk_on':    1.0 if risk == 'Risk-On'  else 0.0,
        'macro_risk_off':   1.0 if risk == 'Risk-Off' else 0.0,
        'macro_neutral':    1.0 if risk == 'Neutral'  else 0.0,

        # ── Rates axis (one-hot) ──────────────────────────────────────────────
        'macro_easing':     1.0 if rates == 'Easing'     else 0.0,
        'macro_tightening': 1.0 if rates == 'Tightening' else 0.0,

        # ── Growth axis (one-hot) ─────────────────────────────────────────────
        'macro_expansion':   1.0 if growth == 'Expansion'   else 0.0,
        'macro_slowdown':    1.0 if growth == 'Slowdown'     else 0.0,
        'macro_contraction': 1.0 if growth == 'Contraction'  else 0.0,
        'macro_recovery':    1.0 if growth == 'Recovery'     else 0.0,

        # ── Early-warning signals ─────────────────────────────────────────────
        'macro_ew_transition': 1.0 if rs.get('transition_warning', False) else 0.0,
        'macro_ew_count':      float(rs.get('ew_active_count', 0)),

        # ── Raw macro snapshot ────────────────────────────────────────────────
        'macro_vix':          float(macro.get('vix', 20.0)),
        'macro_yield_spread': float(macro.get('yield_spread', 0.0)),
        'macro_hy_spread':    float(macro.get('hy_spread', 4.5)),
        'macro_fed_funds':    float(macro.get('fed_funds', 4.0)),

        # ── Regime momentum ───────────────────────────────────────────────────
        'macro_streak_days':  float(rs.get('current_streak_days', 1)),
    }

    logger.info(
        f"[feature_store] Macro regime loaded: {risk} / {rates} / {growth} "
        f"| EW={rs.get('transition_warning', False)} "
        f"| streak={rs.get('current_streak_days', 1)}d"
    )
    return features


# ─────────────────────────────────────────────────────────────────────────────
# DB PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def persist_features(date: str, feature_df: pd.DataFrame):
    """
    Upserts computed per-ticker features into feature_store.
    feature_df: index=tickers, columns=feature_names, values=floats.
    """
    if feature_df is None or feature_df.empty:
        logger.warning("persist_features: empty DataFrame — nothing to write")
        return

    from engine.db.db import get_session

    session = get_session()
    count = 0
    try:
        for ticker in feature_df.index:
            for feature_name in feature_df.columns:
                val = feature_df.loc[ticker, feature_name]
                if pd.isna(val):
                    continue
                session.execute(text("""
                    INSERT INTO feature_store
                        (date, ticker, feature_name, feature_value, computed_at)
                    VALUES
                        (:date, :ticker, :feature_name, :feature_value, datetime('now'))
                    ON CONFLICT (date, ticker, feature_name) DO UPDATE SET
                        feature_value = :feature_value,
                        computed_at   = datetime('now')
                """), {
                    'date':          date,
                    'ticker':        ticker,
                    'feature_name':  feature_name,
                    'feature_value': float(val),
                })
                count += 1

        session.commit()
        logger.info(f"Feature store: persisted {count} values for {date}")
    except Exception as e:
        session.rollback()
        logger.error(f"persist_features failed: {e}")
        raise
    finally:
        session.close()


def persist_portfolio_features(date: str, features: dict):
    """Persist portfolio-level features (ticker = '_PORTFOLIO')."""
    if not features:
        return
    df = pd.DataFrame([features], index=['_PORTFOLIO'])
    df.index.name = 'ticker'
    persist_features(date, df)


# ─────────────────────────────────────────────────────────────────────────────
# DAILY RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_feature_pipeline(tickers: list, date: str = None) -> pd.DataFrame:
    """
    Entry point — called by scheduler after market close.
    Computes all features and writes them to the feature_store table.

    Per-ticker features:  momentum, volatility, technical
    Portfolio features:   statistical regime (vol+corr) + macro regime (VIX/HY/curve)

    Args:
        tickers: list of ticker strings (must already have price data in DB)
        date:    'YYYY-MM-DD', defaults to today

    Returns:
        Combined per-ticker feature DataFrame.
    """
    import datetime
    if date is None:
        date = str(datetime.date.today())

    logger.info(f"Feature pipeline starting: {date}, {len(tickers)} tickers")

    # Load data
    log_returns = load_returns_from_db(tickers, lookback_days=504 + 21)
    if log_returns.empty:
        logger.error("Feature pipeline: no data in DB. Run ingestion first.")
        return pd.DataFrame()

    prices = load_prices_from_db(tickers, lookback_days=504 + 21)

    # ── Per-ticker features ───────────────────────────────────────────────────
    frames = []

    mom_features = compute_momentum_features(prices)
    if not mom_features.empty:
        frames.append(mom_features)
        logger.info(f"Momentum features: {mom_features.shape[1]} cols, {len(mom_features)} tickers")

    # J5 — sector-relative momentum (intra-sector rank, not universe-wide)
    try:
        from portfolio.src.config import TICKER_SECTORS
        sector_rel_features = compute_sector_relative_features(prices, TICKER_SECTORS)
        if not sector_rel_features.empty:
            frames.append(sector_rel_features)
            logger.info(f"Sector-relative momentum features: {sector_rel_features.shape[1]} cols")
    except Exception as e:
        logger.warning(f"Sector-relative momentum computation failed (non-fatal): {e}")

    vol_features = compute_volatility_features(log_returns)
    if not vol_features.empty:
        frames.append(vol_features)
        logger.info(f"Volatility features: {vol_features.shape[1]} cols")

    tech_features = compute_technical_features(prices)
    if not tech_features.empty:
        frames.append(tech_features)
        logger.info(f"Technical features: {tech_features.shape[1]} cols")

    if not frames:
        logger.error("Feature pipeline: all per-ticker computations returned empty")
        return pd.DataFrame()

    all_features = frames[0]
    for frame in frames[1:]:
        all_features = all_features.join(frame, how='outer')

    persist_features(date, all_features)

    # ── Portfolio-level features: BOTH regime signals ─────────────────────────
    portfolio_features = {}

    # 1. Statistical regime (vol + correlation compression)
    stat_features = compute_statistical_regime_features(log_returns)
    if stat_features:
        portfolio_features.update(stat_features)
        logger.info(f"Statistical regime: {stat_features}")

    # 2. Macro regime (3-axis: VIX / HY / yield curve / Fed funds)
    macro_features = compute_macro_regime_features()
    if macro_features:
        portfolio_features.update(macro_features)
        logger.info(
            f"Macro regime: risk_on={macro_features.get('macro_risk_on')}, "
            f"growth_expansion={macro_features.get('macro_expansion')}, "
            f"ew={macro_features.get('macro_ew_transition')}"
        )

    if portfolio_features:
        persist_portfolio_features(date, portfolio_features)

    logger.info(
        f"Feature pipeline complete: {date}, "
        f"{len(all_features)} tickers, {all_features.shape[1]} per-ticker features, "
        f"{len(portfolio_features)} portfolio features"
    )
    return all_features
