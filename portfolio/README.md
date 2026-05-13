# Trade Republic Quantitative Engine
## Project Master Documentation Map

**Project Status:** Live in Production (V2.0 - Unified Flask/SQLite Architecture)  
**Last Updated:** May 2026  
**Current Capital:** Scaled Production Phase  
**Core Stack:** Python, SQLite, Flask, Black-Litterman, XGBoost/LSTM Integration

---

## 📋 Documentation Map & Alignment

This is your **single source of truth** for understanding how all project documents align. Each document serves a specific role in the complete system.

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
    ↓
BUILD: Start Phase 1 implementation (see section "Implementation Roadmap" below)
```

---

## 📁 Directory Structure

```
portfolio/
│
├── README.md (THIS FILE)
│
├── docs/                      # Complete system documentation
│   ├── 00-SYSTEM-OVERVIEW.md         # What does this do? (START HERE)
│   ├── 01-ARCHITECTURE.md             # How is it built?
│   ├── 02-STRATEGY-RULES.md           # What are the exact rules?
│   ├── 03-TUNING-LOG.md               # Change history & maintenance
│   └── REFERENCE-FORMULAS.md          # Quick math reference
│
├── src/                       # Python source code (empty until Phase 1)
│   ├── __init__.py
│   ├── config.py              # Hard-coded constants: tickers, fees, rates
│   ├── data_loader.py         # Reads ledger.csv, fetches yfinance
│   ├── math_optimizer.py      # MPT engine, correlation, volatility
│   ├── rules_engine.py        # Applies constraints: 5% drift, €25 min trade
│   ├── performance.py         # KPI calculations: Sharpe, Calmar, etc.
│   └── app.py                 # Streamlit dashboard
│
├── data/                      # Your input ledger & cached data
│   ├── ledger.csv             # YOUR INPUT: manual transaction log
│   ├── historical_prices.csv  # CACHE: yfinance data (auto-updated)
│   └── engine_state.json      # CACHE: last optimizer output
│
├── notebooks/                 # Exploratory analysis & testing
│   ├── 01_data_exploration.ipynb
│   ├── 02_correlation_testing.ipynb
│   └── 03_backtest_simulation.ipynb
│
├── reports/                   # Generated outputs (auto-created)
│   ├── efficient_frontier.csv
│   └── monthly_summary.txt
│
├── requirements.txt           # Python dependencies
├── run_engine.bat/.sh         # One-click launcher
└── .gitignore                 # Git exclusions
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

## 🔄 How Documents Relate

### Layer 1: Vision (00-SYSTEM-OVERVIEW.md)
- Answers: *"What are we building and why?"*
- Audience: Everyone

### Layer 2: Design (01-ARCHITECTURE.md + Directory Structure)
- Answers: *"How do we organize the code and data?"*
- Audience: Developers and architects
- References: 00 (for context), 02 (for rules)

### Layer 3: Rules (02-STRATEGY-RULES.md)
- Answers: *"What are the exact rules and constraints?"*
- Audience: Developers coding the logic
- References: 00 (for context)

### Layer 4: Implementation (src/ code)
- Implements the rules from Layer 3
- Follows the structure from Layer 2
- Reports KPIs defined in Layer 3

### Layer 5: Maintenance (03-TUNING-LOG.md)
- Records every change to Layer 3 and Layer 4
- Creates audit trail
- Prevents emotional tweaking

### Debug Layer (REFERENCE-FORMULAS.md)
- Available at all times for quick lookup
- Ensures consistency in mathematical implementation

---

## ✅ Alignment Verification

### What's Green (Aligned)

✅ **ARCHITECTURE.md** aligns perfectly with **Directory-Structure.md**
- Both define: src/, data/, docs/ folders
- Both explain: data flow, component responsibilities, data schemas

✅ **STRATEGY-RULES.md** aligns perfectly with **TUNING-LOG.md**
- STRATEGY-RULES defines the rules (what should never change without reason)
- TUNING-LOG records when/why rules change

✅ **quant-engine-blueprint-FULL.md** aligns with everything
- Provides expanded mathematical detail for all rules
- Cross-references all constraints and objectives

### What Needs Attention

⚠️ **Directory still scattered:**
- ARCHITECTURE.md, Directory-Structure.md, STRATEGY_RULES.md, TUNING_LOG.md all in root
- Should be in `/docs` folder for tidiness

⚠️ **No template files created yet:**
- `/src` exists but is empty (intentional, Phase 1 work)
- `/data/ledger.csv` doesn't exist yet (you'll create it when ready)

⚠️ **No generated files yet:**
- `/reports` and `/notebooks` are empty (will populate during Phase 1-6)

---

## 🚀 Implementation Roadmap (7 Phases)

### Phase 1: Core Data Pipeline (Week 1)
**What:** Get real market data flowing

**Files to create:**
- `src/config.py` — Define tickers, constants
- `src/data_loader.py` — Fetch yfinance, cache to CSV
- `data/ledger.csv` — Create with columns: Date, Action, Ticker, Quantity, Price, Total

**Verification:** Can you fetch 2 years of data for 6 tickers without errors?

---

### Phase 2: Statistical Foundation (Week 2)
**What:** Calculate correlations, volatility, returns

**Files to create:**
- `src/math_optimizer.py` — Log returns, correlation matrix, volatility, beta

**Verification:** Generate correlation heatmap. Compare against Yahoo Finance directly.

---

### Phase 3: Optimization Engine (Week 3)
**What:** Calculate efficient frontier & optimal weights

**Files to create:**
- Extend `src/math_optimizer.py` — Add MPT, scipy.optimize for Sharpe maximization

**Verification:** Generate efficient frontier scatter plot with 1000+ simulated portfolios.

---

### Phase 4: Trading Rules (Week 4)
**What:** Convert math to actionable trade signals

**Files to create:**
- `src/rules_engine.py` — Apply 5% drift, €25 minimum, 200-day MA filter
- `src/performance.py` — Calculate Sharpe, Calmar, Information Ratio

**Verification:** Feed in 5 hypothetical portfolio states; verify correct trade signals.

---

### Phase 5: Flask Dashboard (Week 5)
**What:** Build interactive HTML/JS UI

**Files to create:**
- `flask_app.py` — Flask backend routing
- `templates/` — HTML/CSS/JS frontend views:
  - Dashboard: Command Center, Analytics, Risk
  - Ledger: Transaction entry, holdings table

**Verification:** Dashboard loads without errors. Charts display live data.

---

### Phase 6: Integration & Testing (Week 6)
**What:** Connect all modules end-to-end

**What:** Run one complete weekly cycle: engine → signals → dashboard update

**Verification:** Execute first manual rebalance based on engine output.

---

### Phase 7: Polish & Documentation (Week 7)
**What:** Final polish, warnings, guides

**Files to create:**
- `USER-MANUAL.md` — Step-by-step "How to run the engine weekly"
- `TROUBLESHOOTING.md` — Common errors and fixes
- Add Capital Scaling warning box to dashboard

**Verification:** New user can follow manual and execute their first rebalance without issues.

---

## 📊 Project Status Checklist

### Planning Phase (Current)
- [x] Original ideas brainstormed (`idea.md`)
- [x] Architecture designed (`ARCHITECTURE.md`, `Directory-Structure.md`)
- [x] Strategy rules locked (`STRATEGY_RULES.md`)
- [x] Comprehensive blueprint created (`quant-engine-blueprint-FULL.md`)
- [x] Folder structure created
- [x] Documentation aligned (this file)
- [ ] **NEXT:** Phase 1 implementation

### Development Phase (Next)
- [ ] Phase 1: Data pipeline
- [ ] Phase 2: Statistics engine
- [ ] Phase 3: Optimizer
- [ ] Phase 4: Rules engine
- [ ] Phase 5: Streamlit UI
- [ ] Phase 6: Integration
- [ ] Phase 7: Polish

### Operational Phase (After Development)
- [ ] First €100 test trade
- [ ] 4-week live testing
- [ ] Capital scaling to €1,000
- [ ] Quarterly reviews

---

## 🎯 One Direction: The Control Flow

Everything flows in one direction to ensure consistency:

```
idea.md (raw brainstorm)
    ↓
STRATEGY-RULES.md (frozen rules)
    ↓
config.py (hard-coded constants)
    ↓
math_optimizer.py + rules_engine.py (implementation)
    ↓
app.py (visualization)
    ↓
TUNING-LOG.md (record any changes with rationale)
    ↓
NEVER back to STRATEGY-RULES without documented reason
```

**This prevents:**
- Emotional tweaking
- Inconsistent implementations
- Lost knowledge of why rules exist
- Scope creep

---

## 📋 Quick Reference: Which File When?

| Question | Answer File |
|----------|-------------|
| What does this system do? | `00-SYSTEM-OVERVIEW.md` |
| How is it structured? | `01-ARCHITECTURE.md` |
| What are the rules? | `02-STRATEGY-RULES.md` |
| How do I implement rule X? | `02-STRATEGY-RULES.md` + `REFERENCE-FORMULAS.md` |
| What changed and why? | `03-TUNING-LOG.md` |
| What's the Sharpe formula? | `REFERENCE-FORMULAS.md` |
| How do I use it weekly? | `USER-MANUAL.md` (Phase 7) |
| It's broken, what now? | `TROUBLESHOOTING.md` (Phase 7) |

---

## ✨ Next Steps

1. **Read** `docs/00-SYSTEM-OVERVIEW.md` — Understand the big picture
2. **Read** `docs/01-ARCHITECTURE.md` — See how it's organized
3. **Read** `docs/02-STRATEGY-RULES.md` — Lock in the rules
4. **Start Phase 1** — Create `src/config.py` with the 6 `.DE` tickers
5. **Update** `docs/03-TUNING-LOG.md` anytime you modify a rule

---

> **The system is coherent, aligned, and ready to build. All documentation points in one direction: implement the rules consistently, audit changes, never go off-plan without recording why.**
