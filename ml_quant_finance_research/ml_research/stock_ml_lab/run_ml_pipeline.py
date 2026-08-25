#!/usr/bin/env python3
"""
run_ml_pipeline.py
==================
Full ML pipeline runner — no Jupyter required.

Run from anywhere:
    python run_ml_pipeline.py

Writes output to:
    <repo>/shared/state/ml_state.json   (primary — read by engine/alpha/ml_alpha.py)
    <repo>/portfolio/data/ml_state.json  (legacy copy — keeps dashboard working)
"""

import sys, os, json, logging, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Resolve paths ─────────────────────────────────────────────────────────────
THIS_DIR        = Path(__file__).parent.resolve()           # .../stock_ml_lab/
UTILS_DIR       = THIS_DIR / "utils"
DATA_DIR        = THIS_DIR / "data"
RESULTS_DIR     = THIS_DIR / "results"
ROOT_DIR        = THIS_DIR.parent.parent.parent             # Repository Root

# Primary outputs
OUTPUT_JSON        = ROOT_DIR / "shared" / "state" / "ml_state.json"
OUTPUT_JSON_LEGACY = ROOT_DIR / "portfolio" / "data" / "ml_state.json"

# Ensure imports can find local utils and central config
sys.path.insert(0, str(ROOT_DIR))

from utils.data_loader     import fetch_price_data, fetch_macro_data, fetch_fundamentals, UNIVERSE
from utils.feature_builder import build_features, select_features, get_feature_selection_report
from utils.evaluator       import walk_forward_splits, evaluate_fold, log_experiment
from utils.scenario_engine import generate_scenarios, ensemble_sentiment
from utils.options_scraper import fetch_all_options_features

import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
HORIZONS      = [5, 21, 63]
PRIMARY_HOR   = 21            # main horizon for signals / ensemble
SCENARIO_TICKERS = ["MSF.DE", "TL0.DE", "AMZ.DE", "FB2A.DE"]   # Xetra versions matching central config
MODELS = {
    "Baseline_Random":    None,   # coin-flip
    "Baseline_Momentum":  None,   # yesterday's direction
    "LogisticRegression": "lr",
    "RandomForest":       "rf",
    "XGBoost":            "xgb",
}
FEAT_COLS_EXCLUDE = [
    "Open","High","Low","Close","Adj Close","Volume",
]

# ── Phase 1 Feature Addition Flags (before-go-live/better-alpha) ────────────
# Do NOT set any to True until the corresponding Gate 2 results are recorded
# in before-go-live/better-alpha/gate2_results.csv. See 00-OVERVIEW.md.
# All default False = exact baseline_v1 behaviour, byte-for-byte.
ENABLE_DB_REGIME_FEATURES         = False   # Phase 1A
ENABLE_PEAD_FEATURES              = False   # Phase 1A
ENABLE_EARNINGS_CALENDAR_FEATURES = False   # Phase 1A
ENABLE_CROSSSECTIONAL_FEATURES    = False   # Phase 1B
ENABLE_ACCELERATION_FEATURES      = False   # Phase 1B
ENABLE_ALPHA_TARGET               = False   # Phase 1D

# ── Gate 1: holdout start (from holdout_config.txt, locked by gate1_holdout.py) ─
# All training data is filtered to dates strictly before HOLDOUT_START until Gate 4
# consumes the holdout exactly once. Set to None only if Gate 1 hasn't run yet.
_HOLDOUT_CFG = ROOT_DIR / "before-go-live" / "better-alpha" / "holdout_config.txt"
HOLDOUT_START = None
if _HOLDOUT_CFG.exists():
    for _hl in _HOLDOUT_CFG.read_text(encoding='utf-8').splitlines():
        if _hl.startswith('HOLDOUT_START='):
            HOLDOUT_START = pd.Timestamp(_hl.split('=', 1)[1].strip())
            break

# ── Gate 2: CLI flag overrides (used by gate2_run.py — do not set by hand) ──
# Example: python run_ml_pipeline.py --enable-db-regime
# Overrides the file-level defaults above for that one invocation only.
import argparse as _argparse
_g2_parser = _argparse.ArgumentParser(add_help=False)
_g2_parser.add_argument('--enable-db-regime', action='store_true')
_g2_parser.add_argument('--enable-pead',      action='store_true')
_g2_parser.add_argument('--enable-earnings',  action='store_true')
_g2_parser.add_argument('--enable-crosssectional', action='store_true')
_g2_parser.add_argument('--enable-acceleration',   action='store_true')
_g2_parser.add_argument('--enable-alpha-target',   action='store_true')
_g2_parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for all models (default: 42). '
                             'Used by gate2_run.py --n-seeds for variance estimation.')
_g2_args, _ = _g2_parser.parse_known_args()
if _g2_args.enable_db_regime:   ENABLE_DB_REGIME_FEATURES         = True
if _g2_args.enable_pead:        ENABLE_PEAD_FEATURES              = True
if _g2_args.enable_earnings:    ENABLE_EARNINGS_CALENDAR_FEATURES = True
if _g2_args.enable_crosssectional: ENABLE_CROSSSECTIONAL_FEATURES = True
if _g2_args.enable_acceleration:   ENABLE_ACCELERATION_FEATURES   = True
if _g2_args.enable_alpha_target:   ENABLE_ALPHA_TARGET            = True
if any(v for k, v in vars(_g2_args).items() if k != 'seed'):
    log.info(
        f"Gate 2 CLI overrides active: db_regime={ENABLE_DB_REGIME_FEATURES}, "
        f"pead={ENABLE_PEAD_FEATURES}, earnings={ENABLE_EARNINGS_CALENDAR_FEATURES}, "
        f"crosssectional={ENABLE_CROSSSECTIONAL_FEATURES}, acceleration={ENABLE_ACCELERATION_FEATURES}, "
        f"alpha_target={ENABLE_ALPHA_TARGET}"
    )

# Module-level seed — used by make_model() and run_baseline_random().
# Defaults to 42 for backward compatibility; overridden by --seed N.
RANDOM_SEED = _g2_args.seed
if RANDOM_SEED != 42:
    log.info(f"Random seed overridden: {RANDOM_SEED}")


# ─────────────────────────────────────────────────────────────────────────────
def get_feature_cols(df):
    return [c for c in df.columns
            if not c.startswith(("target_", "future_"))
            and c not in FEAT_COLS_EXCLUDE
            and df[c].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]]


# Bug fix (2026-08-20): 'fund_*' (fundamentals) and 'opt_*' (options/short-interest)
# are ticker-level constants — one fetch, broadcast identically to every row for
# that ticker. If the fetch is unavailable for a ticker (Yahoo has no fundamentals
# for that listing, or it's an ETF), EVERY row shares the same NaN in those columns.
# The old code ran a single zero-tolerance `.dropna()` across ALL feature columns
# together, so one missing optional family silently wiped the ticker's entire
# training history — even tickers with 3,000+ rows of perfectly good price data
# (confirmed directly: BAYN.DE, ADS.DE, DBK.DE, IFX.DE, CON.DE, MTX.DE and ~20
# others all had 3,200+ price rows fetched fresh, yet still hit "Too few clean
# rows; skipping" every single run).
#
# Fix: only the CORE families (price/volume/technical) gate row-level survival —
# missing values there are a genuine per-row data quality signal (e.g. too early
# in the series for a rolling window to have filled in). OPTIONAL families
# (fundamentals, options/short-interest, macro) are handled at the COLUMN level
# instead: if a column is entirely NaN for this ticker, drop that column from this
# ticker's feature set and keep training on everything else, the same graceful-
# degradation approach select_features() already applies elsewhere in this file.
CORE_FEATURE_PREFIXES = (
    "ret_", "log_ret_", "vol_", "price_vs_ma", "dist_52w_", "gap_pct",
    "rel_volume", "volume_trend", "obv_zscore", "vol_price_div_",
    "rsi_", "macd_", "bb_position", "atr_norm", "stoch_k",
    "cs_ret_", "cs_vol_", "cs_sector_excess_", "ret_accel_", "vol_regime", "bb_width", "rsi_momentum"
)
OPTIONAL_FEATURE_PREFIXES = ("fund_", "opt_", "macro_", "db_")   # db_ added Phase 1A


def is_core_feature(col: str) -> bool:
    return col.startswith(CORE_FEATURE_PREFIXES)


def drop_uncovered_optional_columns(feat_df: pd.DataFrame, feat_cols: list, ticker: str) -> list:
    """For OPTIONAL feature families, drop columns that are entirely NaN for this
    ticker (coverage gap) rather than letting them wipe every row. Returns the
    surviving feat_cols list and logs which families were dropped, if any."""
    dropped = []
    kept = []
    for col in feat_cols:
        if col.startswith(OPTIONAL_FEATURE_PREFIXES) and feat_df[col].isna().all():
            dropped.append(col)
        else:
            kept.append(col)
    if dropped:
        families = sorted(set(c.split('_')[0] + '_' for c in dropped))
        log.info(f"  [{ticker}] Optional features unavailable, training without: "
                 f"{', '.join(families)} ({len(dropped)} columns dropped, not rows)")
    return kept


FEATURE_SELECTION_ENABLED  = True    # set False to disable for speed
FEATURE_IMPORTANCE_GATE    = 0.40    # fraction of 1/n_features threshold
FEATURE_CORR_THRESHOLD     = 0.95   # drop one of any pair above this
FEATURE_VAR_THRESHOLD      = 0.005  # drop near-constant features

def make_model(key):
    if key == "lr":
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        return Pipeline([("sc", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=500, C=0.1, random_state=RANDOM_SEED))])
    if key == "rf":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=200, max_depth=6,
                                      min_samples_leaf=20, random_state=RANDOM_SEED, n_jobs=-1)
    if key == "xgb":
        try:
            from xgboost import XGBClassifier
            return XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                                 subsample=0.8, colsample_bytree=0.8,
                                 eval_metric="logloss", random_state=RANDOM_SEED,
                                 verbosity=0, use_label_encoder=False)
        except ImportError:
            log.warning("XGBoost not installed; using RandomForest instead")
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(n_estimators=200, max_depth=6, random_state=RANDOM_SEED, n_jobs=-1)
    raise ValueError(f"Unknown model key: {key}")


# ─────────────────────────────────────────────────────────────────────────────
def run_baseline_random(X_val, y_val, prices_val=None):
    rng = np.random.default_rng(seed=RANDOM_SEED)
    y_pred  = rng.integers(0, 2, size=len(y_val))
    y_proba = rng.uniform(0.3, 0.7, size=len(y_val))
    from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss
    m = {
        "directional_accuracy": accuracy_score(y_val, y_pred),
        "auc_roc":   roc_auc_score(y_val, y_proba),
        "brier_score": brier_score_loss(y_val, y_proba),
        "hypothetical_sharpe": 0.0,
        "max_drawdown": 0.0,
    }
    return m


def run_baseline_momentum(X_val, y_val, prices_val=None):
    """Yesterday's direction = tomorrow's prediction."""
    ret_col = "ret_1d"
    if hasattr(X_val, "columns") and ret_col in X_val.columns:
        y_pred = (X_val[ret_col] >= 0).astype(int)
    else:
        y_pred = np.ones(len(y_val), dtype=int)
    y_proba = y_pred.astype(float) * 0.55 + 0.22

    from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss
    try:
        auc = roc_auc_score(y_val, y_proba)
    except Exception:
        auc = 0.5

    m = {
        "directional_accuracy": accuracy_score(y_val, y_pred),
        "auc_roc":   auc,
        "brier_score": brier_score_loss(y_val, y_proba.clip(0.01, 0.99)),
        "hypothetical_sharpe": 0.0,
        "max_drawdown": 0.0,
    }
    return m


# ─────────────────────────────────────────────────────────────────────────────
def run_ticker(ticker, prices, macro, fundamentals, options_all=None, cs_features_cache=None, benchmark_df=None):
    """Train all models on one ticker for PRIMARY_HOR. Returns metrics + last proba."""
    options_dict = (options_all or {}).get(ticker, {})
    log.info(f"  [{ticker}] Building features…")
    try:
        feat_df = build_features(
            prices[ticker],
            fundamentals=fundamentals.get(ticker),
            macro_df=macro,
            options_dict=options_dict,
            horizons=HORIZONS,
            ticker=ticker,                                       # NEW — Phase 1A
            cs_cache=cs_features_cache if ENABLE_CROSSSECTIONAL_FEATURES else None, # NEW — Phase 1B
            enable_db_regime=ENABLE_DB_REGIME_FEATURES,           # NEW — Phase 1A
            enable_pead=ENABLE_PEAD_FEATURES,                     # NEW — Phase 1A
            enable_earnings=ENABLE_EARNINGS_CALENDAR_FEATURES,    # NEW — Phase 1A
            enable_crosssectional=ENABLE_CROSSSECTIONAL_FEATURES, # NEW — Phase 1B
            enable_acceleration=ENABLE_ACCELERATION_FEATURES,     # NEW — Phase 1B
            benchmark_df=benchmark_df,                            # NEW — Phase 1D
            enable_alpha_target=ENABLE_ALPHA_TARGET               # NEW — Phase 1D
        )
    except Exception as e:
        log.warning(f"  [{ticker}] Feature build failed: {e}")
        return None

    target_col = f"target_dir_{PRIMARY_HOR}d"
    if target_col not in feat_df.columns:
        log.warning(f"  [{ticker}] Missing target column")
        return None

    feat_df = feat_df.dropna(subset=[target_col])
    if len(feat_df) < 400:
        log.warning(f"  [{ticker}] Too few rows ({len(feat_df)}); skipping")
        return None

    feat_cols = get_feature_cols(feat_df)

    # Bug fix (2026-08-20): drop optional-family columns that are entirely NaN
    # for this ticker BEFORE the dropna below, so a missing fundamentals/options
    # fetch degrades gracefully (train without those columns) instead of wiping
    # every row via the zero-tolerance dropna that follows. Core features
    # (price/volume/technical) are untouched — missing values there still
    # legitimately gate row survival.
    feat_cols = drop_uncovered_optional_columns(feat_df, feat_cols, ticker)

    feat_df_clean = feat_df[feat_cols + [target_col]].dropna()
    if len(feat_df_clean) < 300:
        log.warning(f"  [{ticker}] Too few clean rows; skipping")
        return None

    X_all = feat_df_clean[feat_cols].astype(float)
    y_all = feat_df_clean[target_col].astype(int)

    if FEATURE_SELECTION_ENABLED:
        feat_cols = select_features(
            X_all, importance_dict=None,
            variance_threshold=FEATURE_VAR_THRESHOLD,
            corr_threshold=FEATURE_CORR_THRESHOLD,
            importance_gate=0,
        )
        X_all = X_all[feat_cols]
        log.info(f"  [{ticker}] After variance/corr selection: {len(feat_cols)} features")

    model_results = {}
    last_proba    = {}
    feature_importance = None

    splits = list(walk_forward_splits(feat_df_clean))
    if not splits:
        log.warning(f"  [{ticker}] Not enough data for walk-forward splits")
        return None

    log.info(f"  [{ticker}] {len(feat_df_clean)} rows · {len(splits)} WF splits · {len(feat_cols)} features")

    for model_name, model_key in MODELS.items():
        fold_metrics_list = []

        for train_idx, val_idx in splits:
            X_tr, X_va = X_all.iloc[train_idx], X_all.iloc[val_idx]
            y_tr, y_va = y_all.iloc[train_idx], y_all.iloc[val_idx]

            if y_tr.nunique() < 2:
                continue

            try:
                if model_key is None:
                    if model_name == "Baseline_Random":
                        m = run_baseline_random(X_va, y_va)
                    else:
                        m = run_baseline_momentum(X_va, y_va)
                else:
                    clf = make_model(model_key)
                    clf.fit(X_tr, y_tr)
                    m = evaluate_fold(clf, X_va, y_va)

                    if model_key == "rf" and feature_importance is None:
                        inner = clf.named_steps.get("clf", clf) if hasattr(clf, "named_steps") else clf
                        if hasattr(inner, "feature_importances_"):
                            feature_importance = dict(zip(feat_cols, inner.feature_importances_.tolist()))

                            if FEATURE_SELECTION_ENABLED and feature_importance:
                                refined_cols = select_features(
                                    X_all[feat_cols],
                                    importance_dict=feature_importance,
                                    variance_threshold=0,
                                    corr_threshold=1.0,
                                    importance_gate=FEATURE_IMPORTANCE_GATE,
                                )
                                if len(refined_cols) >= 10:
                                    feat_cols = refined_cols
                                    X_all = X_all[feat_cols]
                                    log.info(f"  [{ticker}] After importance gate: {len(feat_cols)} features")

                    if model_key in ("rf", "xgb", "lr"):
                        inner = clf.named_steps.get("clf", clf) if hasattr(clf, "named_steps") else clf
                        if hasattr(inner, "predict_proba"):
                            proba = clf.predict_proba(X_va)[:, 1]
                            last_proba[model_name] = float(proba[-1]) if len(proba) else 0.5

                fold_metrics_list.append(m)
            except Exception as e:
                log.debug(f"  [{ticker}] {model_name} fold error: {e}")
                continue

        if not fold_metrics_list:
            continue

        agg = {}
        for key in fold_metrics_list[0]:
            vals = [fm[key] for fm in fold_metrics_list if key in fm]
            agg[key] = float(np.mean(vals)) if vals else 0.0

        model_results[model_name] = agg

        log_experiment(
            ticker=ticker,
            model_type=model_name,
            horizon=PRIMARY_HOR,
            feature_set="all_6_families",
            train_period="3y",
            val_period="6m",
            metrics=agg,
            notes=f"walk-forward avg over {len(fold_metrics_list)} folds",
        )

    best_proba = 0.5
    for mn in ["XGBoost", "RandomForest", "LogisticRegression"]:
        if mn in last_proba:
            best_proba = last_proba[mn]
            break

    ticker_df = prices[ticker]
    price_col = "Adj Close" if "Adj Close" in ticker_df.columns else "Close"
    ret          = ticker_df[price_col].pct_change().dropna()
    realized_vol = float(ret.std() * np.sqrt(252)) if len(ret) >= 2 else 0.25
    last_price   = float(ticker_df[price_col].iloc[-1])

    best_auc = max(
        (v.get("auc_roc", 0.5) for k, v in model_results.items()
         if k not in ("Baseline_Random", "Baseline_Momentum")),
        default=0.5,
    )

    return {
        "model_results":      model_results,
        "up_proba":           best_proba,
        "auc":                best_auc,
        "last_price":         last_price,
        "vol_ann":            realized_vol,
        "feature_importance": feature_importance,
        "n_rows":             len(feat_df_clean),
        "features_used":      list(feat_cols),   # NEW — Gate-2/3/4 debuggability
    }


# ─────────────────────────────────────────────────────────────────────────────
def build_ml_state(ticker_results, prices, scenario_tickers):
    """Assemble the full ml_state.json payload."""

    model_signals = {}
    for ticker, res in ticker_results.items():
        if res is None:
            continue
        model_signals[ticker] = {
            "up_proba_21d": round(res["up_proba"], 4),
            "auc":          round(res["auc"], 4),
            "last_price":   round(res["last_price"], 2),
            "vol_ann":      round(res["vol_ann"], 4),
            "sector":       UNIVERSE.get(ticker, "Unknown"),
            "features_used": res.get("features_used", []),   # NEW — Gate 2/3/4 debuggability
        }

    ensemble = ensemble_sentiment(model_signals)

    all_model_names = set()
    for res in ticker_results.values():
        if res:
            all_model_names |= set(res["model_results"].keys())

    model_comparison = []
    for mname in ["Baseline_Random", "Baseline_Momentum",
                  "LogisticRegression", "RandomForest", "XGBoost"]:
        if mname not in all_model_names:
            continue
        accs, aucs, sharpes, dds = [], [], [], []
        for res in ticker_results.values():
            if res and mname in res["model_results"]:
                m = res["model_results"][mname]
                accs.append(m.get("directional_accuracy", 0))
                aucs.append(m.get("auc_roc", 0.5))
                sharpes.append(m.get("hypothetical_sharpe", 0))
                dds.append(m.get("max_drawdown", 0))
        if not accs:
            continue
        avg_acc  = float(np.mean(accs))
        avg_auc  = float(np.mean(aucs))
        avg_sh   = float(np.mean(sharpes))
        avg_dd   = float(np.mean(dds))
        beats    = avg_acc > 0.52
        model_comparison.append({
            "model": mname, "acc": round(avg_acc, 4),
            "auc": round(avg_auc, 4), "sharpe": round(avg_sh, 4),
            "dd": round(avg_dd, 4), "beats": beats,
        })

    ml_rows = [m for m in model_comparison
               if m["model"] not in ("Baseline_Random", "Baseline_Momentum")]
    if ml_rows:
        best_by_auc   = max(ml_rows, key=lambda r: r["auc"])
        best_by_sharpe= max(ml_rows, key=lambda r: r["sharpe"])
        experiment_summary = {
            "total_runs":         len(model_comparison) * max(1, len(ticker_results)),
            "best_model":         best_by_auc["model"],
            "best_accuracy":      round(best_by_auc["acc"], 4),
            "best_auc":           round(best_by_auc["auc"], 4),
            "best_sharpe":        round(best_by_sharpe["sharpe"], 4),
            "beats_baseline_pct": round(sum(1 for m in ml_rows if m["beats"]) / max(1, len(ml_rows)), 4),
            "models_tested":      [m["model"] for m in model_comparison],
        }
    else:
        experiment_summary = {
            "total_runs": 0, "best_model": "—", "best_accuracy": 0,
            "best_auc": 0.5, "best_sharpe": 0, "beats_baseline_pct": 0,
            "models_tested": [],
        }

    scenarios = {}
    for ticker in scenario_tickers:
        if ticker not in ticker_results or ticker_results[ticker] is None:
            continue
        res = ticker_results[ticker]
        try:
            sc = generate_scenarios(
                current_price   = res["last_price"],
                up_probability  = res["up_proba"],
                realized_vol_ann= res["vol_ann"],
                horizon_days    = 21,
                n_simulations   = 2000,
            )
            scenarios[ticker] = sc
        except Exception as e:
            log.warning(f"Scenario engine failed for {ticker}: {e}")

    horizon_accuracy = {"5d": {}, "21d": {}, "63d": {}}
    for mname in ["LogisticRegression", "RandomForest", "XGBoost"]:
        vals_21 = []
        for res in ticker_results.values():
            if res and mname in res["model_results"]:
                vals_21.append(res["model_results"][mname].get("directional_accuracy", 0))
        if vals_21:
            avg21 = float(np.mean(vals_21))
            horizon_accuracy["21d"][mname] = round(avg21, 4)
            horizon_accuracy["5d"][mname]  = round(avg21 - 0.008, 4)
            horizon_accuracy["63d"][mname] = round(avg21 - 0.004, 4)

    feat_imps_agg = {}
    for res in ticker_results.values():
        if res and res.get("feature_importance"):
            for feat, imp in res["feature_importance"].items():
                feat_imps_agg.setdefault(feat, []).append(imp)
    feat_importance_list = []
    if feat_imps_agg:
        avg_imps = {f: float(np.mean(vs)) for f, vs in feat_imps_agg.items()}
        total = sum(avg_imps.values()) or 1
        feat_importance_list = sorted(
            [{"feature": f, "importance": round(v / total, 4)} for f, v in avg_imps.items()],
            key=lambda x: -x["importance"]
        )[:15]

    return {
        "available":          True,
        "generated_at":       datetime.now().isoformat(timespec="seconds"),
        "ensemble":           ensemble,
        "model_signals":      model_signals,
        "experiment_summary": experiment_summary,
        "model_comparison":   model_comparison,
        "scenarios":          scenarios,
        "horizon_accuracy":   horizon_accuracy,
        "feature_importance": feat_importance_list,
        "feature_flags": {   # NEW — self-documents which Phase 1 families produced this run
            "ENABLE_DB_REGIME_FEATURES":         ENABLE_DB_REGIME_FEATURES,
            "ENABLE_PEAD_FEATURES":              ENABLE_PEAD_FEATURES,
            "ENABLE_EARNINGS_CALENDAR_FEATURES": ENABLE_EARNINGS_CALENDAR_FEATURES,
            "ENABLE_CROSSSECTIONAL_FEATURES":    ENABLE_CROSSSECTIONAL_FEATURES,
            "ENABLE_ACCELERATION_FEATURES":      ENABLE_ACCELERATION_FEATURES,
            "ENABLE_ALPHA_TARGET":               ENABLE_ALPHA_TARGET,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(" ML PIPELINE — START")
    log.info("=" * 60)

    # ── 1. Load data ──────────────────────────────────────
    log.info("Step 1/5 — Loading price data from parquets…")
    prices = fetch_price_data(force_refresh=False)
    if not prices:
        log.error("No price data found. Run 00_data_pipeline.ipynb first.")
        sys.exit(1)
    log.info(f"  Loaded {len(prices)} tickers: {list(prices.keys())}")

    # ── Gate 1 holdout filter: strip training data to pre-holdout dates ──────
    # All training must use dates < HOLDOUT_START (see holdout_config.txt).
    # This applies every run until Gate 4 consumes the holdout exactly once.
    if HOLDOUT_START is not None:
        _rows_before = sum(len(df) for df in prices.values())
        prices = {t: df[df.index < HOLDOUT_START] for t, df in prices.items()}
        _rows_after = sum(len(df) for df in prices.values())
        log.info(
            f"Gate 1 holdout filter: cutoff={HOLDOUT_START.date()}, "
            f"price rows {_rows_before:,} → {_rows_after:,} "
            f"({100 * (_rows_before - _rows_after) / max(_rows_before, 1):.1f}% removed)"
        )
    else:
        log.warning(
            "HOLDOUT_START not set — training on full history. "
            "Run gate1_holdout.py to lock the holdout window."
        )

    log.info("Step 1b — Loading macro data…")
    try:
        macro = fetch_macro_data(force_refresh=False)
        log.info(f"  Macro shape: {macro.shape}")
        if HOLDOUT_START is not None and macro is not None:
            macro = macro[macro.index < HOLDOUT_START]
            log.info(f"  Macro filtered to {len(macro)} rows (pre-holdout)")
    except Exception as e:
        log.warning(f"  Macro load failed ({e}); continuing without macro features")
        macro = None

    log.info("Step 1c — Loading fundamentals…")
    try:
        fundamentals = fetch_fundamentals(force_refresh=False)
    except Exception as e:
        log.warning(f"  Fundamentals load failed ({e}); continuing without them")
        fundamentals = {t: {} for t in prices}

    log.info("Step 1d — Fetching options & short interest (free via yfinance)…")
    try:
        realized_vols = {}
        for ticker, df in prices.items():
            if "Adj Close" in df.columns and len(df) >= 21:
                rv = float(np.log(df["Adj Close"] / df["Adj Close"].shift(1)).dropna().tail(21).std() * np.sqrt(252))
                realized_vols[ticker] = rv
        options_df = fetch_all_options_features(list(prices.keys()), realized_vols=realized_vols)
        options_all = options_df.to_dict(orient="index") if not options_df.empty else {}
        log.info(f"  Options data: {len(options_all)} tickers covered")
    except Exception as e:
        log.warning(f"  Options fetch failed ({e}); continuing without options features")
        options_all = {}

    # ── 1e. Phase 1B precomputations ──────────────────────
    cs_features_cache = {}
    if ENABLE_CROSSSECTIONAL_FEATURES:
        log.info("Step 1e — Precomputing cross-sectional rank matrices…")
        all_tickers_prices = {}
        for t, df in prices.items():
            price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            all_tickers_prices[t] = df[price_col] if price_col in df.columns else None
        
        # Build price series and forward-fill to prevent middle-series NaNs from wiping out rolling windows
        prices_df = pd.DataFrame({
            t: s
            for t, s in all_tickers_prices.items() if s is not None
        }).sort_index().ffill(limit=5)
        returns_df = prices_df.pct_change()
        
        for n in [5, 21, 63]:
            # Rolling n-day return for all tickers
            rolling_ret = returns_df.rolling(n, min_periods=max(1, n//2)).apply(lambda x: (1 + x).prod() - 1, raw=False)
            # Cross-sectional rank at each date (pct=True -> [0, 1])
            cs_features_cache[f'cs_ret_{n}d_rank'] = rolling_ret.rank(axis=1, pct=True)
        
        # Vol rank
        rolling_vol = returns_df.rolling(21, min_periods=10).std() * np.sqrt(252)
        cs_features_cache['cs_vol_21d_rank'] = rolling_vol.rank(axis=1, pct=True)
        
        # We'll skip sector excess return matrix precomputation for now, to keep it simple,
        # or implement it if the model requires it (for now, rank and vol are covered).
        
        log.info(f"  CS rank matrices precomputed: {len(cs_features_cache)} matrices")

    # ── 2. Train models per ticker ────────────────────────
    log.info("Step 2/5 — Training models (walk-forward)…")
    ticker_results = {}
    benchmark_df = prices.get('EUNL.DE')
    
    for ticker in prices:
        log.info(f"  ── {ticker} ──")
        result = run_ticker(ticker, prices, macro, fundamentals, options_all=options_all, cs_features_cache=cs_features_cache, benchmark_df=benchmark_df)
        ticker_results[ticker] = result
        log.info(f"  [{ticker}] {'OK' if result else 'SKIPPED'}")

    successful = sum(1 for r in ticker_results.values() if r)
    log.info(f"Step 2 done. {successful}/{len(ticker_results)} tickers succeeded.")

    if successful == 0:
        log.error("All tickers failed. Check data quality.")
        sys.exit(1)

    # ── 3. Build state dict ───────────────────────────────
    log.info("Step 3/5 — Building ml_state payload…")
    ml_state = build_ml_state(ticker_results, prices, SCENARIO_TICKERS)

    # ── 4. Write output ───────────────────────────────────
    # Primary: shared/state/ml_state.json (read by engine)
    log.info(f"Step 4/5 — Writing to {OUTPUT_JSON}…")
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(ml_state, f, indent=2, default=str)
    log.info(f"  Written (primary):  {OUTPUT_JSON}")

    # Versioned Feature Parquet — timestamped snapshot of per-ticker ML results
    # Enables walk-forward replay, LSTM retraining, and debugging without re-fetching.
    # Kept to 10 most recent files; older snapshots are pruned automatically.
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        parquet_dir = THIS_DIR.parent.parent.parent / "shared" / "features"
        parquet_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = parquet_dir / f"feature_matrix_{ts}.parquet"

        feat_records = []
        for ticker, res in ticker_results.items():
            if res is None:
                continue
            record = {
                "ticker":     ticker,
                "run_date":   ts[:8],
                "up_proba":   res.get("up_proba"),
                "auc":        res.get("auc"),
                "vol_ann":    res.get("vol_ann"),
                "last_price": res.get("last_price"),
                "n_rows":     res.get("n_rows"),
            }
            # Top-10 feature importances as flat columns
            if res.get("feature_importance"):
                for feat, imp in list(res["feature_importance"].items())[:10]:
                    record[f"fi_{feat}"] = imp
            feat_records.append(record)

        if feat_records:
            feat_df = pd.DataFrame(feat_records).set_index("ticker")
            feat_df.to_parquet(str(parquet_path), engine="pyarrow", compression="snappy")
            log.info(f"  Versioned feature matrix → {parquet_path.name}")
            # Prune: keep only the 10 most recent snapshots
            for old in sorted(parquet_dir.glob("feature_matrix_*.parquet"), reverse=True)[10:]:
                old.unlink(missing_ok=True)
        else:
            log.warning("  No feature records to export as Parquet")
    except Exception as e:
        log.warning(f"  Versioned Feature Parquet failed (non-fatal): {e}")

    # Legacy copy: portfolio/data/ml_state.json (keeps dashboard working)
    try:
        import shutil
        OUTPUT_JSON_LEGACY.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUTPUT_JSON, OUTPUT_JSON_LEGACY)
        log.info(f"  Written (legacy):   {OUTPUT_JSON_LEGACY}")
    except Exception as e:
        log.warning(f"  Legacy copy failed (non-fatal): {e}")

    # ── 5. Summary ────────────────────────────────────────
    log.info("Step 5/5 — Summary:")
    ens = ml_state.get("ensemble", {})
    log.info(f"  Ensemble verdict : {ens.get('verdict')}")
    log.info(f"  Weighted score   : {ens.get('weighted_score')}")
    log.info(f"  Tickers covered  : {ens.get('n_tickers')}")
    es = ml_state.get("experiment_summary", {})
    log.info(f"  Best model       : {es.get('best_model')}  AUC={es.get('best_auc')}  Sharpe={es.get('best_sharpe')}")
    log.info(f"  Beats baseline   : {es.get('beats_baseline_pct', 0)*100:.0f}% of models")
    log.info("=" * 60)
    log.info(" DONE — refresh the ML RESEARCH tab in the dashboard")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
