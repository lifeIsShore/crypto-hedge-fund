"""scenario_engine.py — Monte Carlo scenario generator with Student-t fat tails."""
import numpy as np
from scipy.stats import t as student_t

def generate_scenarios(current_price, up_probability, realized_vol_ann,
                       horizon_days=21, n_simulations=2000, df_t=5.0, seed=42):
    daily_vol   = realized_vol_ann / np.sqrt(252)
    drift_bias  = (up_probability - 0.5) * 0.3 * daily_vol
    std_normals = student_t.rvs(df=df_t, size=(n_simulations, horizon_days), random_state=seed)
    daily_returns = drift_bias + daily_vol * std_normals
    final_returns = np.cumprod(1 + daily_returns, axis=1)[:, -1] - 1
    p5, p25, p50, p75, p95 = [float(np.percentile(final_returns, p)) for p in [5,25,50,75,95]]
    return {
        "bull": {
            "label": "Bull", "return_range": [round(p75,4), round(p95,4)],
            "price_range": [round(current_price*(1+p75),2), round(current_price*(1+p95),2)],
            "probability": round(float(np.mean(final_returns > p75)), 3),
            "conditions": ["Earnings beat consensus","Macro tailwinds","Sector inflow","Signal >60%"],
            "suggested_action": "Enter / Add",
            "invalidation": f"Below {round(current_price*0.95,2)}",
        },
        "base": {
            "label": "Base", "return_range": [round(p25,4), round(p75,4)],
            "price_range": [round(current_price*(1+p25),2), round(current_price*(1+p75),2)],
            "probability": round(float(np.mean((final_returns>=p25)&(final_returns<=p75))), 3),
            "conditions": ["In-line earnings","Stable macro","No catalyst"],
            "suggested_action": "Hold / Wait",
            "invalidation": "Break above bull or below bear",
        },
        "bear": {
            "label": "Bear", "return_range": [round(p5,4), round(p25,4)],
            "price_range": [round(current_price*(1+p5),2), round(current_price*(1+p25),2)],
            "probability": round(float(np.mean(final_returns < p25)), 3),
            "conditions": ["Earnings miss","Macro headwinds","Risk-off regime","Signal <40%"],
            "suggested_action": "Avoid / Exit",
            "invalidation": f"Above {round(current_price*1.03,2)} for 5 days",
        },
        "metadata": {
            "current_price": current_price, "up_probability": up_probability,
            "horizon_days": horizon_days, "n_simulations": n_simulations,
            "realized_vol_ann": realized_vol_ann,
            "percentiles": {
                "p5":round(p5,4),"p25":round(p25,4),"p50":round(p50,4),
                "p75":round(p75,4),"p95":round(p95,4)
            },
        }
    }

def ensemble_sentiment(model_signals):
    if not model_signals:
        return {"score": None, "verdict": "NO DATA", "n_tickers": 0}
    scores  = [s.get("up_proba_21d", 0.5) for s in model_signals.values()]
    weights = [max(0.01, s.get("auc", 0.5) - 0.5) for s in model_signals.values()]
    w = np.array(weights) / sum(weights)
    ws = float(np.average(scores, weights=w))
    return {
        "weighted_score": round(ws, 4),
        "median_score":   round(float(np.median(scores)), 4),
        "verdict": "BROADLY BULLISH" if ws > 0.60 else "BROADLY BEARISH" if ws < 0.40 else "MIXED",
        "n_tickers": len(model_signals),
        "spread_25_75": round(float(np.percentile(scores,75) - np.percentile(scores,25)), 4),
    }
