# quant-research/pead_engine/run_engine.py
"""
PEAD Engine — Main Runner

Usage:
  cd quant-research/pead_engine
  python run_engine.py                  # normal run (last 90 days)
  python run_engine.py --refresh        # force data refresh
  python run_engine.py --lookback 180   # scan last 180 days
  python run_engine.py --backfill       # rebuild regression models from scratch
  python run_engine.py --outcomes       # only backfill drift outcomes, no new screen

Output:
  data/pead_setups.csv    — append-only setup log
  data/pead_state.json    — latest state for dashboard
  data/regression_models.json — per-ticker surprise→reaction models
"""

import sys
import logging
import argparse
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

from config import PEAD_UNIVERSE
from data_fetcher  import fetch_all_earnings, fetch_prices
from regression_model import fit_all_regressions, load_regression_models
from screener      import screen_recent_earnings
from pead_db       import save_setups, load_setups, backfill_outcomes, write_pead_state


def run(
    force_refresh:   bool = False,
    lookback_days:   int  = 90,
    backfill_models: bool = False,
    outcomes_only:   bool = False,
) -> dict:

    log.info("═══════════════════════════════════════")
    log.info("  PEAD ENGINE — START")
    log.info("═══════════════════════════════════════")

    # ── Step 1: Fetch prices ──────────────────────────────────────────────────
    log.info("Step 1/5 — Fetching price history...")
    prices_df = fetch_prices(PEAD_UNIVERSE, force_refresh=force_refresh)
    log.info(f"  Prices: {len(prices_df)} rows × {len(prices_df.columns)} tickers")

    # ── Step 2: Backfill outcomes for existing setups ─────────────────────────
    log.info("Step 2/5 — Backfilling drift outcomes...")
    db = backfill_outcomes(prices_df)
    log.info(f"  DB has {len(db)} total setups after backfill")

    if outcomes_only:
        state = write_pead_state(db.head(0), db)  # empty setups_df = no active section
        _print_summary(state)
        log.info("Outcomes-only run complete.")
        return state

    # ── Step 3: Fetch earnings data ───────────────────────────────────────────
    log.info("Step 3/5 — Fetching earnings history...")
    earnings_df = fetch_all_earnings(PEAD_UNIVERSE, force_refresh=force_refresh)
    if earnings_df.empty:
        log.error("No earnings data available. Aborting screen.")
        return {}
    log.info(f"  Earnings: {len(earnings_df)} events across {earnings_df['ticker'].nunique()} tickers")

    # ── Step 4: Fit / load regression models ─────────────────────────────────
    log.info("Step 4/5 — Fitting surprise→reaction regression models...")
    if backfill_models:
        models = fit_all_regressions(earnings_df, prices_df)
    else:
        models = load_regression_models()
        if not models:
            log.info("  No cached models found — fitting now...")
            models = fit_all_regressions(earnings_df, prices_df)
        else:
            log.info(f"  Loaded {len(models)} cached regression models")
            # Re-fit only if models are more than 7 days old
            import os, json
            from config import REGRESSION_CACHE_PATH
            if os.path.exists(REGRESSION_CACHE_PATH):
                import time
                age_days = (time.time() - os.path.getmtime(REGRESSION_CACHE_PATH)) / 86400
                if age_days > 7:
                    log.info(f"  Models are {age_days:.1f}d old — re-fitting...")
                    models = fit_all_regressions(earnings_df, prices_df)

    # ── Step 5: Screen for PEAD setups ───────────────────────────────────────
    log.info(f"Step 5/5 — Screening earnings events (last {lookback_days}d)...")
    setups_df = screen_recent_earnings(
        earnings_df, prices_df, models, lookback_days=lookback_days
    )

    # ── Save + attach regime labels ───────────────────────────────────────────
    if not setups_df.empty:
        _attach_regime_labels(setups_df)
        save_setups(setups_df)

    # ── Reload full DB (includes newly saved setups) ──────────────────────────
    db = load_setups()

    # ── Write state ───────────────────────────────────────────────────────────
    state = write_pead_state(setups_df, db)

    _print_summary(state)

    log.info("═══════════════════════════════════════")
    log.info("  PEAD ENGINE — COMPLETE")
    log.info("═══════════════════════════════════════")

    return state


def _attach_regime_labels(setups_df):
    """
    Attempts to join regime labels from regime_engine output.
    Non-fatal — PEAD runs fine without regime context.
    """
    import os, sys
    base_dir = os.path.dirname(__file__)
    regime_state_path = os.path.join(base_dir, "..", "regime_engine", "data", "regime_state.json")
    regime_history_path = os.path.join(base_dir, "..", "regime_engine", "data", "regime_history.csv")

    if not os.path.exists(regime_history_path):
        log.info("  Regime history not found — skipping regime tagging (run regime_engine first)")
        return

    try:
        import pandas as pd
        # Read the CSV directly to avoid sys.path manipulation and module collisions
        regime = pd.read_csv(regime_history_path, index_col=0, parse_dates=True)
        regime = regime[["regime_risk", "regime_rates", "regime_growth", "regime_composite"]]

        setups_df["earnings_date_ts"] = pd.to_datetime(setups_df["earnings_date"])
        # Join on nearest date
        for i, row in setups_df.iterrows():
            ts = row["earnings_date_ts"]
            matches = regime.index[regime.index <= ts]
            if len(matches):
                r = regime.loc[matches[-1]]
                setups_df.at[i, "regime_risk"]      = r["regime_risk"]
                setups_df.at[i, "regime_growth"]     = r["regime_growth"]
                setups_df.at[i, "regime_composite"]  = r["regime_composite"]

        setups_df.drop(columns=["earnings_date_ts"], inplace=True, errors="ignore")
        log.info("  Regime labels attached to setups.")
    except Exception as e:
        log.info(f"  Regime tagging skipped: {e}")


def _print_summary(state: dict) -> None:
    """Prints human-readable PEAD summary."""
    import pandas as pd

    print("\n" + "-" * 60)
    print(f"  PEAD ENGINE SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("-" * 60)

    active = state.get("active_setups", [])
    if active:
        print(f"\n  [ACTIVE SETUPS] ({len(active)}) — Enter within next 3 days:\n")
        for s in active:
            icon = "[BULL]" if s["direction"] == "bullish" else "[BEAR]"
            ew   = "[!]" if s.get("underreaction") else "   "
            print(f"  {icon} {ew} {s['ticker']:<10} {s['quality']:<8} "
                  f"Surprise: {s['surprise_pct']:+.1f}%  "
                  f"Entry: {s['entry_date']}  "
                  f"Drift window: {s['drift_window']}d")
    else:
        print("\n  No active PEAD setups in entry window today.")

    perf = state.get("performance", {})
    if perf.get("total_setups"):
        print(f"\n  [PERFORMANCE] (all-time, {perf['total_setups']} setups):")
        print(f"     Overall 21d hit rate : {_fmt_pct(perf.get('overall_hit_rate_21d'))}")
        print(f"     Overall avg drift 21d: {_fmt_pct(perf.get('overall_avg_drift_21d'), is_return=True)}")
        print(f"     High quality 21d HR  : {_fmt_pct(perf.get('high_hit_rate_21d'))}")
        print(f"     High quality avg 21d : {_fmt_pct(perf.get('high_avg_drift_21d'), is_return=True)}")

        # Regime breakdown
        for key, val in perf.items():
            if key.startswith("hit_rate_21d_") and val is not None:
                regime_name = key.replace("hit_rate_21d_", "").title()
                print(f"     {regime_name:<20} 21d HR: {_fmt_pct(val)}")

    print("\n" + "-" * 60 + "\n")


def _fmt_pct(val, is_return=False) -> str:
    if val is None:
        return "—"
    if is_return:
        return f"{val:+.2f}%"
    return f"{val*100:.1f}%"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PEAD Engine")
    parser.add_argument("--refresh",   action="store_true", help="Force data refresh")
    parser.add_argument("--lookback",  type=int, default=90, help="Days to look back for earnings (default: 90)")
    parser.add_argument("--backfill",  action="store_true", help="Rebuild regression models from scratch")
    parser.add_argument("--outcomes",  action="store_true", help="Only update drift outcomes, skip screen")
    args = parser.parse_args()

    state = run(
        force_refresh   = args.refresh,
        lookback_days   = args.lookback,
        backfill_models = args.backfill,
        outcomes_only   = args.outcomes,
    )
    sys.exit(0)
