import tkinter as tk
from tkinter import simpledialog
import subprocess
import os

# Dark theme colors matching the institutional dashboard
BG_COLOR = "#0b1121"
SURFACE_COLOR = "#1e293b"
TEXT_COLOR = "#f8fafc"
MUTED_COLOR = "#94a3b8"
ACCENT_GREEN = "#10b981"
ACCENT_BLUE = "#3b82f6"
ACCENT_RED = "#ef4444"
ACCENT_ORANGE = "#f59e0b"

def run_bat(bat_filename):
    """
    Launch the batch file in a new command prompt window.
    We use '/k' so the window stays open after the script finishes,
    allowing the user to read the logs.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.Popen(['start', 'cmd', '/k', bat_filename], shell=True, cwd=base_dir)
    except Exception as e:
        print(f"Failed to launch {bat_filename}: {e}")

class ControlTowerLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Hedge Fund Control Tower")
        self.geometry("950x500")
        self.configure(bg=BG_COLOR)
        self.resizable(True, True)
        self.minsize(800, 450)
        
        # Center the window on the screen
        self.eval('tk::PlaceWindow . center')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Title Label
        title_frame = tk.Frame(self, bg=BG_COLOR, pady=20)
        title_frame.pack(fill=tk.X)
        
        tk.Label(
            title_frame, 
            text="CONTROL TOWER", 
            fg=TEXT_COLOR, 
            bg=BG_COLOR, 
            font=("Segoe UI", 16, "bold")
        ).pack()
        
        tk.Label(
            title_frame, 
            text="OPERATIONS LAUNCHER", 
            fg=MUTED_COLOR, 
            bg=BG_COLOR, 
            font=("Segoe UI", 10)
        ).pack()

        content_frame = tk.Frame(self, bg=BG_COLOR)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        
        left_col = tk.Frame(content_frame, bg=BG_COLOR)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        right_col = tk.Frame(content_frame, bg=BG_COLOR)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # Groups - Left Column
        self.create_group(left_col, "LIVE OPERATIONS", ACCENT_GREEN, [
            ("Launch Dashboard", "DASHBOARD_ONLY.bat", "Live Web UI"),
            ("Run Daily Pipeline", "RUN_FUND_TOTAL.bat", "Ingest & Rebalance")
        ])
        
        self.create_group(left_col, "BACKTEST & RESEARCH", ACCENT_BLUE, [
            ("Run Walk-Forward Backtest", "RUN_BACKTEST.bat", "Full simulation")
        ])
        
        # Groups - Right Column
        self.create_group(right_col, "PAPER TRADING SANDBOX", ACCENT_ORANGE, [
            ("Launch Sandbox Dashboard", "DASHBOARD_SANDBOX.bat", "View paper trades"),
            ("Run Sandbox Pipeline", "RUN_SANDBOX.bat", "Dry-run execution"),
            ("Fix Sandbox Cash", "FIX_SANDBOX_CASH.bat", "Reconcile double-count")
        ])
        
        self.create_group(right_col, "DATA PIPELINES & RECOVERY", ACCENT_RED, [
            ("Run PEAD & Earnings Scraper", "python fill_earnings_data.py", "Backfill missing earnings dates"),
            ("Single Ticker ML Recovery", self.run_single_ticker, "Run ML pipeline for one failed ticker")
        ])

    def run_single_ticker(self):
        ticker = simpledialog.askstring("Single Ticker Recovery", "Enter ticker symbol to run (e.g., AAPL, SIE.DE):", parent=self)
        if ticker and ticker.strip():
            ticker = ticker.strip().upper()
            cmd = f"python ml_quant_finance_research/ml_research/stock_ml_lab/run_ml_pipeline.py --ticker {ticker}"
            run_bat(cmd)

    def create_group(self, parent, title, accent_color, buttons_data):
        frame = tk.Frame(parent, bg=SURFACE_COLOR, padx=15, pady=15)
        frame.pack(fill=tk.X, pady=10)
        
        # Group Header
        header_frame = tk.Frame(frame, bg=SURFACE_COLOR)
        header_frame.pack(fill=tk.X, anchor="w", pady=(0, 10))
        
        # Little colored dot indicator
        tk.Label(header_frame, text="■", fg=accent_color, bg=SURFACE_COLOR, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(header_frame, text=title, fg=TEXT_COLOR, bg=SURFACE_COLOR, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        
        # Buttons
        for text, command, desc in buttons_data:
            btn_frame = tk.Frame(frame, bg=SURFACE_COLOR)
            btn_frame.pack(fill=tk.X, pady=4)
            
            # Use standard Tkinter Button with custom styling
            btn = tk.Button(
                btn_frame, 
                text=text, 
                command=command if callable(command) else lambda c=command: run_bat(c),
                bg="#334155", 
                fg=TEXT_COLOR, 
                activebackground="#475569", 
                activeforeground=TEXT_COLOR,
                font=("Segoe UI", 10),
                relief=tk.FLAT,
                cursor="hand2",
                width=26,
                anchor="w",
                padx=10
            )
            btn.pack(side=tk.LEFT)
            
            # Hover effect bindings
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#475569"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#334155"))
            
            # Description (Wraplength added for dynamic resizing)
            tk.Label(btn_frame, text=desc, fg=MUTED_COLOR, bg=SURFACE_COLOR, font=("Segoe UI", 9), wraplength=200, justify="left").pack(side=tk.LEFT, padx=10)

if __name__ == "__main__":
    app = ControlTowerLauncher()
    app.mainloop()
