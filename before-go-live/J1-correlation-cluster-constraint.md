# J1 — Correlation Cluster Concentration Limit
# Add to `engine/portfolio/optimizer.py`
# Estimated time: 3 hours. No new dependencies (scipy already installed).

---

## The problem this closes

`optimizer.py` currently enforces `MAX_POSITION` (10% per ticker) and
`MAX_SECTOR_SHARE` (30% per sector, via `build_sector_constraints()`). It has
**no constraint on statistical co-movement**. Four tickers can sit in four
different `TICKER_SECTORS` labels (e.g. "Technology", "Semiconductors",
"Communication", "Consumer Disc") and still be 0.85+ correlated in practice
(NVDA, AMD, QCOM, META during an AI-capex drawdown, for example). Nominal
sector labels do not protect against this — only the actual correlation
matrix does.

This was flagged independently in three of your docs (`improvements.md` Phase 4
item 1, `BRAINSTORM-new-features-and-gaps.md` Gap 6, and
`quant_portfolio_framework-research.md` Part 1) but never implemented — I
checked `optimizer.py` directly, there is no clustering logic anywhere in it.

---

## Design

1. Run **hierarchical clustering** (not k-means — hierarchical is more stable
   on a correlation-distance matrix and doesn't require picking a cluster
   count up front, which matters since your universe grows over time) on
   `1 - abs(correlation)` as the distance metric.
2. Cut the dendrogram at a distance threshold, not a fixed cluster count —
   this keeps cluster membership stable as tickers are added/removed from
   the universe, whereas a fixed `k` reshuffles cluster identity every time
   the universe changes size.
3. Add one inequality constraint per cluster to the existing `constraints`
   list in `optimize_with_bl()`, the same pattern already used for sectors.

---

## Implementation

### Step 1 — New function in `engine/portfolio/optimizer.py`

```python
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

MAX_CLUSTER_SHARE = 0.25   # 25% max per correlation cluster
CLUSTER_DISTANCE_THRESHOLD = 0.35  # cut dendrogram here (lower = more clusters)
MIN_CLUSTER_SIZE_TO_CONSTRAIN = 2  # singleton clusters don't need a constraint


def build_correlation_clusters(tickers: list, cov_matrix: pd.DataFrame) -> dict:
    """
    Groups tickers into correlation clusters using hierarchical clustering
    on the correlation-distance matrix. Returns {ticker: cluster_id}.

    Distance metric: 1 - |correlation|. Two tickers with correlation +0.9
    or -0.9 are both "close" (both would move together in absolute-value
    terms during a risk-off shock — for equities, negative correlation
    at that magnitude is unusual and usually a pairs relationship, which
    you still don't want double-counted as diversification).
    """
    # Convert covariance to correlation
    std = np.sqrt(np.diag(cov_matrix.loc[tickers, tickers]))
    corr = cov_matrix.loc[tickers, tickers].values / np.outer(std, std)
    corr = np.clip(corr, -1.0, 1.0)

    distance = 1 - np.abs(corr)
    np.fill_diagonal(distance, 0)
    condensed = squareform(distance, checks=False)

    if len(tickers) < 3:
        return {t: 0 for t in tickers}

    Z = linkage(condensed, method='average')
    cluster_ids = fcluster(Z, t=CLUSTER_DISTANCE_THRESHOLD, criterion='distance')

    return dict(zip(tickers, cluster_ids))


def build_cluster_constraints(tickers: list, cluster_map: dict, max_cluster: float = MAX_CLUSTER_SHARE) -> list:
    """Generates one inequality constraint per cluster with >= 2 members."""
    clusters = {}
    for i, t in enumerate(tickers):
        cid = cluster_map.get(t)
        if cid is not None:
            clusters.setdefault(cid, []).append(i)

    constraints = []
    for cid, indices in clusters.items():
        if len(indices) < MIN_CLUSTER_SIZE_TO_CONSTRAIN:
            continue
        constraints.append({
            "type": "ineq",
            "fun": lambda w, idx=indices: max_cluster - np.sum(w[idx])
        })
    return constraints
```

### Step 2 — Wire into `optimize_with_bl()`

```python
def optimize_with_bl(
    mu_bl: pd.Series,
    cov_matrix: pd.DataFrame,
    current_weights: pd.Series,
    sector_map: dict = None,
    risk_aversion: float = 2.5,
) -> pd.Series:
    tickers = mu_bl.index.tolist()
    n = len(tickers)

    w0 = np.array([current_weights.get(t, 0.0) for t in tickers])
    mu = mu_bl.values
    Sigma = cov_matrix.loc[tickers, tickers].values

    def objective(w):
        ret       = np.dot(mu, w)
        risk      = 0.5 * risk_aversion * w @ Sigma @ w
        delta_w   = np.abs(w - w0)
        turnover  = TURNOVER_PENALTY * np.sum(delta_w)
        costs     = SLIPPAGE_PCT * np.sum(delta_w)
        return -(ret - risk - turnover - costs)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if sector_map:
        constraints += build_sector_constraints(tickers, sector_map)

    # NEW — correlation cluster constraint
    cluster_map = build_correlation_clusters(tickers, cov_matrix)
    constraints += build_cluster_constraints(tickers, cluster_map)

    bounds = [(0, MAX_POSITION)] * n

    result = minimize(
        objective, x0=w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-9}
    )
    # ... rest unchanged
```

### Step 3 — Persist cluster membership for dashboard visibility

Add a `correlation_clusters` table so you can see *why* the optimizer capped
a position — otherwise a 25% cluster cap is invisible/confusing on the
rebalance page compared to the existing sector cap, which at least maps to
a label you recognize.

```sql
CREATE TABLE IF NOT EXISTS correlation_clusters (
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    cluster_id  INTEGER NOT NULL,
    computed_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (date, ticker)
);
```

Write to it inside `step_portfolio_construction()` in `engine/scheduler.py`,
right after `build_correlation_clusters()` is called — same pattern as how
`signal_breakdown` (I2) is persisted alongside `model_outputs`.

### Step 4 — Surface on `rebalance.html`

Next to the existing "WHY (SIGNAL BREAKDOWN)" column from I2, add a small
badge showing cluster membership when a position was capped by the cluster
constraint rather than the sector or position constraint — e.g. a tooltip:
*"Capped: 3 correlated positions (NVDA, AMD, QCOM) at 25% of portfolio —
correlation cluster limit, not sector limit."*

---

## Tuning notes

- `CLUSTER_DISTANCE_THRESHOLD = 0.35` is a reasonable starting point (roughly
  groups tickers correlated above ~0.65) but **validate it empirically**:
  run `build_correlation_clusters()` against your current 90-ticker universe
  once, print the resulting groups, and sanity-check them against sectors you
  already know are related (semis, mega-cap tech, European autos). Adjust the
  threshold until cluster sizes look reasonable (roughly 2–6 tickers per
  cluster; if you get one giant cluster of 40 tickers, raise the threshold —
  too aggressive; if every ticker is its own cluster, lower it).
- Recompute clusters **every pipeline run**, not just once — correlation
  structure drifts, especially across regime changes. This is cheap (scipy
  hierarchical clustering on a ~90×90 matrix is sub-second).
- Document the chosen threshold and any changes to it in
  `portfolio/docs/03-TUNING-LOG.md`, same convention as `MAX_POSITION`.

## Expected effect

With `MAX_CLUSTER_SHARE = 0.25` and `MAX_POSITION = 0.10`, no correlated
cluster of assets can exceed 25% of the portfolio even if each individual
position and each individual sector label stays within their own limits.
This directly closes the Gap 6 example from `BRAINSTORM-new-features-and-gaps.md`
(NVD.DE + AMD.DE + QCI.DE + TSM.DE at 7% each = 28% correlated exposure that
currently sails through both existing constraints).
