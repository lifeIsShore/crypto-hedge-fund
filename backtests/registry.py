"""
backtests/registry.py
=====================
Shared helper for the backtest run registry.

Provides:
  - generate_run_id()          → str "YYYYMMDD_HHMMSS"
  - get_run_dir(run_id)        → Path to backtests/runs/<run_id>/
  - list_runs()                → list of dicts from runs_index.csv (newest first)
  - load_run(run_id)           → dict with results_df, metrics, config, ic_results
  - append_index(run_id, ...)  → append a row to runs_index.csv
  - update_note(run_id, note)  → update notes column for a run
  - RUNS_DIR, INDEX_PATH       → Path constants
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger('backtest.registry')

# ── Paths ─────────────────────────────────────────────────────────────────────
BACKTESTS_DIR = Path(__file__).parent
RUNS_DIR      = BACKTESTS_DIR / 'runs'
INDEX_PATH    = RUNS_DIR / 'runs_index.csv'

INDEX_COLUMNS = [
    'run_id', 'timestamp', 'backtest_start', 'backtest_end',
    'n_days', 'n_years',
    'sharpe_port', 'cagr_port', 'mdd_port',
    'sortino_port', 'calmar_port', 'info_ratio', 'alpha_annualised',
    'total_return_port', 'total_return_bench',
    'alphas', 'git_commit', 'notes',
]


# ── Public helpers ────────────────────────────────────────────────────────────

def generate_run_id() -> str:
    """Return a sortable string like '20260820_152600'."""
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def get_run_dir(run_id: str) -> Path:
    """Return (and create if needed) the directory for a given run_id."""
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_runs() -> list:
    """
    Read runs_index.csv and return a list of dicts, newest run first.
    Returns [] if the index doesn't exist yet.
    """
    if not INDEX_PATH.exists():
        return []
    try:
        df = pd.read_csv(INDEX_PATH, dtype=str)
        df = df.fillna('')
        # Newest first
        df = df.iloc[::-1].reset_index(drop=True)
        return df.to_dict(orient='records')
    except Exception as e:
        logger.warning(f"Could not read runs_index.csv: {e}")
        return []


def load_run(run_id: str) -> dict:
    """
    Load all artifacts for a single run.
    Returns a dict with keys:
        run_id, config, meta, metrics, results_df, ic_results_df
    Any missing file returns None for that key.
    """
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return {}

    def _read_json(name):
        p = run_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                return None
        return None

    def _read_csv(name, **kwargs):
        p = run_dir / name
        if p.exists():
            try:
                return pd.read_csv(p, **kwargs)
            except Exception:
                return None
        return None

    results_df  = _read_csv('backtest_results.csv', index_col='date', parse_dates=True)
    ic_df       = _read_csv('alpha_ic_results.csv')

    # metrics: stored as key=value csv (pandas Series.to_csv style)
    metrics_raw = _read_csv('backtest_metrics.csv', header=None, index_col=0)
    metrics = {}
    if metrics_raw is not None:
        # backtest_metrics.csv has columns: metric, value
        for idx, row in metrics_raw.iterrows():
            try:
                metrics[str(idx)] = float(row.iloc[0])
            except (ValueError, TypeError):
                metrics[str(idx)] = row.iloc[0]

    return {
        'run_id':        run_id,
        'config':        _read_json('strategy_config.json'),
        'meta':          _read_json('run_meta.json'),
        'metrics':       metrics,
        'results_df':    results_df,
        'ic_results_df': ic_df,
    }


def append_index(run_id: str, metrics: dict, config: dict, note: str = '') -> None:
    """
    Append one row to runs_index.csv.
    Creates the CSV with headers if it doesn't exist yet.
    Thread-safe for single-process use (backtest is single-process).
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    alphas_str = '+'.join(
        a['name'] for a in config.get('alphas_active', [])
    ) if config else ''

    git_commit = config.get('git_commit', '') if config else ''

    row = {
        'run_id':             run_id,
        'timestamp':          config.get('run_timestamp', '') if config else '',
        'backtest_start':     metrics.get('start_date', ''),
        'backtest_end':       metrics.get('end_date',   ''),
        'n_days':             metrics.get('n_days',     ''),
        'n_years':            metrics.get('n_years',    ''),
        'sharpe_port':        metrics.get('sharpe_port',       ''),
        'cagr_port':          metrics.get('cagr_port',         ''),
        'mdd_port':           metrics.get('mdd_port',          ''),
        'sortino_port':       metrics.get('sortino_port',      ''),
        'calmar_port':        metrics.get('calmar_port',       ''),
        'info_ratio':         metrics.get('info_ratio',        ''),
        'alpha_annualised':   metrics.get('alpha_annualised',  ''),
        'total_return_port':  metrics.get('total_return_port', ''),
        'total_return_bench': metrics.get('total_return_bench',''),
        'alphas':             alphas_str,
        'git_commit':         git_commit,
        'notes':              note,
    }

    row_df = pd.DataFrame([row], columns=INDEX_COLUMNS)

    if INDEX_PATH.exists():
        row_df.to_csv(INDEX_PATH, mode='a', header=False, index=False)
    else:
        row_df.to_csv(INDEX_PATH, mode='w', header=True, index=False)

    logger.info(f"Appended run {run_id} to runs_index.csv")


def update_note(run_id: str, note: str) -> bool:
    """
    Update the 'notes' field for a given run_id in runs_index.csv.
    Returns True on success, False if not found or file missing.
    """
    if not INDEX_PATH.exists():
        return False
    try:
        df = pd.read_csv(INDEX_PATH, dtype=str).fillna('')
        mask = df['run_id'] == run_id
        if not mask.any():
            return False
        df.loc[mask, 'notes'] = note
        df.to_csv(INDEX_PATH, index=False)
        return True
    except Exception as e:
        logger.error(f"update_note failed for {run_id}: {e}")
        return False
