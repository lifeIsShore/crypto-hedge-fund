"""
better-alpha/gate0_baseline.py
================================
Gate 0 — Baseline Establishment (see 00-OVERVIEW.md).

Run this AFTER you have run, in order:
    1) python ml_quant_finance_research/ml_research/stock_ml_lab/run_ml_pipeline.py
       (from inside that directory)  -> writes shared/state/ml_state.json
    2) python backtests/alpha_eval.py
       (from repo root)              -> writes backtests/alpha_ic_results.csv

This script is read-only w.r.t. those two files. It:
  - Reads shared/state/ml_state.json -> per-ticker best-of-3-model AUC
    (model_signals[ticker]['auc']). This is deliberately the SAME number
    engine/alpha/ml_alpha.py gates on (MIN_AUC = 0.53), not a per-model
    (XGB-only / RF-only) breakdown, because per-model AUC isn't persisted
    per ticker anywhere in the current pipeline. If you want a true
    per-model breakdown later, that's a 3-line addition to
    run_ml_pipeline.py (store model_results per ticker, not just the max).
  - Reads backtests/alpha_ic_results.csv for model_name == 'ml_alpha' AND
    model_name == 'momentum' at horizon 21.
  - Writes better-alpha/baseline_v1_auc.txt

Never overwrite baseline_v1_auc.txt after this run. If you need to
re-baseline (e.g. after a data refresh), rename the old file first
(baseline_v1_auc_SUPERSEDED_<date>.txt) rather than deleting it.
"""
import json
import os
import sys
from datetime import date

import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))  # hedge-fund/

ML_STATE_PATH = os.path.join(ROOT, "shared", "state", "ml_state.json")
IC_RESULTS_PATH = os.path.join(ROOT, "backtests", "alpha_ic_results.csv")
OUT_PATH = os.path.join(HERE, "baseline_v1_auc.txt")


def main():
    if os.path.exists(OUT_PATH):
        print(f"REFUSING TO OVERWRITE: {OUT_PATH} already exists.")
        print("Rename it first (e.g. baseline_v1_auc_SUPERSEDED_<date>.txt) if you "
              "really need to re-baseline.")
        sys.exit(1)

    if not os.path.exists(ML_STATE_PATH):
        print(f"MISSING: {ML_STATE_PATH}")
        print("Run run_ml_pipeline.py first (see docstring at top of this file).")
        sys.exit(1)

    if not os.path.exists(IC_RESULTS_PATH):
        print(f"MISSING: {IC_RESULTS_PATH}")
        print("Run backtests/alpha_eval.py first (see docstring at top of this file).")
        sys.exit(1)

    with open(ML_STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)

    signals = state.get("model_signals", {})
    aucs = [v["auc"] for v in signals.values() if "auc" in v]
    if not aucs:
        print("No per-ticker AUC values found in ml_state.json model_signals. Aborting.")
        sys.exit(1)

    mean_auc = float(np.mean(aucs))
    std_auc = float(np.std(aucs))
    n_tickers = len(aucs)
    below_gate = sum(1 for a in aucs if a < 0.53)

    ic_df = pd.read_csv(IC_RESULTS_PATH)
    row21_ml = ic_df[(ic_df["model"] == "ml_alpha") & (ic_df["horizon"] == 21)]
    row21_mom = ic_df[(ic_df["model"] == "momentum") & (ic_df["horizon"] == 21)]

    def pull(row, col):
        if row.empty or pd.isna(row.iloc[0][col]):
            return None
        return float(row.iloc[0][col])

    mean_ic_ml = pull(row21_ml, "mean_ic")
    icir_ml = pull(row21_ml, "icir")
    n_obs_ml = pull(row21_ml, "n_obs")
    mean_ic_mom = pull(row21_mom, "mean_ic")

    lines = [
        f"# Baseline v1 — recorded {date.today().isoformat()} before any feature additions",
        f"# Source: {ML_STATE_PATH}",
        f"#         {IC_RESULTS_PATH}",
        f"n_tickers={n_tickers}",
        f"mean_auc_best_of_3={mean_auc:.4f}",
        f"std_auc_best_of_3={std_auc:.4f}",
        f"n_tickers_below_min_auc_0.53={below_gate}",
    ]
    if mean_ic_mom is not None:
        lines.append(f"mean_ic_momentum_21d={mean_ic_mom:.4f}")
    else:
        lines.append("mean_ic_momentum_21d=NO_DATA")
    if mean_ic_ml is not None:
        lines.append(f"mean_ic_ml_alpha_21d={mean_ic_ml:.4f}")
        lines.append(f"icir_ml_alpha_21d={icir_ml:.4f}" if icir_ml is not None else "icir_ml_alpha_21d=NO_DATA")
        lines.append(f"n_obs_ml_alpha_21d={int(n_obs_ml) if n_obs_ml is not None else 'NO_DATA'}")
    else:
        lines.append("mean_ic_ml_alpha_21d=NO_DATA")
        lines.append("icir_ml_alpha_21d=NO_DATA")

    out = "\n".join(lines) + "\n"

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(out)

    print("=" * 60)
    print("GATE 0 — baseline recorded")
    print("=" * 60)
    print(out)
    print(f"Written to: {OUT_PATH}")

    if n_obs_ml is not None and n_obs_ml < 20:
        print()
        print("WARNING: n_obs for ml_alpha at 21d is very low "
              f"({int(n_obs_ml)}). IC/ICIR at this sample size is noisy — "
              "treat this baseline as provisional and re-check after the "
              "pipeline has been running long enough to accumulate more "
              "signal-dated observations. Do not size Gate 2 pass/fail "
              "decisions on a baseline this thin without acknowledging that.")


if __name__ == "__main__":
    main()
