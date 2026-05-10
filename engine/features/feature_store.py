# engine/features/feature_store.py
"""
Feature store — computes and persists all alpha signals to the feature_store table.
Promotes existing research code from general_research/src/ without modifying it.

Features computed:
  Momentum:    mom_1m, mom_3m, mom_6m, mom_12m  (cross-sectional percentile rank)
  Volatility:  vol_21d, vol_63d, vol_of_vol     (annualised)
  Technical:   rsi_14                           (0–100)

Portfolio-level features (stored with ticker='_PORTFOLIO'):
  Regime:      stress_score, regime, vol_component, corr_component
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
    # Reconstruct price index (relative, starts at 1)
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
    skip = 21  # skip recent 1 month to avoid reversal
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

        # Return from (lookback + skip) ago to skip days ago
        raw = prices.shift(skip) / prices.shift(lookback + skip) - 1
        latest = raw.iloc[-1].dropna()
        features[name] = latest.rank(pct=True)  # cross-sectional rank [0,1]

    if not features:
        return pd.DataFrame()

    result = pd.DataFrame(features)
    result.index.name = 'ticker'
    return result


def compute_volatility_features(log_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Realised vol (21D, 63D annualised) and vol-of-vol.
    Promotes logic from general_research/src/regime.py.
    """
    features = {}

    if len(log_returns) >= 21:
        features['vol_21d'] = log_returns.tail(21).std() * np.sqrt(252)

    if len(log_returns) >= 63:
        features['vol_63d'] = log_returns.tail(63).std() * np.sqrt(252)

    if len(log_returns) >= 126:
        vol_short = log_returns.rolling(21).std() * np.sqrt(252)
        vol_long  = log_returns.rolling(63).std() * np.sqrt(252)
        # vol_of_vol: positive = vol expanding (risk-off), negative = compressing (risk-on)
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
    Values: 0–100. Oversold < 30, Overbought > 70.
    """
    rsi_values = {}

    for ticker in prices.columns:
        series = prices[ticker].dropna()
        if len(series) < 20:
            continue

        delta = series.diff()
        gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        rsi_values[ticker] = float(rsi.iloc[-1])

    if not rsi_values:
        return pd.DataFrame()

    result = pd.DataFrame({'rsi_14': rsi_values})
    result.index.name = 'ticker'
    return result


def compute_regime_features(log_returns: pd.DataFrame) -> dict:
    """
    Computes portfolio-level regime features using general_research/src/regime.py.
    Returns dict of scalar features to be stored with ticker='_PORTFOLIO'.
    """
    try:
        import sys
        import os
        # Add project root to path so we can import from general_research
        root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        if root not in sys.path:
            sys.path.insert(0, root)

        from ml_quant_finance_research.general_research.src.regime import (
            compute_composite_regime,
        )

        # Use equal-weighted portfolio return as the benchmark series
        portfolio_returns = log_returns.mean(axis=1)
        regime_df = compute_composite_regime(portfolio_returns, log_returns)
        latest = regime_df.iloc[-1]

        return {
            'stress_score':   float(latest.get('stress_score', 0.5)),
            'vol_component':  float(latest.get('vol_component', 0.5)),
            'corr_component': float(latest.get('corr_component', 0.5)),
            # regime label is a string — encode as numeric for feature_store
            'regime_low':     1.0 if latest.get('regime') == 'low_stress'  else 0.0,
            'regime_medium':  1.0 if latest.get('regime') == 'medium'      else 0.0,
            'regime_high':    1.0 if latest.get('regime') == 'high_stress' else 0.0,
        }

    except ImportError as e:
        logger.warning(f"regime.py not importable ({e}) — skipping regime features")
        return {}
    except Exception as e:
        logger.warning(f"Regime feature computation failed: {e}")
        return {}


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

    Args:
        tickers: list of ticker strings (must already have price data in DB)
        date:    'YYYY-MM-DD', defaults to today

    Returns:
        Combined feature DataFrame (all tickers × all features).
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

    # Compute per-ticker features
    frames = []

    mom_features  = compute_momentum_features(prices)
    if not mom_features.empty:
        frames.append(mom_features)
        logger.info(f"Momentum features: {mom_features.shape[1]} cols, {len(mom_features)} tickers")

    vol_features  = compute_volatility_features(log_returns)
    if not vol_features.empty:
        frames.append(vol_features)
        logger.info(f"Volatility features: {vol_features.shape[1]} cols")

    tech_features = compute_technical_features(prices)
    if not tech_features.empty:
        frames.append(tech_features)
        logger.info(f"Technical features: {tech_features.shape[1]} cols")

    # Merge all feature frames on ticker index
    if not frames:
        logger.error("Feature pipeline: all feature computations returned empty")
        return pd.DataFrame()

    all_features = frames[0]
    for frame in frames[1:]:
        all_features = all_features.join(frame, how='outer')

    # Persist per-ticker features
    persist_features(date, all_features)

    # Compute and persist portfolio-level regime features
    regime_features = compute_regime_features(log_returns)
    if regime_features:
        persist_portfolio_features(date, regime_features)
        logger.info(f"Regime: {regime_features}")

    logger.info(
        f"Feature pipeline complete: {date}, "
        f"{len(all_features)} tickers, {all_features.shape[1]} features"
    )
    return all_features
