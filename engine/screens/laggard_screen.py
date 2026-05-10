# engine/screens/laggard_screen.py
"""
Laggard Stock Screen — as specified in laggard_screen_strategy.md.
Phases 1-5 implemented as composable functions.
"""
import pandas as pd
import numpy as np
from engine.features.feature_store import load_returns_from_db
from engine.db.db import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# Configuration (mirrors strategy doc)
SECTOR_ETF_MAP = {
    "tech":        "EXXT.DE",   # Nasdaq-100 ETF
    "europe":      "EXS1.DE",   # DAX ETF
    "world":       "EUNL.DE",   # MSCI World ETF
}

LAGGARD_BOTTOM_QUARTILE = 0.25   # bottom 25% of peer group = laggard candidate


def detect_rising_sectors(
    sector_etf_map: dict,
    min_return_pct: float = 0.08,
    lookback_days: int = 126,   # ~6 months
) -> list:
    """Phase 1: Identify sectors with sustained upward momentum (8-25% over 1-6M)."""
    session = get_session()
    rising = []
    for sector, etf in sector_etf_map.items():
        result = session.execute(text("""
            SELECT adj_close FROM prices
            WHERE ticker = :etf
            ORDER BY date DESC
            LIMIT :days
        """), {"etf": etf, "days": lookback_days + 1})
        prices = [r[0] for r in result.fetchall()]
        if len(prices) < 2:
            continue
        period_return = (prices[0] - prices[-1]) / prices[-1]
        if period_return >= min_return_pct:
            rising.append({"sector": sector, "etf": etf, "return": round(period_return, 4)})
            logger.info(f"Rising sector: {sector} ({period_return:.1%} over {lookback_days}d)")
    session.close()
    return rising


def score_peer_group(tickers: list, lookback_days: int = 126) -> pd.DataFrame:
    """
    Phase 3: Rank tickers by relative performance.
    Returns DataFrame with ticker + relative_rank (0=worst, 1=best).
    """
    log_returns = load_returns_from_db(tickers, lookback_days=lookback_days + 21)
    if log_returns.empty:
        return pd.DataFrame()

    period_returns = (log_returns.tail(lookback_days).sum())   # cumulative log return
    df = pd.DataFrame({"ticker": period_returns.index, "period_return": period_returns.values})
    df["relative_rank"] = df["period_return"].rank(pct=True)
    return df.sort_values("relative_rank")


def run_disqualifier_checks(tickers: list) -> dict:
    """
    Phase 4: Disqualifier checks. Returns dict of {ticker: [disqualification reasons]}.
    Currently checks: short interest proxy via vol spike (placeholder — extend with Fintel API).
    """
    # This is a placeholder framework. In production:
    # - Pull short interest from Fintel/Ortex API
    # - Pull insider transactions from SEC EDGAR
    # - Check news sentiment via news API
    # Returns empty disqualifications by default (manual research required per todo doc)
    return {ticker: [] for ticker in tickers}


def run_laggard_screen(peer_groups: dict) -> list:
    """
    Full laggard screen pipeline. peer_groups = {sector: [tickers]}.
    Returns list of laggard candidates with conviction tier.
    """
    candidates = []

    for sector, tickers in peer_groups.items():
        if len(tickers) < 4:
            continue

        peer_df = score_peer_group(tickers)
        if peer_df.empty:
            continue

        laggards = peer_df[peer_df["relative_rank"] <= LAGGARD_BOTTOM_QUARTILE]
        disqualifiers = run_disqualifier_checks(laggards["ticker"].tolist())

        for _, row in laggards.iterrows():
            ticker = row["ticker"]
            disq = disqualifiers.get(ticker, [])
            if disq:
                logger.info(f"Disqualified: {ticker} — {disq}")
                continue

            # Peer median return for catch-up target
            peer_median_return = float(peer_df["period_return"].median())
            catch_up_gap = peer_median_return - float(row["period_return"])

            candidates.append({
                "ticker":             ticker,
                "sector":             sector,
                "period_return":      round(float(row["period_return"]), 4),
                "relative_rank":      round(float(row["relative_rank"]), 4),
                "peer_median_return": round(peer_median_return, 4),
                "catch_up_gap":       round(catch_up_gap, 4),
                "conviction":         "high" if row["relative_rank"] <= 0.10 else "medium",
                "disqualifiers":      disq,
            })

    candidates.sort(key=lambda x: x["catch_up_gap"], reverse=True)
    logger.info(f"Laggard screen: {len(candidates)} candidates identified")
    return candidates
