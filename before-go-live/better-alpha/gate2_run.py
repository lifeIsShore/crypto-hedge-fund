"""
before-go-live/better-alpha/gate2_run.py
=========================================
Gate 2 automated AUC + IC test for one Phase 1A feature family.
See 00-OVERVIEW.md §Gate 2 for the full gating criteria.

Usage (from repo root):
    python before-go-live/better-alpha/gate2_run.py --family db_regime
    python before-go-live/better-alpha/gate2_run.py --family pead
    python before-go-live/better-alpha/gate2_run.py --family earnings

Steps per run:
  1. Reads AUC baseline from baseline_v1_auc.txt.
  2. Runs run_ml_pipeline.py with --enable-{family} (holdout filter
     is applied automatically since holdout_config.txt exists).
  3. Reads new per-ticker AUC from ml_state.json.
  4. Reads current ml_alpha IC from alpha_ic_results.csv.
  5. Evaluates Gate 2 criteria from 00-OVERVIEW.md.
  6. Appends a row to gate2_results.csv.
  7. Prints PASS / FAIL with full criteria breakdown.

Gate 2 PASS (ALL hard criteria must be met):
  ✓ delta_auc > +0.003 (primary gate — always active)
  ✓ delta_auc_std ≤ +0.010 (AUC consistency must not worsen)
  ✓ No ticker drops below AUC 0.50 that was previously above 0.53
  ✓ delta_ic > +0.003 [deferred if n_obs < 10 — becomes Gate 3 IC check]
  ✓ delta_icir ≥ -0.05 [deferred if n_obs < 10]

AUC baseline note:
  baseline_v1_auc.txt was recorded on full history (no holdout filter).
  The Gate 2 test run uses the holdout filter (~11% fewer rows removed).
  This makes the AUC comparison slightly conservative (harder to pass),
  which is the correct direction for avoiding false positives.
  The actual AUC delta needed to clear the threshold is ~0.003 + any
  small systematic drop from holdout filtering — empirically ≤0.002.

On PASS: update PROJECT-STATE.md and set the flag to True in
         run_ml_pipeline.py. Wait for Gate 3 (2 Saturday live runs).
On FAIL: keep the flag False. Investigate the failing criterion.
         Do NOT proceed to the next family without understanding why.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date

import numpy as np
import pandas as pd

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.normpath(os.path.join(HERE, '..', '..'))
ML_LAB = os.path.join(ROOT, 'ml_quant_finance_research', 'ml_research', 'stock_ml_lab')

BASELINE_FILE   = os.path.join(HERE, 'baseline_v1_auc.txt')
GATE2_CSV       = os.path.join(HERE, 'gate2_results.csv')
ML_STATE_PATH   = os.path.join(ROOT, 'shared', 'state', 'ml_state.json')
IC_RESULTS_PATH = os.path.join(ROOT, 'backtests', 'alpha_ic_results.csv')

FAMILY_FLAG_MAP = {
    'db_regime': 'ENABLE_DB_REGIME_FEATURES',
    'pead':      'ENABLE_PEAD_FEATURES',
    'earnings':  'ENABLE_EARNINGS_CALENDAR_FEATURES',
}
CLI_FLAG_MAP = {
    'db_regime': '--enable-db-regime',
    'pead':      '--enable-pead',
    'earnings':  '--enable-earnings',
}

# Gate 2 thresholds (from 00-OVERVIEW.md)
THRESHOLD_DELTA_AUC  = 0.003
THRESHOLD_DELTA_STD  = 0.010   # must not increase by more than this
THRESHOLD_DELTA_ICIR = -0.05   # must not decrease by more than this
THRESHOLD_DELTA_IC   = 0.003
MIN_OBS_FOR_IC_GATE  = 10      # IC gate deferred below this n_obs


# ─────────────────────────────────────────────────────────────────────────────
def parse_baseline():
    """Read baseline_v1_auc.txt → dict."""
    if not os.path.exists(BASELINE_FILE):
        print(f"ERROR: {BASELINE_FILE} not found. Run gate0_baseline.py first.")
        sys.exit(1)
    result = {}
    with open(BASELINE_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            k, _, v = line.partition('=')
            try:
                result[k.strip()] = float(v.strip())
            except ValueError:
                result[k.strip()] = v.strip()
    return result


def already_tested(family: str) -> bool:
    """Return True if gate2_results.csv already has a row for this family."""
    if not os.path.exists(GATE2_CSV) or os.path.getsize(GATE2_CSV) < 10:
        return False
    df = pd.read_csv(GATE2_CSV)
    return family in df.get('family', pd.Series(dtype=str)).values


def run_pipeline_for_family(family: str):
    """Invoke run_ml_pipeline.py with the given family flag enabled."""
    cli_flag = CLI_FLAG_MAP[family]
    cmd = [sys.executable, 'run_ml_pipeline.py', cli_flag]
    print(f"\n[Gate 2] Launching ML pipeline with {cli_flag}...")
    print(f"         CWD: {ML_LAB}")
    print(f"         This takes ~45–60 minutes. Logs stream below.\n")
    proc = subprocess.run(cmd, cwd=ML_LAB)
    if proc.returncode != 0:
        print(f"\nERROR: run_ml_pipeline.py exited with code {proc.returncode}.")
        print("       Review the output above for errors, then re-run gate2_run.py.")
        sys.exit(1)
    print("[Gate 2] Pipeline complete.\n")


def read_aucs_from_state():
    """Return (aucs_list, below_050_count) from ml_state.json."""
    if not os.path.exists(ML_STATE_PATH):
        print(f"ERROR: {ML_STATE_PATH} not found after pipeline run.")
        sys.exit(1)
    with open(ML_STATE_PATH, encoding='utf-8') as f:
        state = json.load(f)
    signals = state.get('model_signals', {})
    aucs = [v['auc'] for v in signals.values() if isinstance(v, dict) and 'auc' in v]
    if not aucs:
        print("ERROR: No AUC values found in ml_state.json model_signals.")
        sys.exit(1)
    below = sum(1 for a in aucs if a < 0.50)
    return aucs, below


def read_ic_stats(horizon: int = 21):
    """Read ml_alpha IC stats from alpha_ic_results.csv."""
    if not os.path.exists(IC_RESULTS_PATH):
        return None, None, 0
    df = pd.read_csv(IC_RESULTS_PATH)
    row = df[(df['model'] == 'ml_alpha') & (df['horizon'] == horizon)]
    if row.empty:
        return None, None, 0
    r = row.iloc[0]
    mean_ic = float(r['mean_ic']) if not pd.isna(r.get('mean_ic')) else None
    icir    = float(r['icir'])    if not pd.isna(r.get('icir'))    else None
    n_obs   = int(r['n_obs'])     if not pd.isna(r.get('n_obs'))   else 0
    return mean_ic, icir, n_obs


def append_result(row: dict):
    """Append one row to gate2_results.csv."""
    df_new = pd.DataFrame([row])
    write_header = (not os.path.exists(GATE2_CSV)) or os.path.getsize(GATE2_CSV) < 10
    df_new.to_csv(GATE2_CSV, mode='a', header=write_header, index=False)
    print(f"Result appended → {GATE2_CSV}")


# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Gate 2: test one Phase 1A feature family (AUC + IC vs baseline).'
    )
    parser.add_argument(
        '--family', required=True,
        choices=['db_regime', 'pead', 'earnings'],
        help='Feature family to test.',
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Re-run even if this family already has a row in gate2_results.csv.',
    )
    args = parser.parse_args()
    family    = args.family
    flag_name = FAMILY_FLAG_MAP[family]

    # ── Guard: already tested? ────────────────────────────────────────────────
    if already_tested(family) and not args.force:
        print(f"WARNING: '{family}' already has a row in gate2_results.csv.")
        print("         Use --force to overwrite. Exiting without running.")
        sys.exit(0)

    print("\n" + "=" * 60)
    print(f" GATE 2 — Testing family: {family}")
    print(f" Flag:    {flag_name}")
    print("=" * 60)

    # ── 1. Baseline ───────────────────────────────────────────────────────────
    baseline    = parse_baseline()
    auc_before  = float(baseline.get('mean_auc_best_of_3', 0))
    std_before  = float(baseline.get('std_auc_best_of_3', 0))
    ic_before   = float(baseline.get('mean_ic_ml_alpha_21d', 0))
    icir_before = float(baseline.get('icir_ml_alpha_21d', 0))
    n_obs_base  = int(float(baseline.get('n_obs_ml_alpha_21d', 0)))
    n_tix_base  = int(float(baseline.get('n_tickers', 126)))

    print(f"\nBaseline (v1): AUC={auc_before:.4f} ± {std_before:.4f}  "
          f"IC={ic_before:.4f}  ICIR={icir_before:.4f}  n_obs={n_obs_base}  "
          f"n_tickers={n_tix_base}")
    print(f"\nAUC note: baseline was recorded on FULL history (no holdout filter).")
    print(f"          Gate 2 test run uses the holdout filter (~11% fewer rows).")
    print(f"          Comparison is slightly conservative (harder to pass) — "
          f"correct direction.\n")

    # ── 2. Run pipeline with family enabled ───────────────────────────────────
    run_pipeline_for_family(family)

    # ── 3. Read new AUC ───────────────────────────────────────────────────────
    aucs_after, below_050 = read_aucs_from_state()
    auc_after  = float(np.mean(aucs_after))
    std_after  = float(np.std(aucs_after))
    n_tickers  = len(aucs_after)
    delta_auc  = auc_after - auc_before
    delta_std  = std_after - std_before

    print(f"New AUC:  {auc_after:.4f} ± {std_after:.4f}  "
          f"n_tickers={n_tickers}  n_below_0.50={below_050}")
    print(f"Delta:    AUC {delta_auc:+.4f}  std {delta_std:+.4f}")

    # ── 4. Read IC ────────────────────────────────────────────────────────────
    # alpha_eval.py reads signals from the LIVE DB — these don't change when
    # the ML pipeline changes. IC accumulates via Saturday live runs.
    # Gate 2 IC is deferred when n_obs < MIN_OBS_FOR_IC_GATE (= 10).
    ic_after, icir_after, n_obs_ic = read_ic_stats(horizon=21)
    delta_ic   = (ic_after   - ic_before)   if ic_after   is not None else None
    delta_icir = (icir_after - icir_before) if icir_after is not None else None
    ic_sufficient = (n_obs_ic >= MIN_OBS_FOR_IC_GATE)

    print(f"\nIC (ml_alpha 21d): IC={ic_after}  ICIR={icir_after}  n_obs={n_obs_ic}")
    if not ic_sufficient:
        print(f"  ⚠  IC gate DEFERRED (n_obs={n_obs_ic} < {MIN_OBS_FOR_IC_GATE}).")
        print(f"     Re-check after 2+ Saturday live pipeline runs accumulate signal dates.")

    # ── 5. Evaluate criteria ──────────────────────────────────────────────────
    print("\n--- Gate 2 Criteria ---")

    # C1: AUC improvement (primary — always active)
    c1 = delta_auc > THRESHOLD_DELTA_AUC
    print(f"  {'✓' if c1 else '✗'} delta_auc > +{THRESHOLD_DELTA_AUC:.3f}:  "
          f"{delta_auc:+.4f}  ({'PASS' if c1 else 'FAIL'})")

    # C2: AUC variance stability
    c2 = delta_std <= THRESHOLD_DELTA_STD
    print(f"  {'✓' if c2 else '✗'} delta_std ≤ +{THRESHOLD_DELTA_STD:.3f}:   "
          f"{delta_std:+.4f}  ({'PASS' if c2 else 'FAIL'})")

    # C3: No ticker regressions below 0.50
    c3 = (below_050 == 0)
    print(f"  {'✓' if c3 else '✗'} no ticker AUC < 0.50:  "
          f"n_below={below_050}  ({'PASS' if c3 else 'FAIL — investigate these tickers'})")

    # C4+C5: IC criteria (deferred if n_obs too low)
    if ic_sufficient:
        c4 = delta_ic > THRESHOLD_DELTA_IC
        c5 = delta_icir >= THRESHOLD_DELTA_ICIR
        print(f"  {'✓' if c4 else '✗'} delta_ic > +{THRESHOLD_DELTA_IC:.3f}:   "
              f"{delta_ic:+.4f}  ({'PASS' if c4 else 'FAIL'})")
        print(f"  {'✓' if c5 else '✗'} delta_icir ≥ {THRESHOLD_DELTA_ICIR:.2f}:  "
              f"{delta_icir:+.4f}  ({'PASS' if c5 else 'FAIL'})")
        hard = [c1, c2, c3, c4, c5]
    else:
        c4 = c5 = None
        print(f"  ⊙  IC criteria (C4+C5): DEFERRED (n_obs={n_obs_ic} < {MIN_OBS_FOR_IC_GATE})")
        hard = [c1, c2, c3]

    passed = all(hard)

    # ── 6. Verdict ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  GATE 2 VERDICT: {'✅  PASS' if passed else '❌  FAIL'}")
    print(f"{'=' * 60}")

    if passed:
        print(f"\nNext steps:")
        print(f"  1. Set {flag_name} = True in run_ml_pipeline.py (line ~69).")
        print(f"  2. Run the next two Saturday live pipeline runs with this flag enabled.")
        print(f"  3. After each Saturday run, check alpha_eval.py IC for ml_alpha.")
        print(f"     → Gate 3 requires live IC within ±0.008 of walk-forward IC.")
        print(f"  4. Once Gate 3 passes, proceed to the next feature family.")
        if c4 is None:
            print(f"\n  ⚠  IC gate was deferred. Revisit delta_ic after accumulating")
            print(f"     ≥{MIN_OBS_FOR_IC_GATE} ml_alpha signal observations in the live DB.")
            print(f"     If IC then fails (+0.003 threshold), revert the flag.")
    else:
        print(f"\nNext steps:")
        print(f"  • Keep {flag_name} = False (it was not changed by this script).")
        print(f"  • Investigate the failing criterion (see above).")
        print(f"  • Do NOT proceed to the next feature family until this is understood.")
        print(f"  • Optional: re-run baseline pipeline (no flags) to confirm")
        print(f"    AUC ≈ {auc_before:.4f} — this verifies the family is cleanly reversible.")

    # ── 7. Record ─────────────────────────────────────────────────────────────
    notes_parts = [
        f"n_tickers={n_tickers}",
        f"n_below_0.50={below_050}",
        f"IC_gate={'active' if ic_sufficient else f'deferred(n_obs={n_obs_ic}<{MIN_OBS_FOR_IC_GATE})'}",
        f"holdout_filtered=True",
        f"baseline_from=baseline_v1_auc.txt(full_history_no_filter)",
    ]
    row = {
        'date_tested':     date.today().isoformat(),
        'family':          family,
        'flag_name':       flag_name,
        'mean_ic_before':  f"{ic_before:.4f}",
        'mean_ic_after':   f"{ic_after:.4f}" if ic_after is not None else 'DEFERRED',
        'delta_ic':        f"{delta_ic:+.4f}" if delta_ic is not None else 'DEFERRED',
        'icir_before':     f"{icir_before:.4f}",
        'icir_after':      f"{icir_after:.4f}" if icir_after is not None else 'DEFERRED',
        'mean_auc_before': f"{auc_before:.4f}",
        'mean_auc_after':  f"{auc_after:.4f}",
        'delta_auc':       f"{delta_auc:+.4f}",
        'pass':            'PASS' if passed else 'FAIL',
        'notes':           '; '.join(notes_parts),
    }
    print()
    append_result(row)


if __name__ == '__main__':
    main()
