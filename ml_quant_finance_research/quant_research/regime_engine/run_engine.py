# quant-research/regime_engine/run_engine.py
"""
Macro Regime Engine — Main Runner

Usage:
  cd quant-research/regime_engine
  python run_engine.py              # normal run
  python run_engine.py --refresh    # force FRED data refresh
  python run_engine.py --backfill   # rebuild full history from scratch

Output:
  data/regime_history.csv  — append-only daily log
  data/regime_state.json   — latest snapshot for dashboard
"""

import sys
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
from regime_db    import save_regime_history, write_regime_state, load_regime_history


def run(force_refresh: bool = False, backfill: bool = False) -> dict:
    """
    Full pipeline:
      1. Fetch macro data (FRED + yfinance VIX)
      2. Classify all days
      3. Save to history CSV
      4. Write latest state JSON
      5. Return state dict
    """
    log.info("═══════════════════════════════════════")
    log.info("  MACRO REGIME ENGINE — START")
    log.info("═══════════════════════════════════════")

    # Step 1: Fetch
    macro_df = get_macro_data(force_refresh=force_refresh or backfill)
    log.info(f"Macro data: {len(macro_df)} rows × {len(macro_df.columns)} series")

    # Step 2: Classify
    regime_df = classify_all(macro_df)

    # Step 3: Save history
    if backfill:
        import os
        from config import REGIME_DB_PATH
        if os.path.exists(REGIME_DB_PATH):
            os.remove(REGIME_DB_PATH)
            log.info("Backfill mode: cleared existing regime history.")
    save_regime_history(regime_df)

    # Step 4: Write state
    state = write_regime_state(regime_df)

    # Step 5: Print human-readable summary
    _print_summary(state, regime_df)

    log.info("═══════════════════════════════════════")
    log.info("  MACRO REGIME ENGINE — COMPLETE")
    log.info("═══════════════════════════════════════")

    return state


def _print_summary(state: dict, regime_df: pd.DataFrame) -> None:
    """Prints a clean summary table to stdout."""
    print("\n" + "─" * 55)
    print(f"  MACRO REGIME SNAPSHOT — {state['as_of_date']}")
    print("─" * 55)
    print(f"  Risk Appetite  : {state['regime_risk']}")
    print(f"  Rate Environment: {state['regime_rates']}")
    print(f"  Growth Cycle   : {state['regime_growth']}")
    print(f"  Composite      : {state['regime_composite']}")
    print(f"  Streak         : {state['current_streak_days']} consecutive days")
    if state["regime_changed_today"]:
        print(f"  ⚠  REGIME CHANGED today (from {state['prev_regime_composite']})")
    print()

    m = state["macro_snapshot"]
    print(f"  VIX            : {m['vix']}")
    print(f"  10Y-2Y Spread  : {m['yield_spread']}")
    print(f"  HY Spread      : {m['hy_spread']}")
    print(f"  Fed Funds      : {m['fed_funds']}")
    print()

    ew = state["ew_flags"]
    ew_count = state["ew_active_count"]
    warn = "🔴 TRANSITION WARNING ACTIVE" if state["transition_warning"] else "✅ No transition warning"
    print(f"  Early Warnings : {warn} ({ew_count}/4 triggers)")
    if ew["vix_rising"]:       print("    ⚡ VIX rising from calm to stress zone")
    if ew["curve_flattening"]: print("    ⚡ Yield curve flattening rapidly")
    if ew["hy_widening"]:      print("    ⚡ HY credit spreads widening sharply")
    if ew["rate_reprice"]:     print("    ⚡ Fed funds rate repricing significantly")
    print()

    print("  Historical Regime Distribution (last 504d):")
    for regime, pct in sorted(state["regime_distribution"].items(), key=lambda x: -x[1]):
        bar = "█" * int(pct / 5)
        print(f"    {regime:<35} {bar} {pct:.1f}%")

    print()

    # Signal guidance table based on current regime
    growth = state["regime_growth"]
    risk   = state["regime_risk"]
    _print_signal_guidance(growth, risk)

    print("─" * 55 + "\n")


def _print_signal_guidance(growth: str, risk: str) -> None:
    """
    Prints which research techniques are expected to be reliable
    in the current regime, based on the spec's guidance table.
    """
    GUIDANCE = {
        # (growth, risk): {technique: reliability}
        ("Expansion",   "Risk-On"):  {"Laggard": "HIGH", "PEAD": "HIGH",  "Short Squeeze": "HIGH",  "Corr Break": "HIGH"},
        ("Expansion",   "Neutral"):  {"Laggard": "HIGH", "PEAD": "HIGH",  "Short Squeeze": "MEDIUM","Corr Break": "HIGH"},
        ("Slowdown",    "Neutral"):  {"Laggard": "MOD",  "PEAD": "MOD",   "Short Squeeze": "MEDIUM","Corr Break": "AVOID"},
        ("Slowdown",    "Risk-Off"): {"Laggard": "LOW",  "PEAD": "LOW",   "Short Squeeze": "AVOID", "Corr Break": "AVOID"},
        ("Contraction", "Risk-Off"): {"Laggard": "AVOID","PEAD": "LOW",   "Short Squeeze": "AVOID", "Corr Break": "AVOID"},
        ("Recovery",    "Risk-On"):  {"Laggard": "HIGH", "PEAD": "MOD",   "Short Squeeze": "HIGH",  "Corr Break": "HIGH"},
        ("Recovery",    "Neutral"):  {"Laggard": "HIGH", "PEAD": "MOD",   "Short Squeeze": "MOD",   "Corr Break": "MOD"},
    }

    guidance = GUIDANCE.get((growth, risk), {
        "Laggard": "UNKNOWN", "PEAD": "UNKNOWN",
        "Short Squeeze": "UNKNOWN", "Corr Break": "UNKNOWN"
    })

    color_map = {"HIGH": "✅", "MOD": "🟡", "MEDIUM": "🟡", "AVOID": "🔴", "LOW": "🔴", "UNKNOWN": "❓"}

    print(f"  Signal Guidance for {growth} + {risk}:")
    for tech, rel in guidance.items():
        icon = color_map.get(rel, "❓")
        print(f"    {icon} {tech:<20} {rel}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Macro Regime Detection Engine")
    parser.add_argument("--refresh",  action="store_true", help="Force FRED data refresh")
    parser.add_argument("--backfill", action="store_true", help="Rebuild full history from scratch")
    args = parser.parse_args()

    state = run(force_refresh=args.refresh, backfill=args.backfill)
    sys.exit(0)
