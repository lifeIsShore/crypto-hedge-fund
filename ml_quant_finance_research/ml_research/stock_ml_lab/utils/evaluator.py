"""evaluator.py — Walk-forward splits, fold metrics, experiment logger.

Stream 7 changes:
  - walk_forward_splits() now enforces a PURGE_BUFFER between train and val
    so lagged features (RSI-14, 5d momentum, etc.) computed on training data
    can never appear in the validation window. This prevents data leakage.
  - Added get_walk_forward_report() for dashboard diagnostics.
"""
import uuid, csv, logging
from pathlib import Path
from datetime import datetime
import numpy as np

log = logging.getLogger(__name__)
RESULTS_DIR = Path(__file__).parent.parent / "results"
LOG_FILE = RESULTS_DIR / "experiment_log.csv"
LOG_FIELDS = [
    "run_id", "run_date", "ticker", "model_type", "prediction_horizon",
    "feature_set", "train_period", "val_period",
    "directional_accuracy", "auc_roc", "brier_score",
    "hypothetical_sharpe", "max_drawdown", "beats_baseline", "notes",
]

# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD SPLITS  (Stream 7 — purge buffer)
# ─────────────────────────────────────────────────────────────────────────────

# 7 trading days: covers any feature with up to a 5-day lag (RSI-14 smoothing,
# 5d momentum, 5d volume trend) plus a 2-day margin.
# Increasing this reduces leakage risk but shrinks the number of valid splits.
PURGE_BUFFER_DAYS = 7


def walk_forward_splits(
    df,
    train_years: float = 3,
    val_months: float = 6,
    step_months: float = 6,
    purge_buffer: int = PURGE_BUFFER_DAYS,
):
    """
    Generator of (train_idx, val_idx) tuples for time-series cross-validation.

    Key invariant: the last `purge_buffer` rows of each training window are
    EXCLUDED from both train and val indices, ensuring that any feature
    computed with up to a (purge_buffer - 1)-day look-back on training data
    cannot appear in the validation window.

    Example with purge_buffer=7:
        train_idx = [0, ..., train_end - 7]
        val_idx   = [train_end, ..., train_end + val_size]
        The 7 rows [train_end-7, ..., train_end-1] are in neither set.

    This is the "embargo" method from Lopez de Prado (2018), Chapter 7.

    Args:
        df:           DataFrame indexed by date (any feature/target columns)
        train_years:  Training window in years (default 3)
        val_months:   Validation window in months (default 6)
        step_months:  Walk-forward step in months (default 6 — non-overlapping val)
        purge_buffer: Number of rows to exclude between train and val (default 7)

    Yields:
        (train_idx, val_idx): lists of integer positions (iloc-compatible)
    """
    n          = len(df)
    train_size = int(train_years * 252)
    val_size   = int(val_months * 21)
    step_size  = int(step_months * 21)

    if n < train_size + purge_buffer + val_size:
        log.warning(
            f"walk_forward_splits: only {n} rows — insufficient for "
            f"train={train_size} + buffer={purge_buffer} + val={val_size}. "
            "Returning 0 splits."
        )
        return

    start = train_size
    split_count = 0

    while start + val_size <= n:
        # Train: [0, start - purge_buffer)  — the purge buffer rows are excluded
        train_end = start - purge_buffer
        if train_end < 50:   # safety: at least 50 training rows
            start += step_size
            continue

        train_idx = list(range(0, train_end))
        val_idx   = list(range(start, min(start + val_size, n)))

        if len(train_idx) >= 50 and len(val_idx) >= 10:
            split_count += 1
            yield train_idx, val_idx

        start += step_size

    if split_count == 0:
        log.warning(
            f"walk_forward_splits: produced 0 valid splits after purge. "
            f"Consider reducing purge_buffer (current={purge_buffer})."
        )


def get_walk_forward_report(df, train_years=3, val_months=6,
                            step_months=6, purge_buffer=PURGE_BUFFER_DAYS) -> list:
    """
    Returns a list of dicts describing each split — useful for dashboard diagnostics.
    Shows exact date ranges and sizes for train/purge/val windows.
    """
    splits_info = []
    dates = df.index.tolist() if hasattr(df, 'index') else list(range(len(df)))

    for i, (train_idx, val_idx) in enumerate(
        walk_forward_splits(df, train_years, val_months, step_months, purge_buffer)
    ):
        purge_start = train_idx[-1] + 1
        purge_end   = val_idx[0] - 1

        splits_info.append({
            "fold":             i + 1,
            "train_start":      str(dates[train_idx[0]])[:10],
            "train_end":        str(dates[train_idx[-1]])[:10],
            "train_rows":       len(train_idx),
            "purge_start":      str(dates[purge_start])[:10] if purge_start < len(dates) else "—",
            "purge_end":        str(dates[purge_end])[:10]   if purge_end   < len(dates) else "—",
            "purge_rows":       purge_buffer,
            "val_start":        str(dates[val_idx[0]])[:10],
            "val_end":          str(dates[val_idx[-1]])[:10],
            "val_rows":         len(val_idx),
            "leakage_possible": False,   # purge buffer enforces this
        })

    return splits_info


# ─────────────────────────────────────────────────────────────────────────────
# FOLD METRICS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_fold(model, X_val, y_val, prices_val=None):
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, roc_auc_score, brier_score_loss,
    )

    y_pred  = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1] if hasattr(model, "predict_proba") else None

    m = {
        "directional_accuracy": accuracy_score(y_val, y_pred),
        "precision_up":         precision_score(y_val, y_pred, zero_division=0),
        "recall_up":            recall_score(y_val, y_pred, zero_division=0),
        "f1":                   f1_score(y_val, y_pred, zero_division=0),
        # Always present so downstream .get() calls never silently get 0 for AUC
        "auc_roc":             0.5,
        "brier_score":         0.5,
        "hypothetical_sharpe": 0.0,
        "max_drawdown":        0.0,
    }

    if y_proba is not None:
        try:
            m["auc_roc"] = roc_auc_score(y_val, y_proba)
        except Exception:
            pass   # only one class in val fold — keep default 0.5

        m["brier_score"] = brier_score_loss(y_val, y_proba)

        if prices_val is not None:
            sig = (y_proba > 0.5).astype(int)
            ret = np.diff(prices_val) / prices_val[:-1]
            n_min = min(len(sig), len(ret))
            sr = sig[:n_min] * ret[:n_min]
            sharpe = float(sr.mean() / sr.std() * np.sqrt(252)) if sr.std() > 0 else 0.0
            cum      = np.cumprod(1 + sr)
            roll_max = np.maximum.accumulate(cum)
            dd       = float((cum - roll_max).min() / roll_max.max())
            m["hypothetical_sharpe"] = sharpe
            m["max_drawdown"]        = dd

    return m


# ─────────────────────────────────────────────────────────────────────────────
# EXPERIMENT LOGGER
# ─────────────────────────────────────────────────────────────────────────────

def log_experiment(ticker, model_type, horizon, feature_set,
                   train_period, val_period, metrics, notes=""):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id":                str(uuid.uuid4())[:8],
        "run_date":              datetime.now().isoformat(timespec="seconds"),
        "ticker":                ticker,
        "model_type":            model_type,
        "prediction_horizon":    horizon,
        "feature_set":           feature_set,
        "train_period":          train_period,
        "val_period":            val_period,
        "directional_accuracy":  round(metrics.get("directional_accuracy", 0), 4),
        "auc_roc":               round(metrics.get("auc_roc", 0), 4),
        "brier_score":           round(metrics.get("brier_score", 0), 4),
        "hypothetical_sharpe":   round(metrics.get("hypothetical_sharpe", 0), 4),
        "max_drawdown":          round(metrics.get("max_drawdown", 0), 4),
        "beats_baseline":        metrics.get("directional_accuracy", 0) > 0.52,
        "notes":                 notes,
    }
    write_hdr = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if write_hdr:
            w.writeheader()
        w.writerow(row)
    log.info(
        f"Logged: {row['run_id']} | {ticker} | {model_type} | "
        f"acc={row['directional_accuracy']} | auc={row['auc_roc']} "
        f"| purge={PURGE_BUFFER_DAYS}d"
    )
    return row
