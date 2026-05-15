# Trade Republic Quantitative Engine
## Project Master Documentation Map

**Project Status:** Live in Production (V2.0 - Unified Flask/SQLite Architecture)  
**Last Updated:** May 2026  
**Current Capital:** Scaled Production Phase  
**Core Stack:** Python, SQLite, Flask, Black-Litterman, XGBoost/LSTM Integration

---

## 📋 Documentation Map & Alignment

This is your **single source of truth** for understanding the core portfolio management logic.

### Hierarchy & Reading Order

```
START HERE: README.md (you are here)
    ↓
UNDERSTAND: docs/00-SYSTEM-OVERVIEW.md (what the system does)
    ↓
DESIGN: docs/01-ARCHITECTURE.md (how it's structured)
    ↓
LOGIC: docs/02-STRATEGY-RULES.md (the exact rules & math)
    ↓
TRACK: docs/03-TUNING-LOG.md (maintenance diary)
```

---

## 📁 Directory Structure (Unified V2.0)

```
portfolio/
│
├── README.md (THIS FILE)
│
├── docs/                      # Complete system documentation
│   ├── 00-SYSTEM-OVERVIEW.md         # 1-page summary
│   ├── 01-ARCHITECTURE.md             # Data flow & schemas
│   ├── 02-STRATEGY-RULES.md           # Optimization math & constraints
│   ├── 03-TUNING-LOG.md               # Audit trail of parameter changes
│   └── REFERENCE-FORMULAS.md          # Math implementation guide
│
├── src/                       # Core engine source code
│   ├── __init__.py
│   ├── config.py              # SINGLE SOURCE OF TRUTH (Asset Universe & Mappings)
│   ├── data_loader.py         # Multi-tier ingestion (yfinance/TwelveData/etc)
│   ├── math_optimizer.py      # Black-Litterman & MPT engine
│   ├── rules_engine.py        # Drift thresholds & TR fee capping
│   └── performance.py         # Sharpe, Calmar, Sortino, VaR calculations
│
├── data/                      # Input & persistence layer
│   ├── ledger.csv             # Manual transaction log (EUR)
│   ├── historical_prices.csv  # Price cache
│   └── engine_state.json      # Last valid optimizer state
│
├── reports/                   # Automated output artifacts
│   ├── efficient_frontier.csv
│   └── monthly_summary.txt
│
├── flask_app.py               # Production Flask Dashboard (at project root)
├── templates/                 # UI Views (Analytics, Risk, Rebalance)
├── requirements.txt           # Python dependencies
└── RUN_FUND_TOTAL.bat         # Master pipeline launcher
```

---

## 📚 Each Document's Purpose

### `docs/00-SYSTEM-OVERVIEW.md`
**What it answers:** What does this system do? How do I use it? What are the constraints?

**Contains:**
- Executive summary (1-page overview)
- Your workflow (Friday evening → trades → ledger update)
- Trade Republic constraints & workarounds
- High-level architecture diagram

**For whom:** Anyone new to the project. Start here.

---

### `docs/01-ARCHITECTURE.md`
**What it answers:** How is the system built? What are the components and their responsibilities?

**Contains:**
- Complete directory tree with explanations
- Data flow diagram (initialization → optimization → signals → UI)
- Component responsibilities (config.py, data_loader.py, math_optimizer.py, rules_engine.py, app.py)
- Database schema (ledger.csv columns, engine_state.json structure)

**For whom:** Developers and technical architects. Read after OVERVIEW.

---

### `docs/02-STRATEGY-RULES.md`
**What it answers:** What are the exact mathematical rules, constraints, and decision logic?

**Contains:**
- Objective function (Maximize Sharpe Ratio)
- Asset universe (6 tickers with `.DE` suffixes)
- Mathematical parameters (2-year lookback, 2% risk-free rate, log returns)
- Hard constraints (25% max weight, 200-day MA trend filter)
- Rebalancing rules (1st & 3rd Friday, 5% drift threshold, €25 minimum trade)
- UI/UX design guidelines (Ligne Claire aesthetic)

**For whom:** Developers implementing the rules logic. Reference while coding `rules_engine.py` and `config.py`.

---

### `docs/03-TUNING-LOG.md`
**What it answers:** What changes have been made? Why? When?

**Contains:**
- Template for documenting every parameter change
- Change history with date, what changed, old/new values, and rationale
- Current status (V1.0 live on 2026-03-25)

**For whom:** Project maintainers. Add an entry every time you modify `config.py` or `rules_engine.py`.

---

### `docs/REFERENCE-FORMULAS.md`
**What it answers:** What are all the mathematical formulas I need?

**Contains:**
- Quick reference table: formula, definition, Python implementation
- Log returns, volatility, correlation, beta, Sharpe, Calmar, Information Ratio, etc.

**For whom:** Developers implementing `math_optimizer.py` and `performance.py`.

---

## 🚀 Implementation Roadmap (Status: COMPLETE)

### Phase 1: Core Data Pipeline
**Status:** ✅ **COMPLETE**
- [x] Unified `src/config.py` as the single source of truth for 130+ tickers.
- [x] Implemented Xetra/Frankfurt mapping for Trade Republic alignment.

### Phase 2: Statistical Foundation
**Status:** ✅ **COMPLETE**
- [x] High-density correlation matrices and rolling volatility implemented.
- [x] Risk Engine integration (VaR/CVaR).

### Phase 3: Optimization Engine
**Status:** ✅ **COMPLETE**
- [x] **Black-Litterman** framework successfully replaces basic MPT.
- [x] Bayesian confidence scaling based on ML Information Coefficient (IC).

### Phase 4: Trading Rules
**Status:** ✅ **COMPLETE**
- [x] Asymmetric drift thresholds (-5% buy / +7% sell) implemented.
- [x] Minimum trade size logic to cap fee drag at 0.5%.

### Phase 5: Flask Dashboard
**Status:** ✅ **COMPLETE**
- [x] Institutional dark-mode UI with high-performance JS charts.
- [x] Real-time ledger reconstruction for live position tracking.

### Phase 6: Multi-Strategy Integration
**Status:** ✅ **COMPLETE**
- [x] Unified ML Research, PEAD, Regime, and Pairs Trading into a single command center.

---

## 🎯 Control Flow

Everything flows in one direction to ensure consistency:

```
STRATEGY-RULES.md (frozen rules)
    ↓
config.py (CENTRAL TICKER CONFIG)
    ↓
math_optimizer.py + rules_engine.py (mathematical implementation)
    ↓
flask_app.py (live visualization)
    ↓
TUNING-LOG.md (audit trail)
```

**This prevents:**
- Emotional tweaking of weights.
- Ticker discrepancies across sub-modules.
- Inconsistent fee calculations.

---

## 📋 Quick Reference: Which File When?

| Question | Answer File |
|----------|-------------|
| What is the current asset universe? | `src/config.py` |
| How do I add a new ticker? | Append to `ASSET_UNIVERSE` in `src/config.py` |
| What is the current target allocation? | `data/engine_state.json` or Rebalance Dashboard |
| How do I record a new trade? | Append to `data/ledger.csv` |
| Where is the Sharpe formula? | `docs/REFERENCE-FORMULAS.md` |

---

> **The portfolio engine is fully operational. Any modifications to the optimization math or universe constraints MUST be recorded in `docs/03-TUNING-LOG.md` to maintain institutional discipline.**
