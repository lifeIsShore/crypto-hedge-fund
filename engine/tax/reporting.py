import os
import json
import csv
from datetime import datetime
from engine.db.db import get_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def generate_tax_package(tax_year: int, out_dir: str = 'audit_packages'):
    """
    Generates the German Tax Audit Package for the specified year.
    Includes full ledger, lots, disposals, and a manifest.
    """
    pkg_dir = os.path.join(out_dir, f'tax_package_{tax_year}')
    os.makedirs(pkg_dir, exist_ok=True)
    
    session = get_session()
    
    try:
        # 1. Disposals
        disposals = session.execute(
            text("SELECT * FROM tax_disposals WHERE tax_year = :ty ORDER BY disposal_timestamp ASC"),
            {'ty': tax_year}
        ).fetchall()
        
        disposals_path = os.path.join(pkg_dir, '02_disposals.csv')
        with open(disposals_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Fetch column names
            col_names = session.execute(text("PRAGMA table_info(tax_disposals)")).fetchall()
            headers = [c[1] for c in col_names]
            writer.writerow(headers)
            for row in disposals:
                writer.writerow(row)
                
        # 2. Ledger
        ledger = session.execute(text("SELECT * FROM tax_ledger_entries ORDER BY timestamp_utc ASC")).fetchall()
        ledger_path = os.path.join(pkg_dir, '03_full_ledger.csv')
        with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            col_names = session.execute(text("PRAGMA table_info(tax_ledger_entries)")).fetchall()
            headers = [c[1] for c in col_names]
            writer.writerow(headers)
            for row in ledger:
                writer.writerow(row)
                
        # 3. Lots
        lots = session.execute(text("SELECT * FROM tax_lots ORDER BY acquisition_timestamp ASC")).fetchall()
        lots_path = os.path.join(pkg_dir, '04_lots.csv')
        with open(lots_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            col_names = session.execute(text("PRAGMA table_info(tax_lots)")).fetchall()
            headers = [c[1] for c in col_names]
            writer.writerow(headers)
            for row in lots:
                writer.writerow(row)
                
        # Calculate totals
        total_gains = sum(r.gain_loss_eur for r in disposals if r.gain_loss_eur > 0 and r.tax_category == 'TAXABLE')
        total_losses = sum(r.gain_loss_eur for r in disposals if r.gain_loss_eur < 0 and r.tax_category == 'TAXABLE')
        net_taxable = total_gains + total_losses
        
        tax_free_gains = sum(r.gain_loss_eur for r in disposals if r.gain_loss_eur > 0 and r.tax_category == 'TAX_FREE_LONG_TERM')
        
        manifest = {
            "tax_year": tax_year,
            "exchange": "Binance",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "records": len(ledger),
            "disposals": len(disposals),
            "total_taxable_gains_eur": round(total_gains, 2),
            "total_taxable_losses_eur": round(total_losses, 2),
            "net_taxable_eur": round(net_taxable, 2),
            "tax_free_long_term_gains_eur": round(tax_free_gains, 2)
        }
        
        manifest_path = os.path.join(pkg_dir, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f"Generated tax package for {tax_year} at {pkg_dir}")
        return manifest
        
    finally:
        session.close()
