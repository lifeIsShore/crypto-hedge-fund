import json
import hashlib
from datetime import datetime
from engine.db.db import get_session
from sqlalchemy import text

def push_raw_event(source: str, event_type: str, binance_event_id: str, event_time: datetime, payload: dict, account_id: str = None) -> int:
    """
    Persist an immutable raw event from an exchange.
    Returns the internal source_event_id.
    """
    raw_json = json.dumps(payload, sort_keys=True)
    payload_hash = hashlib.sha256(raw_json.encode('utf-8')).hexdigest()

    session = get_session()
    try:
        # Check if exists (idempotency)
        existing = session.execute(
            text("SELECT id FROM tax_raw_events WHERE binance_event_id = :eid AND source = :src"),
            {'eid': binance_event_id, 'src': source}
        ).fetchone()

        if existing:
            return existing[0]

        result = session.execute(
            text("""
                INSERT INTO tax_raw_events 
                (source, account_id, event_type, binance_event_id, event_time, raw_json, payload_hash)
                VALUES (:src, :acc, :etype, :eid, :etime, :json, :hash)
            """),
            {
                'src': source,
                'acc': account_id,
                'etype': event_type,
                'eid': binance_event_id,
                'etime': event_time.isoformat(),
                'json': raw_json,
                'hash': payload_hash
            }
        )
        session.commit()
        return result.lastrowid
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
