# engine/reconciliation/ledger_importer.py
"""
Stream 8 — Portfolio Ledger Replay

Reads portfolio/data/ledger.csv and replays every transaction to reconstruct:
  - Current holdings (quantity per ticker)
  - Exact cash balance (deposits - buys + sells + dividends - fees)

Then syncs the result into the engine's SQLite tables:
  - positions_history  (one row per ticker, today's date)
  - cash_history       (one row with current cash)

This ensures the portfolio optimizer always works from real-world positions,
not theoretical ones. Run once at the start of each pipeline day (before
portfolio construction).

Public API:
    run_ledger_import()           ← called from scheduler before step_portfolio_construction
    get_current_holdings()        ← returns (holdings_df, cash_eur) without writing to DB
    print_trade_advisor(date)     ← prints BUY/HOLD/SELL vs model targets
"""

import os
import logging
import pandas as pd
import datetime

logger = logging.getLogger(__name__)

# FX Logic (mirrors ingestion.py)
EUR_SUFFIXES = ('.DE', '.AS', '.PA', '.SG')
GBP_SUFFIXES = ('.L',)
FALLBACK_USDEUR = 0.92
FALLBACK_GBPEUR = 1.17

def _get_fx_rate(pair: str) -> float:
    """
    H3 fix: Get FX rate from DB (most recent), falling back to env var, then hardcoded constant.
    pair: 'USDEUR' or 'GBPEUR'
    """
    HARDCODED = {"USDEUR": FALLBACK_USDEUR, "GBPEUR": FALLBACK_GBPEUR}

    # 1. Try DB (fx_rates table, populated daily by ingestion)
    try:
        from engine.db.db import get_session
        from sqlalchemy import text
        session = get_session()
        try:
            row = session.execute(text(
                "SELECT rate FROM fx_rates WHERE pair = :p ORDER BY date DESC LIMIT 1"
            ), {"p": pair}).fetchone()
            if row and row[0]:
                return float(row[0])
        finally:
            session.close()
    except Exception:
        pass

    # 2. Try env var
    env_key = f"FALLBACK_{pair}"
    env_val = os.getenv(env_key)
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass

    # 3. Hardcoded last resort
    logger.warning(f"Using hardcoded FX fallback for {pair}: {HARDCODED[pair]}")
    return HARDCODED.get(pair, 1.0)

def _apply_fx_if_needed(ticker: str, price: float) -> float:
    """Converts price to EUR if ticker is non-EUR (US/UK). H3 fix: DB-first, no more live yfinance call per import."""
    if any(ticker.endswith(s) for s in EUR_SUFFIXES):
        return price

    if any(ticker.endswith(s) for s in GBP_SUFFIXES):
        rate = _get_fx_rate("GBPEUR")
    else:
        rate = _get_fx_rate("USDEUR")

    return price * rate

# Path to ledger.csv relative to project root
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
LEDGER_PATH = os.path.join(_ROOT, 'portfolio', 'data', 'ledger.csv')

def replay_ledger(filepath: str = None) -> tuple:
    """
    Replays every ledger transaction in chronological order.

    Returns:
        holdings: dict  {ticker: quantity}   — current live positions
        cash_eur: float                       — current uninvested cash (€)

    Transaction logic:
        Deposit   → cash += total
        Dividend  → cash += total
        Fee       → cash -= total
        Buy       → cash -= total, holdings[ticker] += quantity
        Sell      → cash += total, holdings[ticker] -= quantity
    """
    path = filepath or LEDGER_PATH

    if not os.path.exists(path):
        logger.error(f"[ledger] Ledger file not found: {path}")
        return {}, 0.0

    try:
        df = pd.read_csv(path, comment='#')
        df.columns = [c.strip().lower() for c in df.columns]
    except Exception as e:
        logger.error(f"[ledger] Failed to read ledger: {e}")
        return {}, 0.0

    required_cols = {'date', 'action', 'ticker', 'quantity', 'price', 'total'}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error(f"[ledger] Missing columns: {missing}")
        return {}, 0.0

    holdings = {}
    cash_eur  = 0.0
    errors    = 0

    for i, row in df.iterrows():
        action = str(row.get('action', '')).strip().title()
        ticker = str(row.get('ticker', '')).strip().upper()
        qty    = _safe_float(row.get('quantity'), 0.0)
        total  = _safe_float(row.get('total'), 0.0)

        try:
            if action == 'Deposit':
                cash_eur += total

            elif action == 'Dividend':
                cash_eur += total

            elif action == 'Fee':
                cash_eur -= total

            elif action == 'Buy':
                cash_eur -= total
                holdings[ticker] = holdings.get(ticker, 0.0) + qty

            elif action == 'Sell':
                cash_eur += total
                current_qty = holdings.get(ticker, 0.0)
                new_qty = current_qty - qty
                if new_qty < -0.0001:
                    logger.warning(
                        f"[ledger] Row {i}: SELL {qty} {ticker} but only {current_qty:.4f} held — "
                        "setting to 0 (check ledger)"
                    )
                    new_qty = 0.0
                holdings[ticker] = new_qty
                if holdings[ticker] < 0.0001:
                    del holdings[ticker]

            elif action in ('', 'Nan', 'None'):
                continue  # skip blank rows

            else:
                logger.warning(f"[ledger] Row {i}: Unknown action '{action}' — skipped")

        except Exception as e:
            logger.error(f"[ledger] Row {i} processing error: {e}")
            errors += 1

    if errors:
        logger.warning(f"[ledger] {errors} rows had errors — check ledger.csv")

    logger.info(
        f"[ledger] Replay complete: {len(holdings)} positions, "
        f"cash=€{cash_eur:.2f}"
    )
    return holdings, cash_eur


def _safe_float(val, default=0.0) -> float:
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# PRICE LOOKUP
# ─────────────────────────────────────────────────────────────────────────────

def _get_latest_prices(tickers: list) -> dict:
    """
    Fetches the latest EUR price for each ticker from the prices table.
    Falls back to the ledger's last Buy price if DB has no data.
    Returns {ticker: price_eur}.
    """
    if not tickers:
        return {}

    try:
        from engine.db.db import get_session
        from sqlalchemy import text

        session = get_session()
        placeholders = ','.join([f':t{i}' for i in range(len(tickers))])
        params = {f't{i}': t for i, t in enumerate(tickers)}

        result = session.execute(text(f"""
            SELECT p.ticker, p.adj_close
            FROM prices p
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date
                FROM prices WHERE ticker IN ({placeholders})
                GROUP BY ticker
            ) latest ON p.ticker = latest.ticker AND p.date = latest.max_date
        """), params)
        rows = result.fetchall()
        session.close()
        return {r[0]: float(r[1]) for r in rows if r[1] is not None}
    except Exception as e:
        logger.warning(f"[ledger] Price lookup failed: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# DB SYNC
# ─────────────────────────────────────────────────────────────────────────────

def _sync_to_db(holdings: dict, cash_eur: float, date: str, prices: dict):
    """
    Writes holdings and cash into positions_history and cash_history.
    Uses upsert pattern: inserts a new row for today's date. If the
    pipeline runs twice in one day the second run just adds another row
    (the reconciler reads MAX(date) so this is safe).
    """
    if not holdings and cash_eur == 0:
        logger.warning("[ledger] Nothing to sync — empty holdings and zero cash")
        return

    from engine.db.db import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        # Compute total portfolio value for weight calculation
        total_value = sum(
            holdings.get(t, 0) * prices.get(t, 0) for t in holdings
        ) + max(cash_eur, 0)

        # --- SYNC: We append the ledger reconstruction as the latest state ---
        # The reconciler reads MAX(date) and the dashboard reads latest ID, 
        # so appending is safer than deleting existing audit trails.
        
        count = 0
        for ticker, qty in holdings.items():
            price = prices.get(ticker, 0.0)
            value = qty * price
            weight = value / total_value if total_value > 0 else 0.0

            session.execute(text("""
                INSERT INTO positions_history
                    (date, ticker, quantity, price, value_eur, weight, recorded_at)
                VALUES
                    (:date, :ticker, :qty, :price, :value, :weight, datetime('now'))
            """), {
                'date':   date,
                'ticker': ticker,
                'qty':    round(qty, 6),
                'price':  round(price, 4),
                'value':  round(value, 2),
                'weight': round(weight, 6),
            })
            count += 1

        session.execute(text("""
            INSERT INTO cash_history (date, cash_eur, event_type, notes, recorded_at)
            VALUES (:date, :cash, 'ledger_import', 'Replayed from ledger.csv', datetime('now'))
        """), {'date': date, 'cash': round(cash_eur, 2)})

        session.commit()
        logger.info(
            f"[ledger] Synced {count} positions + cash=€{cash_eur:.2f} "
            f"(total portfolio ≈ €{total_value:.2f}) for {date}"
        )
    except Exception as e:
        session.rollback()
        logger.error(f"[ledger] DB sync failed: {e}")
        raise
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────────────────────
# TRADE ADVISOR
# ─────────────────────────────────────────────────────────────────────────────

def build_trade_advisor(
    holdings: dict,
    cash_eur: float,
    prices: dict,
) -> pd.DataFrame:
    """
    Compares current holdings (from ledger replay) against model_outputs
    (suggested weights from BL optimizer) and generates trade advice.

    Returns a DataFrame with columns:
        ticker | qty_held | price_eur | value_eur | current_weight_pct
        | model_weight_pct | delta_weight_pct | action | shares_to_trade | trade_value_eur

    This is the "Trade Advisor" from Stream 8.2.
    """
    try:
        from engine.db.db import get_session
        from sqlalchemy import text

        session = get_session()
        model_rows = session.execute(text("""
            SELECT ticker, suggested_weight
            FROM model_outputs
            WHERE date = (SELECT MAX(date) FROM model_outputs)
        """)).fetchall()
        session.close()

        model_weights = {r[0]: float(r[1]) for r in model_rows}
    except Exception as e:
        logger.warning(f"[ledger] Could not load model_outputs: {e}")
        model_weights = {}

    # Total portfolio value (positions + cash)
    total_value = sum(
        holdings.get(t, 0) * prices.get(t, 0) for t in holdings
    ) + max(cash_eur, 0)

    if total_value < 1:
        logger.warning("[ledger] Portfolio value too low for trade advisor")
        return pd.DataFrame()

    rows = []
    all_tickers = set(list(holdings.keys()) + list(model_weights.keys()))

    for ticker in sorted(all_tickers):
        qty    = holdings.get(ticker, 0.0)
        price  = prices.get(ticker, 0.0)
        value  = qty * price
        cur_w  = value / total_value
        tgt_w  = model_weights.get(ticker, 0.0)
        delta_w = tgt_w - cur_w
        delta_val = delta_w * total_value

        if abs(delta_val) < 5:      # €5 threshold — below Trade Republic min
            action = 'HOLD'
        elif delta_val > 0:
            action = 'BUY'
        else:
            action = 'SELL'

        shares_to_trade = delta_val / price if price > 0 else 0

        rows.append({
            'ticker':             ticker,
            'qty_held':           round(qty, 4),
            'price_eur':          round(price, 2),
            'value_eur':          round(value, 2),
            'current_weight_pct': round(cur_w * 100, 2),
            'model_weight_pct':   round(tgt_w * 100, 2),
            'delta_weight_pct':   round(delta_w * 100, 2),
            'action':             action,
            'shares_to_trade':    round(shares_to_trade, 4),
            'trade_value_eur':    round(delta_val, 2),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values('trade_value_eur', key=abs, ascending=False)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_current_holdings(filepath: str = None) -> tuple:
    """
    Returns (holdings_dict, cash_eur) without writing to DB.
    Useful for the dashboard to display live holdings without triggering a sync.
    """
    return replay_ledger(filepath)


def run_ledger_import(date: str = None, filepath: str = None) -> dict:
    """
    Full ledger import pipeline. Called from scheduler before portfolio construction.

    1. Replay ledger → current holdings + cash
    2. Fetch latest EUR prices from DB
    3. Sync holdings to positions_history + cash_history
    4. Build and return trade advisor DataFrame

    Returns dict with keys: holdings, cash_eur, prices, trade_advisor_df
    """
    if date is None:
        date = str(datetime.date.today())

    holdings, cash_eur = replay_ledger(filepath)

    if not holdings and cash_eur == 0:
        logger.error("[ledger] Ledger replay produced no data — aborting import")
        return {}

    prices = _get_latest_prices(list(holdings.keys()))

    # For any ticker not yet in the DB prices table, try to fetch live price
    missing = [t for t in holdings if t not in prices or prices[t] == 0]
    if missing:
        logger.info(f"[ledger] Fetching live prices for {len(missing)} tickers not yet in DB")
        try:
            import yfinance as yf
            raw = yf.download(missing, period='5d', auto_adjust=True, progress=False)
            if not raw.empty:
                close = raw['Close'] if len(missing) > 1 else raw[['Close']]
                for t in missing:
                    col = t if t in close.columns else None
                    if col:
                        val = close[col].dropna().iloc[-1] if not close[col].dropna().empty else 0
                        # --- APPLY FX CONVERSION HERE ---
                        prices[t] = _apply_fx_if_needed(t, float(val))
        except Exception as e:
            logger.warning(f"[ledger] Live price fetch failed: {e}")

    _sync_to_db(holdings, cash_eur, date, prices)

    advisor_df = build_trade_advisor(holdings, cash_eur, prices)

    if not advisor_df.empty:
        logger.info("\n[ledger] Trade Advisor Summary:")
        for _, r in advisor_df[advisor_df['action'] != 'HOLD'].iterrows():
            logger.info(
                f"  {r['action']:4s} {r['ticker']:12s} "
                f"{r['shares_to_trade']:+.4f} shares  "
                f"€{r['trade_value_eur']:+.2f}  "
                f"(currently {r['current_weight_pct']:.1f}% → target {r['model_weight_pct']:.1f}%)"
            )

    return {
        'holdings':        holdings,
        'cash_eur':        cash_eur,
        'prices':          prices,
        'trade_advisor_df': advisor_df,
    }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    result = run_ledger_import()
    if result:
        print(f"\nHoldings: {result['holdings']}")
        print(f"Cash: €{result['cash_eur']:.2f}")
        if not result['trade_advisor_df'].empty:
            print("\nTrade Advisor:")
            print(result['trade_advisor_df'].to_string(index=False))
