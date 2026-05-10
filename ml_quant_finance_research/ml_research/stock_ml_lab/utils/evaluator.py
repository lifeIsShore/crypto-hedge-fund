"""evaluator.py — Walk-forward splits, fold metrics, experiment logger."""
import uuid, csv, logging
from pathlib import Path
from datetime import datetime
import numpy as np

log = logging.getLogger(__name__)
RESULTS_DIR = Path(__file__).parent.parent / "results"
LOG_FILE = RESULTS_DIR / "experiment_log.csv"
LOG_FIELDS = ["run_id","run_date","ticker","model_type","prediction_horizon","feature_set",
              "train_period","val_period","directional_accuracy","auc_roc","brier_score",
              "hypothetical_sharpe","max_drawdown","beats_baseline","notes"]

def walk_forward_splits(df, train_years=3, val_months=6, step_months=6):
    """Generator of (train_idx, val_idx). No shuffling — time order is sacred."""
    n = len(df)
    train_size = int(train_years * 252)
    val_size   = int(val_months * 21)
    step_size  = int(step_months * 21)
    start = train_size
    while start + val_size <= n:
        yield list(range(0, start)), list(range(start, min(start+val_size, n)))
        start += step_size

def evaluate_fold(model, X_val, y_val, prices_val=None):
    from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                                  f1_score, roc_auc_score, brier_score_loss)
    y_pred  = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:,1] if hasattr(model,"predict_proba") else None
    m = {
        "directional_accuracy": accuracy_score(y_val, y_pred),
        "precision_up": precision_score(y_val, y_pred, zero_division=0),
        "recall_up":    recall_score(y_val, y_pred, zero_division=0),
        "f1":           f1_score(y_val, y_pred, zero_division=0),
        # Defaults: auc_roc=0.5 (random) and financial metrics=0 when prices not provided.
        # These are always present so downstream .get() calls never silently return 0 for AUC.
        "auc_roc":              0.5,
        "brier_score":          0.5,
        "hypothetical_sharpe":  0.0,
        "max_drawdown":         0.0,
    }
    if y_proba is not None:
        try:
            m["auc_roc"]     = roc_auc_score(y_val, y_proba)
        except Exception:
            pass  # only one class in val fold — keep default 0.5
        m["brier_score"] = brier_score_loss(y_val, y_proba)
        if prices_val is not None:
            sig = (y_proba > 0.5).astype(int)
            ret = np.diff(prices_val) / prices_val[:-1]
            n_min = min(len(sig), len(ret))
            sr = sig[:n_min] * ret[:n_min]
            sharpe = float(sr.mean()/sr.std()*np.sqrt(252)) if sr.std()>0 else 0.0
            cum = np.cumprod(1+sr)
            roll_max = np.maximum.accumulate(cum)
            dd = float((cum - roll_max).min() / roll_max.max())
            m["hypothetical_sharpe"] = sharpe
            m["max_drawdown"] = dd
    return m

def log_experiment(ticker, model_type, horizon, feature_set, train_period, val_period, metrics, notes=""):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": str(uuid.uuid4())[:8],
        "run_date": datetime.now().isoformat(timespec="seconds"),
        "ticker": ticker, "model_type": model_type,
        "prediction_horizon": horizon, "feature_set": feature_set,
        "train_period": train_period, "val_period": val_period,
        "directional_accuracy": round(metrics.get("directional_accuracy",0),4),
        "auc_roc":              round(metrics.get("auc_roc",0),4),
        "brier_score":          round(metrics.get("brier_score",0),4),
        "hypothetical_sharpe":  round(metrics.get("hypothetical_sharpe",0),4),
        "max_drawdown":         round(metrics.get("max_drawdown",0),4),
        "beats_baseline":       metrics.get("directional_accuracy",0) > 0.52,
        "notes": notes,
    }
    write_hdr = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if write_hdr: w.writeheader()
        w.writerow(row)
    log.info(f"Logged: {row['run_id']} | {ticker} | {model_type} | acc={row['directional_accuracy']}")
    return row
