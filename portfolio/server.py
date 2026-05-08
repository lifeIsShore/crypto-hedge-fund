#!/usr/bin/env python3
"""
Simple Flask server to serve the HTML dashboard and handle API calls
"""

from flask import Flask, render_template_string, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import json
import subprocess
import os
from datetime import datetime
import pandas as pd
import logging

app = Flask(__name__, static_folder='.', static_url_path='')

# --- API ENDPOINTS ---

@app.route('/', methods=['GET'])
def dashboard():
    """Serve the HTML dashboard"""
    with open('dashboard.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/data/engine_state.json', methods=['GET'])
def get_engine_state():
    """Return the current engine state"""
    try:
        with open('data/engine_state.json', 'r', encoding='utf-8') as f:
            state = json.load(f)
            # Add current_values to state for dashboard
            if 'current_values' not in state:
                state['current_values'] = {
                    'total_portfolio': 0,
                    'cash': 0,
                    'holdings': {}
                }
            return jsonify(state)
    except FileNotFoundError:
        return jsonify({'error': 'Engine state not found'}), 404

@app.route('/api/log_transaction', methods=['POST'])
def log_transaction():
    """Log a transaction to the ledger CSV"""
    try:
        data = request.json
        csv_row = data.get('csvRow', '')
        
        # Validation: CSV row exists
        if not csv_row:
            return jsonify({'error': 'No CSV row provided'}), 400
        
        # Validation: CSV row is not empty/whitespace
        if not csv_row.strip():
            return jsonify({'error': 'CSV row cannot be empty'}), 400
        
        # Validation: CSV row has minimum required fields
        fields = csv_row.split(',')
        if len(fields) < 3:  # At minimum: Date, Action, Ticker
            return jsonify({'error': 'CSV row must have at least 3 fields (Date, Action, Ticker)'}), 400
        
        print(f"[LOG_TRANSACTION] Saving: {csv_row}")
        
        # Ensure data directory exists
        csv_path = 'data/ledger.csv'
        os.makedirs(os.path.dirname(csv_path) or '.', exist_ok=True)
        
        # Append to ledger.csv
        with open(csv_path, 'a', encoding='utf-8') as f:
            f.write(csv_row + '\n')
        
        print(f"[LOG_TRANSACTION] ✅ Successfully saved to {csv_path}")
        return jsonify({'success': True, 'message': 'Transaction logged'})
    except Exception as e:
        error_msg = str(e)
        print(f"[LOG_TRANSACTION] ❌ Error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/refresh_engine', methods=['POST'])
def refresh_engine():
    """Recalculate the engine"""
    try:
        # Run the recalculate_engine.py script
        result = subprocess.run(
            ['python', 'recalculate_engine.py'],
            capture_output=True,
            timeout=60,
            text=True,
            cwd=os.getcwd(),
            encoding='utf-8'
        )
        
        # Log output for debugging
        if result.stdout:
            print(f"[recalculate_engine] stdout: {result.stdout}")
        if result.stderr:
            print(f"[recalculate_engine] stderr: {result.stderr}")
        
        if result.returncode == 0:
            # Validate that engine_state.json was created/updated
            engine_state_path = 'data/engine_state.json'
            if not os.path.exists(engine_state_path):
                error_msg = 'Engine completed but engine_state.json was not created'
                print(f"[ERROR] {error_msg}")
                return jsonify({'error': error_msg}), 500
            
            # Validate JSON is readable
            try:
                with open(engine_state_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as je:
                error_msg = f'engine_state.json is corrupted: {str(je)}'
                print(f"[ERROR] {error_msg}")
                return jsonify({'error': error_msg}), 500
            
            return jsonify({'success': True, 'message': 'Engine recalculated'})
        else:
            error_msg = result.stderr or "Unknown error"
            print(f"[ERROR] Engine failed with code {result.returncode}: {error_msg}")
            return jsonify({'error': f'Engine error: {error_msg}'}), 500
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Engine calculation timed out (>60s)'}), 500
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Exception during refresh: {error_msg}")
        return jsonify({'error': error_msg}), 500

def run_scheduled_refresh():
    """Background task to refresh engine"""
    try:
        print(f"\n⏰ [SCHEDULED REFRESH] Starting auto-refresh at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run the recalculate_engine.py script
        result = subprocess.run(
            ['python', 'recalculate_engine.py'],
            capture_output=True,
            timeout=60,
            text=True,
            cwd=os.getcwd(),
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ [SCHEDULED REFRESH] Auto-refresh completed successfully!")
            print("📊 Dashboard will update on next page load\n")
        else:
            error_msg = result.stderr or "Unknown error"
            print(f"❌ [SCHEDULED REFRESH] Auto-refresh failed: {error_msg}\n")
    except Exception as e:
        print(f"❌ [SCHEDULED REFRESH] Exception: {str(e)}\n")

def start_scheduler():
    """Initialize and start the background scheduler"""
    scheduler = BackgroundScheduler()
    
    # Schedule refresh every Monday at 5 PM CET (17:00)
    # day_of_week: 0=Monday, 6=Sunday
    # timezone: Europe/Berlin = CET/CEST
    scheduler.add_job(
        func=run_scheduled_refresh,
        trigger="cron",
        day_of_week=0,  # Monday
        hour=17,         # 5 PM (17:00)
        minute=0,
        timezone="Europe/Berlin",
        id="weekly_refresh",
        name="Weekly Portfolio Refresh (Monday 5 PM CET)"
    )
    
    scheduler.start()
    print("\n⏱️  Scheduler initialized!")
    print("📅 Auto-refresh scheduled: Every Monday at 5:00 PM CET (17:00)")
    print("📍 Timezone: Europe/Berlin (CET/CEST)\n")
    
    # Prevent scheduler from being killed when Flask restarts in debug mode
    import atexit
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler

# --- PEAD / QUANT RESEARCH ENDPOINTS ---

@app.route('/api/run_pead_engine', methods=['POST'])
def run_pead_engine():
    """
    Runs the PEAD engine with the options sent in the JSON body.
    Body (all optional):
      { "refresh": bool, "backfill": bool, "lookback": int, "outcomes_only": bool }
    """
    try:
        body      = request.get_json(silent=True) or {}
        refresh   = bool(body.get('refresh', False))
        backfill  = bool(body.get('backfill', False))
        lookback  = int(body.get('lookback', 90))
        outcomes  = bool(body.get('outcomes_only', False))

        cmd = ['python', 'run_engine.py']
        if refresh:  cmd.append('--refresh')
        if backfill: cmd.append('--backfill')
        if outcomes: cmd.append('--outcomes')
        cmd += ['--lookback', str(lookback)]

        pead_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'ml_quant_finance_research', 'quant_research', 'pead_engine'
        )

        print(f"[PEAD ENGINE] Running: {' '.join(cmd)} in {pead_dir}")
        import os
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
            text=True,
            cwd=pead_dir,
            encoding='utf-8',
            env=env,
        )

        stdout = result.stdout or ''
        stderr = result.stderr or ''

        if result.returncode == 0:
            state_path = os.path.join(pead_dir, 'data', 'pead_state.json')
            pead_state = None
            if os.path.exists(state_path):
                try:
                    import re as _re
                    with open(state_path, 'r', encoding='utf-8') as f:
                        raw = _re.sub(r'\bNaN\b', 'null', f.read())
                        pead_state = json.loads(raw)
                except Exception as e:
                    print(f"[PEAD ENGINE] Could not read pead_state.json: {e}")
            return jsonify({'success': True, 'log': stdout + stderr, 'pead_state': pead_state})
        else:
            print(f"[PEAD ENGINE] Failed (rc={result.returncode}): {stderr}")
            return jsonify({'success': False, 'error': stderr or stdout or 'Unknown error', 'log': stdout + stderr}), 500

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'PEAD engine timed out (>5 min)'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/run_regime_engine', methods=['POST'])
def run_regime_engine():
    """Runs the regime engine. Pass { "backfill": true } to rebuild from scratch."""
    try:
        body     = request.get_json(silent=True) or {}
        backfill = bool(body.get('backfill', False))

        cmd = ['python', 'run_engine.py']
        if backfill: cmd.append('--backfill')

        regime_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'ml_quant_finance_research', 'quant_research', 'regime_engine'
        )

        import os
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"

        result = subprocess.run(
            cmd, capture_output=True, timeout=180,
            text=True, cwd=regime_dir, encoding='utf-8', env=env,
        )
        stdout = result.stdout or ''
        stderr = result.stderr or ''
        return jsonify({
            'success': result.returncode == 0,
            'log':     stdout + stderr,
            'error':   stderr if result.returncode != 0 else None,
        }), 200 if result.returncode == 0 else 500

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Regime engine timed out (>3 min)'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# --- RESEARCH LAYER ENDPOINTS ---

@app.route('/data/research_state.json', methods=['GET'])
def get_research_state():
    """
    Merges outputs from the research notebooks into a single response.
    Returns { available: false } gracefully if notebooks haven't been run yet.
    Files are written by research/notebooks/ and live in research/outputs/.
    """
    RESEARCH_OUTPUTS = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'ml_quant_finance_research', 'general_research', 'outputs'
    )

    files = {
        'correlation': os.path.join(RESEARCH_OUTPUTS, 'correlation_state.json'),
        'regime':      os.path.join(RESEARCH_OUTPUTS, 'regime_state.json'),
        'factor':      os.path.join(RESEARCH_OUTPUTS, 'factor_state.json'),
    }

    # Check if any research outputs exist at all
    any_available = any(os.path.exists(p) for p in files.values())
    if not any_available:
        return jsonify({
            'available': False,
            'message':   'No research outputs found. Run the notebooks in research/notebooks/ first.'
        })

    merged = {'available': True}

    for key, path in files.items():
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    merged[key] = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f'Could not read {path}: {e}')
                merged[key] = None
        else:
            merged[key] = None  # Notebook not run yet — not an error

    return jsonify(merged)


# --- STARTUP ---

if __name__ == '__main__':
    print("\n" + "="*50)
    print(" QUANT ENGINE DASHBOARD (HTML)")
    print("="*50)
    print("\n Open your browser and go to:")
    print("   -> http://localhost:5000")
    print("\n" + "="*50)
    
    # Initialize scheduler
    start_scheduler()
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)