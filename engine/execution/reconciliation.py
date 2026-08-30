import os
import json
import logging
from datetime import datetime
from engine.db.db import get_session
from sqlalchemy import text
from engine.execution.broker import broker
from engine.alerting.digest import send_alert
from shared.state_paths import STATE_DIR

logger = logging.getLogger(__name__)

import os
RECON_STATE_PATH = os.path.join(STATE_DIR, "reconciliation.json")
DUST_THRESHOLD_EUR = 1.00  # Discrepancies smaller than 1 EUR are ignored as dust

def _get_latest_price_eur(asset: str) -> float:
    """Fetch the latest price for an asset (e.g. 'BTC') to compute EUR equivalent."""
    if asset in ('EUR', 'USDT'):
        return 1.0 if asset == 'EUR' else 0.92  # Approx fallback for stable/fiat
    session = get_session()
    try:
        # We try to find a ticker that starts with the asset e.g., BTC/EUR or BTC/USDT
        row = session.execute(
            text("SELECT adj_close, ticker FROM prices WHERE ticker LIKE :a ORDER BY date DESC LIMIT 1"),
            {'a': f"{asset}/%"}
        ).fetchone()
        
        if not row:
            return 0.0
            
        price, ticker = row
        price = float(price)
        
        # If the quote is USDT, convert to EUR
        if ticker.endswith('USDT') or ticker.endswith('USD'):
            usd_eur_row = session.execute(
                text("SELECT rate FROM fx_rates WHERE pair = 'USDEUR' ORDER BY date DESC LIMIT 1")
            ).fetchone()
            usd_eur = float(usd_eur_row[0]) if usd_eur_row else 0.92
            return price * usd_eur
            
        return price
    finally:
        session.close()


def run_reconciliation():
    """
    Compares internal tax_lots balance against live Binance balance.
    Alerts on discrepancies > DUST_THRESHOLD_EUR.
    """
    logger.info("Starting Daily Reconciliation Check...")
    
    # 1. Handle Sandbox Mode
    if broker.sandbox_mode:
        logger.info("[reconciliation] SANDBOX MODE active. Live balance unavailable.")
        state = {
            "status": "SKIPPED — LIVE BALANCE UNAVAILABLE",
            "timestamp": datetime.now().isoformat(),
            "discrepancies": [],
            "matched": []
        }
        with open(RECON_STATE_PATH, "w") as f:
            json.dump(state, f)
        return

    # 2. Fetch Internal Balance (from Tax Lots)
    internal_balances = {}
    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT asset, SUM(quantity_remaining) as qty 
            FROM tax_lots 
            WHERE quantity_remaining > 0 
            GROUP BY asset
        """)).fetchall()
        for r in rows:
            internal_balances[r[0]] = float(r[1])
    finally:
        session.close()

    # 3. Fetch Live Binance Balance
    if not broker.exchange:
        logger.error("[reconciliation] Broker exchange not initialized.")
        return
        
    try:
        live_balances_raw = broker.exchange.fetch_balance()
    except Exception as e:
        logger.error(f"[reconciliation] Failed to fetch Binance balance: {e}")
        send_alert(f"⚠️ Reconciliation Failed: Could not fetch Binance API balance. {str(e)}")
        return

    live_balances = {}
    for asset, data in live_balances_raw.get('total', {}).items():
        if data > 0:
            live_balances[asset] = float(data)

    # 4. Compare and find discrepancies
    all_assets = set(internal_balances.keys()).union(set(live_balances.keys()))
    
    discrepancies = []
    matched = []
    has_alertable_discrepancy = False
    
    for asset in all_assets:
        internal_qty = internal_balances.get(asset, 0.0)
        live_qty = live_balances.get(asset, 0.0)
        
        delta_qty = abs(live_qty - internal_qty)
        
        if delta_qty == 0:
            matched.append({"asset": asset, "qty": internal_qty, "delta_eur": 0.0})
            continue
            
        price_eur = _get_latest_price_eur(asset)
        delta_eur = delta_qty * price_eur
        
        if delta_eur > DUST_THRESHOLD_EUR:
            has_alertable_discrepancy = True
            discrepancies.append({
                "asset": asset,
                "internal_qty": internal_qty,
                "live_qty": live_qty,
                "delta_qty": delta_qty,
                "delta_eur": delta_eur,
                "price_eur": price_eur
            })
            logger.error(f"[reconciliation] MISMATCH on {asset}: Internal={internal_qty}, Live={live_qty}, Delta=€{delta_eur:.2f}")
        else:
            # Treated as matched (dust)
            matched.append({
                "asset": asset, 
                "qty": internal_qty, 
                "delta_eur": delta_eur,
                "note": "within dust tolerance"
            })

    # 5. Alerting
    if has_alertable_discrepancy:
        status_text = "FAILED — DISCREPANCIES DETECTED"
        alert_msg = "🚨 *Daily Reconciliation FAILED*\n"
        alert_msg += "Significant discrepancies found between Internal DB and Binance API:\n"
        for d in discrepancies:
            alert_msg += f"- {d['asset']}: DB={d['internal_qty']:.6f} | API={d['live_qty']:.6f} (Delta: €{d['delta_eur']:.2f})\n"
        alert_msg += "\nPlease check missed trades or manual exchange interventions."
        send_alert(alert_msg)
    else:
        status_text = "PASSED — FULLY MATCHED"
        logger.info("[reconciliation] PASSED: All balances match within dust tolerance.")

    # 6. Save State
    state = {
        "status": status_text,
        "timestamp": datetime.now().isoformat(),
        "discrepancies": discrepancies,
        "matched": matched,
        "dust_threshold_eur": DUST_THRESHOLD_EUR
    }
    
    try:
        with open(RECON_STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error(f"Failed to save reconciliation state: {e}")

if __name__ == "__main__":
    run_reconciliation()
