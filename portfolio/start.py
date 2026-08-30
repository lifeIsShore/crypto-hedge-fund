#!/usr/bin/env python3
"""
Start the Quant Engine Dashboard
Initializes the engine and launches the Flask server
"""

import subprocess
import sys
import time
import os

def main():
    print("\n" + "="*60)
    print("TRADE REPUBLIC QUANT ENGINE - DASHBOARD")
    print("="*60)
    
    # Step 1: Initialize engine
    print("\nInitializing engine...")
    result = subprocess.run(['python', 'recalculate_engine.py'], capture_output=True, text=True, errors='replace')
    if result.returncode != 0:
        print(f"Engine initialization failed:\n{result.stderr}")
        return 1
    print("Engine initialized")
    
    # Step 2: Start server
    print("\nStarting Flask server...\n")
    time.sleep(1)
    
    try:
        subprocess.run(['python', 'server.py'])
    except KeyboardInterrupt:
        print("\n\nDashboard stopped.")
        return 0
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
