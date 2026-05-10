# engine/risk/pre_trade.py
import pandas as pd
import numpy as np
import logging
from engine.db.db import get_session
from sqlalchemy import text

logger = logging.getLogger(__name__)

MAX_POSITION    = 0.10
MAX_SECTOR      = 0.30
MAX_LEVERAGE    = 1.0
MIN_ADV_RATIO   = 0.01    # order must be < 1% of 30-day avg daily volume


def check_position_limits(suggested_weights: pd.Series) -> list:
    violations = []
    for ticker, w in suggested_weights.items():
        if w > MAX_POSITION:
            violations.append(f"{ticker}: weight {w:.1%} exceeds max {MAX_POSITION:.0%}")
    return violations


def check_leverage(suggested_weights: pd.Series) -> list:
    total = suggested_weights.sum()
    if total > MAX_LEVERAGE + 0.001:
        return [f"Total weight {total:.3f} exceeds max leverage {MAX_LEVERAGE}"]
    return []


def check_sector_exposure(suggested_weights: pd.Series, sector_map: dict) -> list:
    sector_totals = {}
    for ticker, w in suggested_weights.items():
        s = sector_map.get(ticker, "other")
        sector_totals[s] = sector_totals.get(s, 0) + w
    violations = []
    for sector, total in sector_totals.items():
        if total > MAX_SECTOR:
            violations.append(f"Sector {sector}: {total:.1%} exceeds {MAX_SECTOR:.0%} limit")
    return violations


def run_pre_trade_checks(suggested_weights: pd.Series, sector_map: dict = None) -> dict:
    """
    Runs all pre-trade checks. Returns result with pass/fail and list of violations.
    Violations block order submission.
    """
    violations = []
    violations += check_position_limits(suggested_weights)
    violations += check_leverage(suggested_weights)
    if sector_map:
        violations += check_sector_exposure(suggested_weights, sector_map)

    result = {
        "passed": len(violations) == 0,
        "violations": violations,
    }

    if not result["passed"]:
        logger.warning(f"Pre-trade FAILED: {violations}")
    else:
        logger.info("Pre-trade checks: ALL PASSED")

    # Log to DB
    session = get_session()
    for v in violations:
        session.execute(text("""
            INSERT INTO risk_events (date, metric_name, metric_value)
            VALUES (CURRENT_DATE, :name, 1)
        """), {"name": f"pre_trade_violation: {v[:60]}"})
    session.commit()
    session.close()

    return result
