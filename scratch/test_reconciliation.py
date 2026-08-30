import os
import json
from datetime import datetime
import sys
sys.path.insert(0, r"c:\Users\ahmty\Desktop\SW-PROJECTS\crypto-hedge-fund")
from engine.execution.reconciliation import RECON_STATE_PATH

def mock_reconciliation():
    discrepancies = [
        {"asset": "BTC", "internal_qty": 1.5, "live_qty": 1.45, "delta_qty": 0.05, "delta_eur": 3000.0}
    ]
    matched = [
        {"asset": "ETH", "qty": 10.0, "delta_eur": 0.0}
    ]
    state = {
        "status": "FAILED — DISCREPANCIES DETECTED",
        "timestamp": datetime.now().isoformat(),
        "discrepancies": discrepancies,
        "matched": matched,
        "dust_threshold_eur": 1.0
    }
    with open(RECON_STATE_PATH, "w") as f:
        json.dump(state, f)
    print("Mock state written.")

if __name__ == "__main__":
    mock_reconciliation()
