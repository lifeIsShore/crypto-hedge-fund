import numpy as np

def mc_portfolio(positions, targets_map, n_paths=8000):
    """Run Monte Carlo on portfolio; return (var5_pct, cvar5_pct, var1_pct, total_eur)."""
    total = sum(float(p.get("value_eur") or 0.0) for p in positions)
    if total <= 0:
        return 0, 0, 0, 0
    port_ret = np.zeros(n_paths)
    t = 21 / 252
    rng = np.random.default_rng()  # H2 fix: no fixed seed - genuine MC variation for portfolio VaR/CVaR
    for p in positions:
        ticker = p["ticker"]
        w = float(p.get("weight", 0))
        sig = targets_map.get(ticker, {})
        up_p = float(sig.get("up_proba", 0.5))
        vol  = float(sig.get("vol_ann", 0.25))
        edge = (up_p - 0.5) * 2
        dr   = edge * vol * t
        sr   = vol * np.sqrt(t)
        port_ret += w * rng.normal(dr, sr, n_paths)
    var5  = float(np.percentile(port_ret, 5)  * 100)
    var1  = float(np.percentile(port_ret, 1)  * 100)
    cvar5 = float(np.mean(port_ret[port_ret <= np.percentile(port_ret, 5)]) * 100)
    return round(var5, 2), round(cvar5, 2), round(var1, 2), round(total, 2)
