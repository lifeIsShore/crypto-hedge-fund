# quant-research/regime_engine/run_engine.py
"""
Macro Regime Engine — Main Runner
Supports multi-regional data (US, EU).
"""

import sys
import os
import logging
import argparse
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from data_fetcher import get_macro_data
from classifier   import classify_all
from regime_db    import save_regime_history, write_regime_state


def run(region: str = "US", force_refresh: bool = False, backfill: bool = False) -> dict:
    """Full regional pipeline."""
    log.info("-" * 40)
    log.info(f"  MACRO REGIME ENGINE - {region} - START")
    log.info("-" * 40)

    # Step 1: Fetch
    macro_df = get_macro_data(region=region, force_refresh=force_refresh or backfill)
    log.info(f"Macro data ({region}): {len(macro_df)} rows")

    # Step 2: Classify
    regime_df = classify_all(macro_df, region=region)

    # Step 3: Save history
    save_regime_history(regime_df, region=region)

    # Step 4: Write state snapshot
    state = write_regime_state(regime_df, region=region)

    # Step 5: Print summary
    _print_summary(state, region)

    log.info("-" * 40)
    log.info(f"  MACRO REGIME ENGINE - {region} - COMPLETE")
    log.info("-" * 40)

    return state


def _print_summary(state: dict, region: str) -> None:
    print("\n" + "=" * 55)
    print(f"  MACRO REGIME SNAPSHOT - {region} - {state['as_of_date']}")
    print("=" * 55)
    print(f"  Risk Appetite   : {state['regime_risk']}")
    print(f"  Rate Environment: {state['regime_rates']}")
    print(f"  Growth Cycle    : {state['regime_growth']}")
    print(f"  Composite       : {state['regime_composite']}")
    
    m = state["macro_snapshot"]
    v_label = "VSTOXX" if region == "EU" else "VIX"
    r_label = "ECB Rate" if region == "EU" else "Fed Funds"
    print(f"  {v_label:<15}: {m['vix']}")
    print(f"  Spread (10Y-2Y): {m['yield_spread']}")
    print(f"  HY Spread      : {m['hy_spread']}")
    print(f"  {r_label:<15}: {m['fed_funds']}")
    
    warn = "TRANSITION WARNING ACTIVE" if state["transition_warning"] else "No transition warning"
    print(f"  Status          : {warn} ({state['ew_active_count']}/4 triggers)")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Macro Regime Detection Engine")
    parser.add_argument("--region",   type=str, default="US", help="Region (US, EU, ALL)")
    parser.add_argument("--refresh",  action="store_true", help="Force data refresh")
    parser.add_argument("--backfill", action="store_true", help="Rebuild history from scratch")
    args = parser.parse_args()

    # Support "ALL" to run both
    target_region = args.region.upper()
    regions = ["US", "EU"] if target_region == "ALL" else [target_region]
    
    for r in regions:
        try:
            run(region=r, force_refresh=args.refresh, backfill=args.backfill)
        except Exception as e:
            log.error(f"Failed to run engine for {r}: {e}")
            
    sys.exit(0)
