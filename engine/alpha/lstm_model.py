# engine/alpha/lstm_model.py
"""
Alpha Model — LSTM (Long Short-Term Memory) price direction model.

Architecture:
  Input  : rolling window of T=20 days × N features (from feature_store)
  Hidden : 2 LSTM layers (64 units each) + Dropout(0.3)
  Output : sigmoid → up_proba_21d  (probability stock is higher in 21 trading days)

Design decisions:
  - Inherits AlphaModel so it plugs into the scheduler and BL pipeline
    exactly like XGBoost / RandomForest.
  - Walk-forward validated using the same walk_forward_splits() used by
    run_ml_pipeline.py — NO static train/test split.
  - Saves the trained model to engine/alpha/saved_models/lstm_<ticker>.pt
    so it can be reloaded without retraining on every dashboard refresh.
  - up_proba contract enforced by validate_signals() from base.py.

Requirements:
    pip install torch  (CPU-only is fine for this scale)

Usage (from scheduler or bat):
    from engine.alpha.lstm_model import LSTMAlpha
    model = LSTMAlpha()
    signals = model.generate_signals(date='2026-05-12', tickers=['AAPL', 'MSFT'])
    model.persist_signals(date, signals)

Training (once per week, triggered from scheduler):
    model.train_all(tickers, date)
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, date as date_type
from engine.alpha.base import AlphaModel, validate_signals

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE        = Path(__file__).parent
SAVED_DIR    = _HERE / 'saved_models'
SAVED_DIR.mkdir(exist_ok=True)

# ── Hyperparameters ────────────────────────────────────────────────────────────
SEQ_LEN      = 20      # look-back window in trading days
HIDDEN_SIZE  = 64      # LSTM hidden units per layer
N_LAYERS     = 2       # stacked LSTM layers
DROPOUT      = 0.30    # dropout between LSTM layers
LR           = 1e-3    # Adam learning rate
EPOCHS       = 30      # training epochs per fold
BATCH_SIZE   = 64      # mini-batch size
MIN_ROWS     = 500     # minimum rows required to train (avoids overfitting on thin data)
AUC_GATE     = 0.53    # minimum AUC to include in live signals

# ── Features to pull from feature_store ───────────────────────────────────────
FEATURE_NAMES = [
    'mom_1m', 'mom_3m', 'mom_6m', 'mom_12m',
    'vol_21d', 'vol_63d', 'vol_of_vol',
    'rsi_14',
]


# ─────────────────────────────────────────────────────────────────────────────
# PYTORCH MODEL DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

def _build_lstm(n_features: int):
    """
    Returns a PyTorch LSTM → FC → Sigmoid model.
    Lazy import so the module loads even without torch installed.
    """
    try:
        import torch
        import torch.nn as nn

        class _LSTMNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(
                    input_size=n_features,
                    hidden_size=HIDDEN_SIZE,
                    num_layers=N_LAYERS,
                    dropout=DROPOUT if N_LAYERS > 1 else 0.0,
                    batch_first=True,
                )
                self.dropout = nn.Dropout(DROPOUT)
                self.fc      = nn.Linear(HIDDEN_SIZE, 1)
                self.sigmoid = nn.Sigmoid()

            def forward(self, x):
                # x: (batch, seq_len, n_features)
                out, _ = self.lstm(x)
                out = self.dropout(out[:, -1, :])   # last timestep
                return self.sigmoid(self.fc(out)).squeeze(-1)

        return _LSTMNet()

    except ImportError:
        raise ImportError(
            "PyTorch is required for LSTMAlpha. "
            "Install with: pip install torch"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DATA PREPARATION
# ─────────────────────────────────────────────────────────────────────────────

def _load_feature_sequences(ticker: str, seq_len: int = SEQ_LEN) -> tuple:
    """
    Loads feature matrix from feature_store + prices table,
    builds sliding-window sequences for LSTM.

    Returns:
        X  : np.ndarray shape (N, seq_len, n_features)
        y  : np.ndarray shape (N,) — binary target (1 = up in 21d)
        dates: list of date strings (one per sample, aligned to sequence end)
    """
    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        # Load features from feature_store
        # SQLite text() doesn't handle tuple binding for IN automatically in all versions/drivers.
        # Since FEATURE_NAMES is a constant, we format the placeholders manually.
        placeholders = ', '.join([':f' + str(i) for i in range(len(FEATURE_NAMES))])
        params = {"t": ticker}
        for i, name in enumerate(FEATURE_NAMES):
            params[f"f{i}"] = name

        result = session.execute(text(f"""
            SELECT date, feature_name, feature_value
            FROM feature_store
            WHERE ticker = :t AND feature_name IN ({placeholders})
            ORDER BY date ASC
        """), params)
        rows = result.fetchall()

        # Load prices for target construction
        price_result = session.execute(text("""
            SELECT date, adj_close FROM prices
            WHERE ticker = :t AND adj_close IS NOT NULL
            ORDER BY date ASC
        """), {"t": ticker})
        price_rows = price_result.fetchall()
    finally:
        session.close()

    if not rows or not price_rows:
        return np.array([]), np.array([]), []

    # Build feature DataFrame
    feat_df = pd.DataFrame(rows, columns=['date', 'feature_name', 'feature_value'])
    feat_pivot = feat_df.pivot(index='date', columns='feature_name', values='feature_value')

    # Align to available features (in case some are missing for this ticker)
    available = [f for f in FEATURE_NAMES if f in feat_pivot.columns]
    if len(available) < 3:
        logger.warning(f"[LSTM] {ticker}: only {len(available)} features available — skipping")
        return np.array([]), np.array([]), []
    feat_pivot = feat_pivot[available].sort_index().ffill(limit=5).dropna()

    # Build price series for target
    price_df = pd.DataFrame(price_rows, columns=['date', 'adj_close'])
    price_df = price_df.set_index('date').sort_index()

    # Align dates
    common_dates = feat_pivot.index.intersection(price_df.index)
    feat_pivot   = feat_pivot.loc[common_dates]
    price_df     = price_df.loc[common_dates]

    if len(feat_pivot) < seq_len + 22:
        logger.warning(f"[LSTM] {ticker}: insufficient rows ({len(feat_pivot)}) — need {seq_len + 22}")
        return np.array([]), np.array([]), []

    # Build sliding windows
    feat_vals = feat_pivot.values.astype(np.float32)
    dates_all = feat_pivot.index.tolist()
    prices    = price_df['adj_close'].values.astype(np.float32)

    X_seqs, y_labels, sample_dates = [], [], []
    horizon = 21

    for i in range(seq_len, len(feat_vals) - horizon):
        window = feat_vals[i - seq_len:i]
        cur_price  = prices[i]
        fut_price  = prices[i + horizon]
        if cur_price <= 0:
            continue
        label = 1 if fut_price > cur_price else 0
        X_seqs.append(window)
        y_labels.append(label)
        sample_dates.append(dates_all[i])

    if not X_seqs:
        return np.array([]), np.array([]), []

    # Normalise: z-score per feature across the whole series
    # (per-window normalisation would leak future data)
    X = np.stack(X_seqs, axis=0)
    mean = X.mean(axis=(0, 1), keepdims=True)
    std  = X.std(axis=(0, 1), keepdims=True) + 1e-8
    X    = (X - mean) / std

    return X.astype(np.float32), np.array(y_labels, dtype=np.float32), sample_dates


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def _train_fold(model, X_tr, y_tr, X_va, y_va, epochs: int = EPOCHS):
    """
    Train one walk-forward fold. Returns val AUC.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    from sklearn.metrics import roc_auc_score

    device = torch.device('cpu')   # CPU is fine for portfolio-scale data
    model  = model.to(device)

    X_t = torch.tensor(X_tr, dtype=torch.float32, device=device)
    y_t = torch.tensor(y_tr, dtype=torch.float32, device=device)
    ds  = TensorDataset(X_t, y_t)
    dl  = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=True)

    opt      = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.BCELoss()

    model.train()
    for _ in range(epochs):
        for xb, yb in dl:
            opt.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            opt.step()

    # Validation AUC
    model.eval()
    with torch.no_grad():
        X_v  = torch.tensor(X_va, dtype=torch.float32, device=device)
        prob = model(X_v).numpy()

    try:
        auc = float(roc_auc_score(y_va, prob))
    except Exception:
        auc = 0.5

    return model, auc, float(prob[-1]) if len(prob) > 0 else 0.5


# ─────────────────────────────────────────────────────────────────────────────
# ALPHA MODEL CLASS
# ─────────────────────────────────────────────────────────────────────────────

class LSTMAlpha(AlphaModel):
    """
    LSTM-based directional alpha model.

    Integrates with the existing AlphaModel interface:
      - generate_signals()  : load saved model → predict → return signal DF
      - train_all()         : walk-forward train → save model → return metrics
      - persist_signals()   : inherited from AlphaModel (writes to signals table)
    """
    name = 'lstm'

    def __init__(self):
        self._meta: dict = {}   # {ticker: {'auc': float, 'trained_at': str}}
        self._load_meta()

    # ── Meta (tracks which tickers have saved models + their AUC) ─────────────
    def _meta_path(self) -> Path:
        return SAVED_DIR / 'lstm_meta.json'

    def _load_meta(self):
        if self._meta_path().exists():
            try:
                with open(self._meta_path()) as f:
                    self._meta = json.load(f)
            except Exception:
                self._meta = {}

    def _save_meta(self):
        with open(self._meta_path(), 'w') as f:
            json.dump(self._meta, f, indent=2, default=str)

    def _model_path(self, ticker: str) -> Path:
        return SAVED_DIR / f'lstm_{ticker}.pt'

    # ── Load a saved model ────────────────────────────────────────────────────
    def _load_model(self, ticker: str, n_features: int):
        """Load saved PyTorch model weights. Returns None if no saved model."""
        import torch
        path = self._model_path(ticker)
        if not path.exists():
            return None
        try:
            model = _build_lstm(n_features)
            model.load_state_dict(torch.load(str(path), map_location='cpu'))
            model.eval()
            return model
        except Exception as e:
            logger.warning(f"[LSTM] Could not load model for {ticker}: {e}")
            return None

    # ── Save model ────────────────────────────────────────────────────────────
    def _save_model(self, model, ticker: str):
        import torch
        torch.save(model.state_dict(), str(self._model_path(ticker)))

    # ── generate_signals: fast path (no training) ─────────────────────────────
    def generate_signals(self, date: str, tickers: list) -> pd.DataFrame:
        """
        Load saved LSTM models and generate signals for today's feature window.
        Falls back gracefully if torch is not installed or model not trained yet.

        Returns DataFrame with columns: ticker, expected_return, confidence, raw_score
        """
        try:
            import torch
        except ImportError:
            logger.warning("[LSTM] PyTorch not installed — skipping LSTM signals")
            return pd.DataFrame()

        rows = []
        for ticker in tickers:
            X, y, dates = _load_feature_sequences(ticker)
            if X.size == 0:
                continue

            n_features = X.shape[2]
            model = self._load_model(ticker, n_features)
            if model is None:
                logger.debug(f"[LSTM] {ticker}: no saved model — run train_all() first")
                continue

            meta = self._meta.get(ticker, {})
            auc  = float(meta.get('auc', 0.5))
            if auc < AUC_GATE:
                logger.debug(f"[LSTM] {ticker}: AUC {auc:.3f} below gate — excluded")
                continue

            # Predict on the most recent sequence
            import torch as th
            model.eval()
            with th.no_grad():
                x_latest = th.tensor(X[-1:], dtype=th.float32)
                up_proba = float(model(x_latest).item())

            # Contract: clip to [0, 1]
            up_proba = float(np.clip(up_proba, 0.0, 1.0))

            # Expected return (same formula as ml_alpha.py)
            edge            = (up_proba - 0.5) * 2
            expected_return = round(edge * 0.04, 4)  # 4% scale

            # Confidence: AUC rescaled [0.5, 0.75] → [0, 1]
            confidence = min(max((auc - 0.5) * 4, 0.01), 1.0)

            rows.append({
                'ticker':          ticker,
                'expected_return': expected_return,
                'confidence':      round(confidence, 4),
                'raw_score':       round(up_proba, 4),
            })

        result = pd.DataFrame(rows)
        if not result.empty:
            result = validate_signals(result, model_name=self.name)
            logger.info(f"[LSTM] {len(result)} signals for {date}")
        return result

    # ── train_all: walk-forward train, save models ─────────────────────────────
    def train_all(self, tickers: list, date: str = None) -> dict:
        """
        Walk-forward train LSTM for each ticker and save models.
        Typically called from the Saturday ML refresh (same schedule as XGBoost).

        Returns {ticker: {'auc': float, 'n_folds': int}}
        """
        try:
            import torch
        except ImportError:
            logger.error("[LSTM] PyTorch not installed. Install with: pip install torch")
            return {}

        if date is None:
            date = str(date_type.today())

        from ml_quant_finance_research.ml_research.stock_ml_lab.utils.evaluator import (
            walk_forward_splits,
        )

        summary = {}

        for ticker in tickers:
            logger.info(f"[LSTM] Training {ticker}…")
            X, y, dates = _load_feature_sequences(ticker)

            if X.size == 0 or len(X) < MIN_ROWS:
                logger.warning(f"[LSTM] {ticker}: insufficient data ({len(X)} samples) — skipped")
                continue

            n_features = X.shape[2]
            splits = list(walk_forward_splits(
                pd.DataFrame(index=range(len(X))),
                train_years=2, val_months=6, step_months=6,
            ))

            if not splits:
                logger.warning(f"[LSTM] {ticker}: no walk-forward splits — skipped")
                continue

            fold_aucs = []
            best_model = None
            best_auc   = 0.0

            for train_idx, val_idx in splits:
                import torch
                model = _build_lstm(n_features)
                model, fold_auc, _ = _train_fold(
                    model,
                    X[train_idx], y[train_idx],
                    X[val_idx],   y[val_idx],
                )
                fold_aucs.append(fold_auc)
                if fold_auc > best_auc:
                    best_auc   = fold_auc
                    best_model = model
                logger.debug(f"[LSTM] {ticker} fold AUC={fold_auc:.4f}")

            avg_auc = float(np.mean(fold_aucs))
            logger.info(f"[LSTM] {ticker}: avg_auc={avg_auc:.4f} over {len(splits)} folds")

            if best_model is not None:
                self._save_model(best_model, ticker)
                self._meta[ticker] = {
                    'auc':        round(avg_auc, 4),
                    'n_folds':    len(splits),
                    'n_features': n_features,
                    'trained_at': datetime.now().isoformat(timespec='seconds'),
                }
                self._save_meta()

            summary[ticker] = {'auc': round(avg_auc, 4), 'n_folds': len(splits)}

        logger.info(
            f"[LSTM] Training complete for {date}. "
            f"{sum(1 for v in summary.values() if v['auc'] >= AUC_GATE)} / {len(summary)} "
            f"tickers above AUC gate ({AUC_GATE})"
        )
        return summary
