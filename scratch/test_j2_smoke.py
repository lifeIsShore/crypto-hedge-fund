"""
Functional smoke test for engine/portfolio/tax_rates.py (J2)
Uses an in-memory SQLite DB so it never touches engine_data.db.
Run from the hedge-fund root: python scratch/test_j2_smoke.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Monkey-patch get_session to use an in-memory engine ─────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

mem_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
MemSession = sessionmaker(bind=mem_engine)

import engine.db.db as dbmod
dbmod.engine  = mem_engine
dbmod.SessionLocal = MemSession
dbmod.get_session = lambda: MemSession()

# ── Import AFTER patch ────────────────────────────────────────────────────────
from engine.portfolio.tax_rates import (
    ensure_tax_settings_table, get_active_tax_rate,
    get_tax_settings, set_tax_jurisdiction, JURISDICTION_PRESETS,
    DEFAULT_JURISDICTION,
)

PASS = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
errors = []

def check(cond, msg):
    if cond:
        print(f"{PASS} {msg}")
    else:
        print(f"{FAIL} {msg}")
        errors.append(msg)


# ── 1. Table creation + default seeding ────────────────────────────────────
ensure_tax_settings_table()
rate = get_active_tax_rate()
check(abs(rate - 0.26375) < 1e-9, f"Default rate = {rate:.5f} (Germany Abgeltungsteuer = 26.375%)")

# ── 2. Preset switch — Austria ──────────────────────────────────────────────
set_tax_jurisdiction("austria")
s = get_tax_settings()
check(s["jurisdiction"] == "austria", "Austria jurisdiction stored")
check(abs(s["tax_rate"] - 0.275) < 1e-9, f"Austria rate = {s['tax_rate']:.3f}")

# ── 3. Custom rate ──────────────────────────────────────────────────────────
set_tax_jurisdiction("custom", custom_rate=0.260)
s2 = get_tax_settings()
check(s2["jurisdiction"] == "custom",        "Custom jurisdiction stored")
check(abs(s2["tax_rate"] - 0.260) < 1e-9,  f"Custom rate = {s2['tax_rate']:.3f}")
check(abs(s2["custom_rate"] - 0.260) < 1e-9, "custom_rate column populated")

# ── 4. Switching back to a preset remembers last custom_rate ────────────────
set_tax_jurisdiction("france")
s3 = get_tax_settings()
check(s3["jurisdiction"] == "france",   "France jurisdiction stored")
check(abs(s3["tax_rate"] - 0.30) < 1e-9, f"France rate = {s3['tax_rate']:.2f} (30%)")
# custom_rate should be preserved (COALESCE keeps old value when new custom is None)
check(s3["custom_rate"] is not None and abs(s3["custom_rate"] - 0.260) < 1e-9,
      f"custom_rate preserved = {s3['custom_rate']}")

# ── 5. Validation — unknown jurisdiction ────────────────────────────────────
try:
    set_tax_jurisdiction("narnia")
    check(False, "Unknown jurisdiction NOT rejected (should have raised)")
except ValueError as e:
    check(True, f"Unknown jurisdiction rejected: {e}")

# ── 6. Validation — custom without rate ────────────────────────────────────
try:
    set_tax_jurisdiction("custom", custom_rate=None)
    check(False, "custom + None rate NOT rejected (should have raised)")
except ValueError as e:
    check(True, f"custom_rate=None rejected: {e}")

# ── 7. Validation — rate out of range ──────────────────────────────────────
try:
    set_tax_jurisdiction("custom", custom_rate=1.5)  # 150% — nonsense
    check(False, "Out-of-range custom_rate NOT rejected (should have raised)")
except ValueError as e:
    check(True, f"custom_rate > 1.0 rejected: {e}")

# ── 8. No-tax preset ────────────────────────────────────────────────────────
set_tax_jurisdiction("none")
r_none = get_active_tax_rate()
check(r_none == 0.0, f"none preset active rate = {r_none} (tax modeling disabled)")

# ── 9. get_active_tax_rate() reflects current state ─────────────────────────
set_tax_jurisdiction("uk")
r_uk = get_active_tax_rate()
check(abs(r_uk - 0.20) < 1e-9, f"get_active_tax_rate() after preset switch = {r_uk:.2f}")

# ── 10. Round-trip all presets ───────────────────────────────────────────────
for key, preset in JURISDICTION_PRESETS.items():
    if key == "custom":
        continue
    set_tax_jurisdiction(key)
    r = get_active_tax_rate()
    expected = preset["rate"]
    check(abs(r - expected) < 1e-9,
          f"Preset '{key}': expected {expected:.5f}, got {r:.5f}")

print()
if errors:
    print(f"\033[91m{len(errors)} test(s) FAILED:\033[0m")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\033[92mALL TESTS PASSED — J2 tax_rates.py is fully functional.\033[0m")
