import sqlite3
import csv
import sys
import os

DB_PATH = 'engine_data.db'
CSV_PATH = 'portfolio/data/ledger.csv'

def main():
    if not os.path.exists(CSV_PATH):
        print(f"File not found: {CSV_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM trades')
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('Date,Action,Ticker'):
                    break
            
            reader = csv.reader(f)
            for row in reader:
                if not row or not row[0].strip() or row[0].startswith('#'):
                    continue
                date_str = row[0].strip()
                action = row[1].strip()
                ticker = row[2].strip()
                quantity_str = row[3].strip()
                price_str = row[4].strip()
                total_str = row[5].strip()
                notes = row[6].strip() if len(row) > 6 else ""

                quantity = float(quantity_str) if quantity_str else None
                price = float(price_str) if price_str else None
                total = float(total_str) if total_str else 0.0
                fee_eur = 0.0

                if action.upper() == 'FEE':
                    fee_eur = total

                cursor.execute('''
                    INSERT INTO trades (date, ticker, action, quantity, price_eur, value_eur, fee_eur, notes, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'csv_migration')
                ''', (date_str, ticker, action.upper(), quantity, price, total, fee_eur, notes))
                
        conn.commit()

        # Reconstruct cash history
        cursor.execute('DELETE FROM cash_history')
        cursor.execute('SELECT date, action, value_eur, fee_eur, notes FROM trades ORDER BY date ASC, id ASC')
        trades = cursor.fetchall()

        cash = 0.0
        for date_str, action, val, fee, notes in trades:
            val = val or 0.0
            fee = fee or 0.0
            action = action.upper()
            
            if action == "BUY":
                cash = cash - val - fee
                event = "BUY_DEBIT"
            elif action == "SELL":
                cash = cash + val - fee
                event = "SELL_CREDIT"
            elif action == "DEPOSIT":
                cash = cash + val
                event = "DEPOSIT"
            elif action == "DIVIDEND":
                cash = cash + val
                event = "DIVIDEND"
            elif action == "FEE":
                cash = cash - val
                event = "FEE_DEBIT"
            else:
                event = "OTHER"
                
            cursor.execute('''
                INSERT INTO cash_history (date, cash_eur, event_type, notes)
                VALUES (?, ?, ?, ?)
            ''', (date_str, round(cash, 4), event, notes))

        conn.commit()
        
        # We also need to reconstruct positions_history
        cursor.execute('DELETE FROM positions_history')
        
        # Build running positions
        positions = {} # ticker -> {qty, price, value}
        
        trades_list = cursor.execute('SELECT date, action, ticker, quantity, price_eur, value_eur, fee_eur, notes FROM trades ORDER BY date ASC, id ASC').fetchall()
        for date_str, action, ticker, qty, price, val, fee, notes in trades_list:
            if action.upper() in ("BUY", "SELL") and ticker and ticker != "CASH":
                if ticker not in positions:
                    positions[ticker] = {"qty": 0.0, "price": 0.0, "value": 0.0}
                
                q = float(qty or 0)
                if action.upper() == "BUY":
                    positions[ticker]["qty"] += q
                elif action.upper() == "SELL":
                    positions[ticker]["qty"] -= q
                    if positions[ticker]["qty"] < 1e-6:
                        positions[ticker]["qty"] = 0
                        
                positions[ticker]["price"] = float(price or 0)
                positions[ticker]["value"] = positions[ticker]["qty"] * positions[ticker]["price"]
                
                # We need to insert snapshot for this date
                total_val = sum(p["value"] for p in positions.values())
                
                for t, data in positions.items():
                    if data["qty"] > 0:
                        weight = data["value"] / total_val if total_val > 0 else 0
                        cursor.execute('''
                            INSERT INTO positions_history (date, ticker, quantity, price, value_eur, weight)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (date_str, t, data["qty"], data["price"], data["value"], weight))
                
        conn.commit()
        print("Migration successful.")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
