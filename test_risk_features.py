import os
import json
import logging
import warnings
# Suppress some standard torch/sklearn warnings for cleaner output
warnings.filterwarnings("ignore")

from engine.alpha.lstm_model import LSTMAlpha
import engine.alpha.lstm_model as lstm_mod

logging.basicConfig(level=logging.INFO) # Only show our print statements

tickers = [
    '18U.DE', '2H1.DE', '2PY.DE'
]

# Monkey-patch walk_forward_splits to work with small local DBs
import ml_quant_finance_research.ml_research.stock_ml_lab.utils.evaluator as evaluator
orig_wfs = evaluator.walk_forward_splits

def mock_wfs(df, train_years, val_months, step_months):
    # Use 6 months train, 1 month val, jump 10 years to only do 1 fold
    return orig_wfs(df, train_years=0.5, val_months=1, step_months=120)

evaluator.walk_forward_splits = mock_wfs

def run_experiment():
    print("=== Running LSTM Experiment on 10 Tickers ===")
    
    model = LSTMAlpha()
    lstm_mod.MIN_ROWS = 100
    
    print("\n--- BASELINE (No Volatility/Risk Metrics) ---")
    lstm_mod.FEATURE_NAMES = [
        'mom_1m', 'mom_3m', 'mom_6m', 'mom_12m', 'rsi_14'
    ]
    summary_base = model.train_all(tickers)
    
    print("\n--- WITH RISK METRICS (var_21d, vol_21d, vol_63d, vol_of_vol) ---")
    lstm_mod.FEATURE_NAMES = [
        'mom_1m', 'mom_3m', 'mom_6m', 'mom_12m', 'rsi_14',
        'var_21d', 'vol_21d', 'vol_63d', 'vol_of_vol'
    ]
    summary_risk = model.train_all(tickers)
    
    print(f"summary_base: {summary_base}")
    print(f"summary_risk: {summary_risk}")
    
    print("\n=== RESULTS ===")
    base_aucs = []
    risk_aucs = []
    for t in tickers:
        base_auc = summary_base.get(t, {}).get("auc", 0)
        risk_auc = summary_risk.get(t, {}).get("auc", 0)
        if base_auc and risk_auc:
            base_aucs.append(base_auc)
            risk_aucs.append(risk_auc)
            diff = risk_auc - base_auc
            print(f"{t}: Base AUC = {base_auc:.4f}, Risk AUC = {risk_auc:.4f} (Delta: {diff:+.4f})")
            
    if base_aucs:
        avg_base = sum(base_aucs)/len(base_aucs)
        avg_risk = sum(risk_aucs)/len(risk_aucs)
        print(f"\nAverage Base AUC: {avg_base:.4f}")
        print(f"Average Risk AUC: {avg_risk:.4f}")
        print(f"Net Change: {avg_risk - avg_base:+.4f}")
        if avg_risk > avg_base:
            print("CONCLUSION: Adding risk metrics INCREASES model AUC.")
        else:
            print("CONCLUSION: Adding risk metrics DECREASES model AUC.")
            
        print("\nNote: We are currently testing statically with LSTM. A dynamic ensemble that")
        print("includes XGBoost might capture non-linear relationships in var_21d much better.")
            
if __name__ == "__main__":
    try:
        run_experiment()
    except Exception as e:
        import traceback
        traceback.print_exc()
