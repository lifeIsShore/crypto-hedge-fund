"""
Jurisdiction-selectable capital gains tax rates for the tax-aware
selling penalty in optimizer.py. See before-go-live/J2-tax-aware-selling.md.
"""
import logging
from sqlalchemy import text
from engine.db.db import get_session

logger = logging.getLogger(__name__)

# rate=None for 'custom' means "read custom_rate from the DB row instead" —
# there is no fixed preset value for it.
JURISDICTION_PRESETS = {
    'germany':      {'label': 'Germany (Abgeltungsteuer)',      'rate': 0.26375, 'approximate': False},
    'austria':      {'label': 'Austria (KESt)',                  'rate': 0.275,   'approximate': False},
    'france':       {'label': 'France (PFU)',                    'rate': 0.30,    'approximate': False},
    'belgium':      {'label': 'Belgium (private investors)',     'rate': 0.0,     'approximate': False},
    'switzerland':  {'label': 'Switzerland (private investors)', 'rate': 0.0,     'approximate': False},
    'uk':           {'label': 'United Kingdom (CGT)',            'rate': 0.20,    'approximate': True},
    'us':           {'label': 'United States (federal, LT)',     'rate': 0.15,    'approximate': True},
    'none':         {'label': 'No tax modeling (disabled)',      'rate': 0.0,     'approximate': False},
    'custom':       {'label': 'Custom',                          'rate': None,    'approximate': False},
}

DEFAULT_JURISDICTION = 'germany'


def ensure_tax_settings_table():
    """Creates the tax_settings table if missing and seeds the default row. Idempotent."""
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS tax_settings (
                id           INTEGER PRIMARY KEY CHECK (id = 1),
                jurisdiction TEXT NOT NULL DEFAULT 'germany',
                tax_rate     REAL NOT NULL DEFAULT 0.26375,
                custom_rate  REAL,
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        """))
        session.execute(text("""
            INSERT OR IGNORE INTO tax_settings (id, jurisdiction, tax_rate)
            VALUES (1, :j, :r)
        """), {'j': DEFAULT_JURISDICTION, 'r': JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate']})
        session.commit()
    finally:
        session.close()


def get_active_tax_rate() -> float:
    """
    Reads the currently active tax rate. Called by optimizer.py on every
    portfolio construction run — cheap (single-row lookup), so no caching.
    Falls back to the German default if the table/row is missing or the
    read fails for any reason — a settings problem should never crash the
    pipeline.
    """
    try:
        session = get_session()
        try:
            row = session.execute(text(
                "SELECT tax_rate FROM tax_settings WHERE id = 1"
            )).fetchone()
        finally:
            session.close()
        if row and row[0] is not None:
            return float(row[0])
    except Exception as e:
        logger.warning(f"[tax_rates] get_active_tax_rate failed, using default: {e}")
    return JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate']


def get_tax_settings() -> dict:
    """Returns the full current settings row, for the settings page."""
    ensure_tax_settings_table()
    session = get_session()
    try:
        row = session.execute(text(
            "SELECT jurisdiction, tax_rate, custom_rate FROM tax_settings WHERE id = 1"
        )).fetchone()
    finally:
        session.close()
    if not row:
        return {
            'jurisdiction': DEFAULT_JURISDICTION,
            'tax_rate': JURISDICTION_PRESETS[DEFAULT_JURISDICTION]['rate'],
            'custom_rate': None,
        }
    return {'jurisdiction': row[0], 'tax_rate': float(row[1]), 'custom_rate': row[2]}


def set_tax_jurisdiction(jurisdiction: str, custom_rate: float = None) -> dict:
    """
    Updates the active jurisdiction. If jurisdiction == 'custom', custom_rate
    is required (as a decimal fraction, e.g. 0.26375 for 26.375%) and becomes
    the active tax_rate. Otherwise the preset's rate is used, and custom_rate
    (if provided) is stored alongside so switching back to Custom later
    remembers the last value entered.
    """
    ensure_tax_settings_table()

    if jurisdiction not in JURISDICTION_PRESETS:
        raise ValueError(f"Unknown jurisdiction: {jurisdiction}")

    if jurisdiction == 'custom':
        if custom_rate is None:
            raise ValueError("custom_rate is required when jurisdiction='custom'")
        if not (0.0 <= custom_rate <= 1.0):
            raise ValueError("custom_rate must be between 0 and 1 (a decimal fraction, e.g. 0.25 for 25%)")
        effective_rate = float(custom_rate)
    else:
        effective_rate = JURISDICTION_PRESETS[jurisdiction]['rate']

    session = get_session()
    try:
        session.execute(text("""
            UPDATE tax_settings SET
                jurisdiction = :j,
                tax_rate     = :rate,
                custom_rate  = COALESCE(:custom, custom_rate),
                updated_at   = datetime('now')
            WHERE id = 1
        """), {'j': jurisdiction, 'rate': effective_rate, 'custom': custom_rate})
        session.commit()
    finally:
        session.close()

    logger.info(f"[tax_rates] Jurisdiction set to '{jurisdiction}' — active rate {effective_rate:.4%}")
    return {'jurisdiction': jurisdiction, 'tax_rate': effective_rate}
