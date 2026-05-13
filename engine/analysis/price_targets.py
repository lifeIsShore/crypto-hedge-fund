# engine/analysis/price_targets.py
"""
Stream 3 — Price Target & Resistance Levels (EUR)

Computes probabilistic price targets for every ticker using:
  - ML up_proba_21d from shared/state/ml_state.json
  - Realised annualised vol from the feature_store table
  - OHLCV history from the prices table (MA, Bollinger, 52w high/low)

All output prices are in EUR (prices table already stores EUR-converted values).

Public API:
    run_price_targets(tickers, date)   ← called from scheduler step 12
    get_latest_targets()               ← called from Flask /api/price_targets
"""

import numpy as np
import pandas as pd
import json
import os
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CORE COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_price_targets(
    ticker: str,
    current_price_eur: float,
    up_proba: float,
    vol_ann: float,
    prices_series: pd.Series,   # adj_close series, index=date, already in EUR
) -> dict:
    """
    Computes probabilistic price targets for a single ticker.

    The expected price is the median of a lognormal distribution at t=21d,
    shifted by the ML edge signal. It will be wrong ~50% of the time —
    the value is in having an explicit, pre-committed exit plan.

    Args:
        ticker:            ticker string
        current_price_eur: latest EUR-adjusted close price
        up_proba:          ML predicted probability of 21d upside (0–1)
        vol_ann:           annualised realised volatility (e.g. 0.28 = 28%)
        prices_series:     historical adj_close in EUR, needs ≥200 rows for MA200

    Returns:
        dict with all target fields, ready to insert into price_targets table.
    """
    if current_price_eur <= 0 or vol_ann <= 0:
        logger.warning(f"[price_targets] {ticker}: invalid inputs (price={current_price_eur}, vol={vol_ann})")
        return {}

    horizon = 21
    t = horizon / 252

    # Edge: centre up_proba around 0 → [-1, +1]
    edge  = (up_proba - 0.5) * 2
    drift = edge * vol_ann * t
    sigma = vol_ann * np.sqrt(t)

    # Lognormal targets
    expected   = current_price_eur * np.exp(drift)
    target_up  = current_price_eur * np.exp(drift + sigma)      # 84th percentile
    stop_loss  = current_price_eur * np.exp(drift - sigma)      # 16th percentile
    stop_tight = current_price_eur * np.exp(drift - 0.5 * sigma)

    # Risk/reward: upside potential vs downside risk
    upside   = target_up - current_price_eur
    downside = current_price_eur - stop_loss
    rr_ratio = upside / downside if downside > 0.001 else 0.0

    # Technical levels (only computed when enough history)
    ps = prices_series.dropna()
    n  = len(ps)

    ma50  = float(ps.tail(50).mean())  if n >= 50  else None
    ma200 = float(ps.tail(200).mean()) if n >= 200 else None

    if n >= 20:
        bb_mean  = ps.tail(20).mean()
        bb_std   = ps.tail(20).std()
        bb_upper = float(bb_mean + 2 * bb_std)
        bb_lower = float(bb_mean - 2 * bb_std)
    else:
        bb_upper = bb_lower = None

    high_52w = float(ps.tail(252).max()) if n >= 252 else float(ps.max())
    low_52w  = float(ps.tail(252).min()) if n >= 252 else float(ps.min())

    # ── Half-Kelly position sizing ───────────────────────────────────────────
    # Kelly fraction = (p * b - q) / b
    #   p = up_proba, q = 1 - p
    #   b = reward-to-risk ratio (upside % / downside %)
    # Half-Kelly is standard practice for live trading:
    #   - Reduces variance vs full Kelly
    #   - Accounts for parameter estimation error
    # Capped at 25% of portfolio (hard maximum per position)
    p = up_proba
    q = 1.0 - p
    upside_pct  = (target_up - current_price_eur) / current_price_eur if current_price_eur > 0 else 0
    downside_pct = (current_price_eur - stop_loss) / current_price_eur if current_price_eur > 0 else 1
    b = upside_pct / downside_pct if downside_pct > 0.001 else 1.0
    full_kelly = (p * b - q) / b if b > 0 else 0.0
    half_kelly = max(0.0, full_kelly / 2.0)  # never negative (don't short via Kelly)
    kelly_half  = min(half_kelly * 100, 25.0)  # as percentage, capped at 25%

    return {
        'ticker':               ticker,
        'current_price_eur':    round(current_price_eur, 4),
        'expected_21d_eur':     round(expected, 4),
        'target_1sigma_eur':    round(target_up, 4),
        'stop_1sigma_eur':      round(stop_loss, 4),
        'stop_tight_eur':       round(stop_tight, 4),
        'resistance_ma50':      round(ma50,  4) if ma50  is not None else None,
        'resistance_ma200':     round(ma200, 4) if ma200 is not None else None,
        'resistance_bb_upper':  round(bb_upper, 4) if bb_upper is not None else None,
        'support_bb_lower':     round(bb_lower, 4) if bb_lower is not None else None,
        'high_52w':             round(high_52w, 4),
        'low_52w':              round(low_52w,  4),
        'risk_reward_ratio':    round(rr_ratio, 3),
        'up_proba':             round(up_proba, 4),
        'vol_ann':              round(vol_ann,  4),
        'kelly_half':           round(kelly_half, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_ml_signals() -> dict:
    """
    Returns {ticker: {'up_proba_21d': float, 'auc': float}} from ml_state.json.
    Returns empty dict if file missing or model_signals empty.
    """
    try:
        from shared.state_paths import ML_STATE_PATH
        if not os.path.exists(ML_STATE_PATH):
            logger.warning("[price_targets] ml_state.json not found — using up_proba=0.5 for all tickers")
            return {}
        with open(ML_STATE_PATH, 'r') as f:
            state = json.load(f)
        return state.get('model_signals', {})
    except Exception as e:
        logger.warning(f"[price_targets] Failed to load ml_state.json: {e}")
        return {}


def _load_vol_from_db(tickers: list) -> dict:
    """
    Loads vol_21d (annualised) from feature_store for the most recent date.
    Falls back to vol_63d if vol_21d missing, then to a 0.25 default.
    Returns {ticker: vol_ann}.
    """
    try:
        from engine.db.db import get_session
        session = get_session()
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        result = session.execute(text(f"""
            SELECT fs.ticker, fs.feature_name, fs.feature_value
            FROM feature_store fs
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date
                FROM feature_store
                WHERE feature_name IN ('vol_21d', 'vol_63d')
                  AND ticker IN ({placeholders})
                GROUP BY ticker
            ) latest ON fs.ticker = latest.ticker AND fs.date = latest.max_date
            WHERE fs.feature_name IN ('vol_21d', 'vol_63d')
              AND fs.ticker IN ({placeholders})
        """), params)
        rows = result.fetchall()
        session.close()
    except Exception as e:
        logger.warning(f"[price_targets] Could not load vol from feature_store: {e}")
        return {}

    vol_map = {}
    for ticker, feature_name, val in rows:
        # Prefer vol_21d; only store vol_63d if vol_21d not yet seen
        if feature_name == 'vol_21d':
            vol_map[ticker] = float(val)
        elif feature_name == 'vol_63d' and ticker not in vol_map:
            vol_map[ticker] = float(val)

    return vol_map


def _load_prices_from_db(tickers: list, lookback: int = 260) -> dict:
    """
    Returns {ticker: pd.Series(adj_close, index=date)} for the last `lookback` days.
    """
    try:
        from engine.db.db import get_session
        session = get_session()
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}
        result = session.execute(text(f"""
            SELECT date, ticker, adj_close
            FROM prices
            WHERE ticker IN ({placeholders})
              AND adj_close IS NOT NULL
            ORDER BY date ASC
        """), params)
        rows = result.fetchall()
        session.close()
    except Exception as e:
        logger.warning(f"[price_targets] Could not load prices: {e}")
        return {}

    if not rows:
        return {}

    df = pd.DataFrame(rows, columns=['date', 'ticker', 'adj_close'])
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')

    out = {}
    for ticker in tickers:
        sub = df[df['ticker'] == ticker].set_index('date')['adj_close']
        if len(sub) > 0:
            out[ticker] = sub.tail(lookback)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def _persist_targets(date: str, targets: list):
    """Upserts a list of price target dicts into the price_targets table."""
    if not targets:
        logger.warning("[price_targets] No targets to persist")
        return

    from engine.db.db import get_session
    session = get_session()
    count = 0
    try:
        for t in targets:
            session.execute(text("""
                INSERT INTO price_targets (
                    date, ticker, current_price_eur, expected_21d_eur,
                    target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
                    resistance_ma50, resistance_ma200,
                    resistance_bb_upper, support_bb_lower,
                    high_52w, low_52w, risk_reward_ratio,
                    up_proba, vol_ann, kelly_half, computed_at
                ) VALUES (
                    :date, :ticker, :current_price_eur, :expected_21d_eur,
                    :target_1sigma_eur, :stop_1sigma_eur, :stop_tight_eur,
                    :resistance_ma50, :resistance_ma200,
                    :resistance_bb_upper, :support_bb_lower,
                    :high_52w, :low_52w, :risk_reward_ratio,
                    :up_proba, :vol_ann, :kelly_half, datetime('now')
                )
                ON CONFLICT (date, ticker) DO UPDATE SET
                    current_price_eur   = :current_price_eur,
                    expected_21d_eur    = :expected_21d_eur,
                    target_1sigma_eur   = :target_1sigma_eur,
                    stop_1sigma_eur     = :stop_1sigma_eur,
                    stop_tight_eur      = :stop_tight_eur,
                    resistance_ma50     = :resistance_ma50,
                    resistance_ma200    = :resistance_ma200,
                    resistance_bb_upper = :resistance_bb_upper,
                    support_bb_lower    = :support_bb_lower,
                    high_52w            = :high_52w,
                    low_52w             = :low_52w,
                    risk_reward_ratio   = :risk_reward_ratio,
                    up_proba            = :up_proba,
                    vol_ann             = :vol_ann,
                    kelly_half          = :kelly_half,
                    computed_at         = datetime('now')
            """), {'date': date, **t})
            count += 1

        session.commit()
        logger.info(f"[price_targets] Persisted {count} price targets for {date}")
    except Exception as e:
        session.rollback()
        logger.error(f"[price_targets] Persist failed: {e}")
        raise
    finally:
        session.close()


def _write_price_targets_json(targets: list):
    """
    Writes price targets to shared/state/price_targets.json as a fallback
    for dashboards that read state files directly.
    """
    try:
        from shared.state_paths import STATE_DIR, ensure_state_dir
        ensure_state_dir()
        path = os.path.join(STATE_DIR, 'price_targets.json')
        with open(path, 'w') as f:
            json.dump(targets, f, indent=2, default=str)
        logger.info(f"[price_targets] JSON written to {path}")
    except Exception as e:
        logger.warning(f"[price_targets] Could not write JSON: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINTS
# ─────────────────────────────────────────────────────────────────────────────

def run_price_targets(tickers: list, date: str) -> list:
    """
    Full price target pipeline. Called from scheduler step 12.

    1. Load ML up_proba per ticker from ml_state.json
    2. Load vol_ann per ticker from feature_store
    3. Load price history from DB
    4. Compute probabilistic targets + technical levels
    5. Persist to price_targets table + shared/state/price_targets.json

    Returns list of target dicts (one per ticker with data).
    """
    logger.info(f"[price_targets] Starting for {date}, {len(tickers)} tickers")

    ml_signals  = _load_ml_signals()
    vol_map     = _load_vol_from_db(tickers)
    prices_map  = _load_prices_from_db(tickers)

    targets = []
    skipped = 0

    for ticker in tickers:
        price_series = prices_map.get(ticker)
        if price_series is None or len(price_series) < 5:
            logger.debug(f"[price_targets] {ticker}: no price history — skipped")
            skipped += 1
            continue

        current_price = float(price_series.iloc[-1])
        if current_price <= 0:
            skipped += 1
            continue

        # ML signal — default to neutral (0.5) if model hasn't run yet
        signal    = ml_signals.get(ticker, {})
        up_proba  = float(signal.get('up_proba_21d', 0.5))

        # Vol — default to 25% if feature store hasn't run yet
        vol_ann   = vol_map.get(ticker, 0.25)
        if vol_ann <= 0:
            vol_ann = 0.25

        result = compute_price_targets(ticker, current_price, up_proba, vol_ann, price_series)
        if result:
            targets.append(result)

    logger.info(
        f"[price_targets] Computed {len(targets)} targets, "
        f"{skipped} skipped (no data), date={date}"
    )

    if targets:
        _persist_targets(date, targets)
        _write_price_targets_json(targets)

    return targets


def get_latest_targets() -> list:
    """
    Returns the most recent price targets for all tickers.
    Called from Flask /api/price_targets.
    """
    try:
        from engine.db.db import get_session
        session = get_session()
        result = session.execute(text("""
            SELECT ticker, current_price_eur, expected_21d_eur,
                   target_1sigma_eur, stop_1sigma_eur, stop_tight_eur,
                   resistance_ma50, resistance_ma200,
                   resistance_bb_upper, support_bb_lower,
                   high_52w, low_52w, risk_reward_ratio,
                   up_proba, vol_ann, kelly_half, computed_at
            FROM price_targets
            WHERE date = (SELECT MAX(date) FROM price_targets)
            ORDER BY ticker
        """))
        rows = result.fetchall()
        session.close()
        cols = [
            'ticker', 'current_price_eur', 'expected_21d_eur',
            'target_1sigma_eur', 'stop_1sigma_eur', 'stop_tight_eur',
            'resistance_ma50', 'resistance_ma200',
            'resistance_bb_upper', 'support_bb_lower',
            'high_52w', 'low_52w', 'risk_reward_ratio',
            'up_proba', 'vol_ann', 'kelly_half', 'computed_at',
        ]
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.error(f"[price_targets] get_latest_targets failed: {e}")
        return []
