"""
run_screener.py
Automated stock screening script for Indian stocks.
1. Combines NSE & BSE universes and deduplicates by ISIN.
2. Performs batch download of weekly historical price data.
3. Monkey-patches Factor Analysis script to use cache and calculates expected Sharpe ratio.
4. Filters for expected Sharpe > 1.0.
5. Runs Valuation Random Forest model to check for undervaluation.
6. Queries local database for 3yr Revenue CAGR and 3yr NPM Average.
7. Calculates 3yr Stock Price Performance in-memory.
8. Writes results to data/screened_stocks.json.
"""

import os
import sys
import time
import json
import sqlite3
import warnings
import shutil
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

# Suppress warnings
warnings.filterwarnings('ignore')

# 1. Environment Setup & Sibling Directory Detection
ORIGINAL_CWD = Path.cwd().resolve()
print(f"Original working directory: {ORIGINAL_CWD}")

# Find factoranalysis and Valuation directories
local_paths = [
    (Path("factoranalysis"), Path("Valuation")),  # GitHub Actions checkout paths
    (Path("..") / "factoranalysis", Path("..") / "Valuation"),  # Sibling directories locally (from parent)
    (Path("..") / ".." / "factoranalysis", Path("..") / ".." / "Valuation")  # Sibling directories locally (from subfolder)
]

FACTOR_DIR = None
VALUATION_DIR = None

for f_path, v_path in local_paths:
    if f_path.exists() and v_path.exists():
        FACTOR_DIR = f_path.resolve()
        VALUATION_DIR = v_path.resolve()
        print(f"Detected project directories:\n  FactorAnalysis: {FACTOR_DIR}\n  Valuation: {VALUATION_DIR}")
        break

if not FACTOR_DIR:
    # Default fallbacks (check if running inside subfolder)
    if (ORIGINAL_CWD / ".." / ".." / "factoranalysis").exists():
        FACTOR_DIR = (ORIGINAL_CWD / ".." / ".." / "factoranalysis").resolve()
        VALUATION_DIR = (ORIGINAL_CWD / ".." / ".." / "Valuation").resolve()
    else:
        FACTOR_DIR = (ORIGINAL_CWD / ".." / "factoranalysis").resolve()
        VALUATION_DIR = (ORIGINAL_CWD / ".." / "Valuation").resolve()
    print(f"Project directories not automatically detected. Using fallbacks:\n  FactorAnalysis: {FACTOR_DIR}\n  Valuation: {VALUATION_DIR}")


# Define data paths
nse_map_path = FACTOR_DIR / "data" / "nse_map.csv"
bse_map_path = FACTOR_DIR / "data" / "bse_map.csv"
db_source_path = FACTOR_DIR / "data" / "screener_data.db"
db_target_path = VALUATION_DIR / "screener_data.db"

# Create output data directory in current workspace
output_dir = ORIGINAL_CWD / "data"
output_dir.mkdir(exist_ok=True)
output_json_path = output_dir / "screened_stocks.json"

# Copy populated database to Valuation directory if source exists
if db_source_path.exists():
    try:
        print(f"Copying populated screener_data.db from {db_source_path} to {db_target_path}...")
        shutil.copy2(db_source_path, db_target_path)
        print("Database copied successfully.")
    except Exception as e:
        print(f"Warning: Failed to copy database: {e}")
else:
    print(f"Warning: Database source {db_source_path} not found.")

# 2. Mock Streamlit Class for Factor Analysis Import
class DummyStreamlit:
    def __init__(self):
        self.session_state = {"current_rf": 6.5}
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass
    def cache_data(self, *args, **kwargs):
        def decorator(func=None):
            return func if func else lambda f: f
        if len(args) == 1 and callable(args[0]): return args[0]
        return decorator
    def set_page_config(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def header(self, *args, **kwargs): pass
    def subheader(self, *args, **kwargs): pass
    def text_input(self, *args, **kwargs): return ""
    def number_input(self, *args, **kwargs): return 6.5
    def date_input(self, *args, **kwargs): return None
    def markdown(self, *args, **kwargs): pass
    def plotly_chart(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def success(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def write(self, *args, **kwargs): pass
    def dataframe(self, *args, **kwargs): pass
    @property
    def sidebar(self): return self
    def tabs(self, *args, **kwargs): return [self, self]
    def columns(self, *args, **kwargs): return [self]*args[0] if len(args)>0 else [self,self]
    def file_uploader(self, *args, **kwargs): return None
    def button(self, *args, **kwargs): return False
    def spinner(self, *args, **kwargs): return self
    def stop(self): sys.exit()
    def download_button(self, *args, **kwargs): pass

# Set Dummy Streamlit in sys.modules before importing portfolio_analyzer
sys.modules['streamlit'] = DummyStreamlit()

# 3. Load Universe & Deduplicate by ISIN
# 3. Load Universe & Filter by Database Availability
print("\nLoading NSE and BSE maps...")
nse_tickers = {}
if nse_map_path.exists():
    try:
        df_nse = pd.read_csv(nse_map_path)
        for _, row in df_nse.iterrows():
            ticker = str(row.get('Ticker', '')).strip().upper()
            isin = str(row.get('ISIN', '')).strip()
            name = str(row.get('NAME OF COMPANY', '')).strip()
            if ticker and isin and ticker != 'nan' and isin != 'nan':
                nse_tickers[ticker] = {
                    'isin': isin,
                    'ticker': ticker + '.NS',
                    'symbol': ticker,
                    'name': name,
                    'exchange': 'NSE'
                }
        print(f"Loaded {len(df_nse)} tickers from NSE map.")
    except Exception as e:
        print(f"Error loading NSE map: {e}")

bse_tickers = {}
if bse_map_path.exists():
    try:
        df_bse = pd.read_csv(bse_map_path)
        for _, row in df_bse.iterrows():
            ticker_sym = str(row.get('TckrSymb', '')).strip().upper()
            isin = str(row.get('ISIN', '')).strip()
            name = str(row.get('FinInstrmNm', '')).strip()
            if ticker_sym and isin and ticker_sym != 'nan' and isin != 'nan':
                bse_tickers[ticker_sym] = {
                    'isin': isin,
                    'ticker': ticker_sym + '.BO',
                    'symbol': ticker_sym,
                    'name': name,
                    'exchange': 'BSE'
                }
        print(f"Loaded {len(df_bse)} tickers from BSE map.")
    except Exception as e:
        print(f"Error loading BSE map: {e}")

# Load tickers from database
print("Loading tickers from database to filter universe...")
db_tickers = []
if db_source_path.exists():
    try:
        db_conn = sqlite3.connect(db_source_path)
        db_rows = db_conn.execute("SELECT ticker FROM companies WHERE data_available=1").fetchall()
        db_tickers = [r[0].strip().upper() for r in db_rows]
        db_conn.close()
        print(f"Found {len(db_tickers)} companies with available data in the database.")
    except Exception as e:
        print(f"Error reading database tickers: {e}")
else:
    print(f"Warning: Database source {db_source_path} not found. Cannot filter universe by DB availability.")

stocks = {}
if db_tickers:
    for db_t in db_tickers:
        if db_t in nse_tickers:
            info = nse_tickers[db_t]
            stocks[info['isin']] = info
        elif db_t in bse_tickers:
            info = bse_tickers[db_t]
            stocks[info['isin']] = info
        else:
            # Fallback if in database but not in maps (default to NSE)
            stocks[db_t] = {
                'isin': db_t,
                'ticker': db_t + '.NS',
                'symbol': db_t,
                'name': db_t,
                'exchange': 'NSE'
            }
else:
    # Fallback to loading all tickers if database loading failed
    print("Fallback: Using all tickers from NSE map.")
    for isin, info in nse_tickers.items():
        stocks[isin] = info

total_unique_stocks = len(stocks)
print(f"Total unique stocks to screen: {total_unique_stocks}")

if total_unique_stocks == 0:
    print("Error: No tickers loaded. Exiting.")
    sys.exit(1)


# 4. Batch Download Price Data
print("\nPreparing price data download (10 years of weekly data)...")
end_date = datetime.now()
start_date = end_date - timedelta(days=365*10)

all_prices = {}
weekly_returns_dict = {}
tickers_list = [s['ticker'] for s in stocks.values()]

# Split into batches of 250 to respect yfinance rate limits and minimize requests
batch_size = 250
total_batches = (len(tickers_list) - 1) // batch_size + 1

print(f"Downloading price data in {total_batches} batches...")
for idx in range(0, len(tickers_list), batch_size):
    batch = tickers_list[idx:idx+batch_size]
    batch_num = idx // batch_size + 1
    print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} tickers)...")
    
    df = pd.DataFrame()
    retries = 3
    for attempt in range(retries):
        try:
            df = yf.download(batch, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval="1d", progress=False, group_by='ticker')
            if not df.empty:
                break
            else:
                print(f"  Attempt {attempt+1} returned empty data. Retrying in 12s...")
                time.sleep(12)
        except Exception as e:
            print(f"  Attempt {attempt+1} failed with error: {e}. Retrying in 12s...")
            time.sleep(12)
            
    if df.empty:
        print(f"  Warning: Batch {batch_num} failed completely after {retries} attempts.")
        continue

    # Parse close prices for each ticker in the batch
    for ticker in batch:
        try:
            # Handle single vs multi-index columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.levels[0]:
                    ticker_df = df[ticker]
                else:
                    continue
            else:
                ticker_df = df
            
            # Check if 'Close' exists
            close_col = [c for c in ticker_df.columns if c.lower().startswith('close')]
            if close_col:
                close = ticker_df[close_col[0]].dropna()
                if len(close) > 10:
                    # Resample to weekly (Friday)
                    weekly_prices = close.resample('W-FRI').last()
                    all_prices[ticker] = weekly_prices
                    # Calculate weekly percent change
                    returns = weekly_prices.pct_change().dropna()
                    if len(returns) > 5:
                        weekly_returns_dict[ticker] = returns
        except Exception as e:
            # Silently skip single ticker failures to avoid cluttering logs
            pass

    time.sleep(3.0) # sleep between batches to respect rate limits


print(f"Successfully downloaded price history for {len(weekly_returns_dict)} stocks.")

# 5. Load and Run Fama-French Factor Expected Sharpe Calculation
print("\nLoading Fama-French Factor Analysis module...")
sys.path.insert(0, str(FACTOR_DIR))
os.chdir(str(FACTOR_DIR))

try:
    import portfolio_analyzer_0428_fixed as pa
    
    # Setup dates matching the factor calculation
    sd_str = start_date.strftime('%Y-%m-%d')
    ed_str = end_date.strftime('%Y-%m-%d')
    
    # Load factors
    print("Loading Fama-French factors...")
    ff_factors = pa.fetch_ff_factors(sd_str, ed_str)
    if ff_factors is None or ff_factors.empty:
        print("Warning: Failed to load pre-calculated factors. Using fallback factor approximation...")
        ff_factors = pa.fetch_ff_factors_fallback(sd_str, ed_str)
    
    # Patch weekly_returns function in portfolio analyzer to use our downloaded cache
    def patched_weekly_returns(ticker, sd, ed):
        return weekly_returns_dict.get(ticker)
    
    pa.weekly_returns = patched_weekly_returns
    
    # Run factor regression for all stocks and filter by expected Sharpe > 1
    print("\nCalculating expected Sharpe ratio for all stocks...")
    high_sharpe_stocks = []
    
    for isin, stock_info in stocks.items():
        ticker = stock_info['ticker']
        if ticker not in weekly_returns_dict:
            continue
            
        try:
            # Run factor analysis regression
            metrics = pa.compute_factor_metrics_for_stock(ticker, sd_str, ed_str, ff_factors)
            if metrics:
                sharpe = metrics.get('Sharpe', 0.0)
                exp_return = metrics.get('Exp_Annual_Rtn', 0.0)
                if sharpe is not None and not np.isnan(sharpe) and sharpe > 1.0:
                    stock_copy = stock_info.copy()
                    stock_copy['expected_sharpe'] = float(sharpe)
                    stock_copy['expected_return'] = float(exp_return)
                    high_sharpe_stocks.append(stock_copy)
        except Exception as e:
            pass
            
    print(f"Found {len(high_sharpe_stocks)} stocks with expected Sharpe Ratio > 1.0")
    
except Exception as e:
    print(f"Error loading/running factor analysis: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    # Restore working directory
    os.chdir(str(ORIGINAL_CWD))

# 6. Load Valuation Model and Predict Fair P/E for High Sharpe Stocks
print("\nLoading Valuation Random Forest model...")
sys.path.insert(0, str(VALUATION_DIR))
os.chdir(str(VALUATION_DIR))

undervalued_stocks = []

try:
    import pe_prediction_model as pe_mod
    
    # Initialize and load model
    val_model = pe_mod.PEPredictionModel('indian_stocks_tickers.csv')
    val_model.load_model('pe_prediction_model.pkl')
    
    # Connect to the SQLite database
    db_conn = sqlite3.connect('screener_data.db')
    
    # Helper to parse years, e.g. "Mar 2025"
    def parse_year_str(year_str):
        try:
            return datetime.strptime(year_str, "%b %Y")
        except:
            try:
                # Handle cases like "2025"
                return datetime.strptime(year_str, "%Y")
            except:
                return datetime.min

    # Fetch additional data and evaluate undervaluation for each stock
    print(f"Evaluating valuation for {len(high_sharpe_stocks)} stocks...")
    for idx, stock in enumerate(high_sharpe_stocks):
        ticker = stock['ticker']
        clean_ticker = stock['symbol']
        
        try:
            # Predict P/E and Fair Price
            pred = val_model.predict_pe(ticker)
            if pred:
                current_price = pred.get('current_price', np.nan)
                fair_price = pred.get('fair_price', np.nan)
                upside = pred.get('upside_downside_pct', np.nan)
                
                # Check if undervalued (Fair Price > Current Price)
                if upside is not None and not np.isnan(upside) and upside > 0.0:
                    stock_copy = stock.copy()
                    stock_copy['current_price'] = float(current_price) if not pd.isna(current_price) else None
                    stock_copy['fair_price'] = float(fair_price) if not pd.isna(fair_price) else None
                    stock_copy['valuation_upside_pct'] = float(upside)
                    stock_copy['actual_pe'] = float(pred.get('current_pe')) if pred.get('current_pe') is not None and not pd.isna(pred.get('current_pe')) else None
                    stock_copy['predicted_pe'] = float(pred.get('predicted_pe')) if pred.get('predicted_pe') is not None and not pd.isna(pred.get('predicted_pe')) else None
                    
                    # Resolve Sector and Industry
                    db_sector = pred.get('sector', 'Unknown')
                    db_industry = pred.get('industry', 'Unknown')
                    stock_copy['sector'] = db_sector if db_sector and db_sector != 'Unknown' else stock.get('sector', 'Unknown')
                    stock_copy['industry'] = db_industry if db_industry and db_industry != 'Unknown' else stock.get('industry', 'Unknown')
                    
                    # Fetch Market Cap from key_metrics
                    cursor = db_conn.cursor()
                    cursor.execute("SELECT market_cap FROM key_metrics WHERE ticker = ?", (clean_ticker,))
                    row = cursor.fetchone()
                    stock_copy['market_cap_cr'] = float(row[0]) if row and row[0] is not None else None
                    
                    # Calculate 3yr Revenue CAGR & 3yr NPM Average from database
                    cursor.execute(
                        "SELECT year, sales, net_profit FROM annual_profit_loss WHERE ticker = ? AND year NOT LIKE '%TTM%'",
                        (clean_ticker,)
                    )
                    pl_rows = cursor.fetchall()
                    
                    valid_pl = []
                    for y_str, sales, net_profit in pl_rows:
                        y_date = parse_year_str(y_str)
                        if y_date != datetime.min and sales is not None:
                            valid_pl.append((y_date, sales, net_profit))
                    
                    # Sort chronologically
                    valid_pl.sort(key=lambda x: x[0])
                    
                    # 3yr Revenue CAGR
                    rev_cagr = None
                    if len(valid_pl) >= 4:
                        # 3 periods of growth (e.g. valid_pl[-4] to valid_pl[-1])
                        s_end = valid_pl[-1][1]
                        s_start = valid_pl[-4][1]
                        if s_start > 0 and s_end > 0:
                            rev_cagr = (s_end / s_start) ** (1/3) - 1
                    elif len(valid_pl) >= 3:
                        s_end = valid_pl[-1][1]
                        s_start = valid_pl[-3][1]
                        if s_start > 0 and s_end > 0:
                            rev_cagr = (s_end / s_start) ** (1/2) - 1
                    elif len(valid_pl) >= 2:
                        s_end = valid_pl[-1][1]
                        s_start = valid_pl[-2][1]
                        if s_start > 0 and s_end > 0:
                            rev_cagr = (s_end / s_start) - 1
                    
                    stock_copy['revenue_cagr_3yr'] = float(rev_cagr * 100) if rev_cagr is not None else None
                    
                    # 3yr NPM Average
                    npm_avg = None
                    last_years = valid_pl[-3:] if len(valid_pl) >= 3 else valid_pl
                    npm_values = []
                    for _, sales, profit in last_years:
                        if sales and profit is not None:
                            npm_values.append(profit / sales)
                    if npm_values:
                        npm_avg = sum(npm_values) / len(npm_values)
                    
                    stock_copy['npm_avg_3yr'] = float(npm_avg * 100) if npm_avg is not None else None
                    
                    # 3yr Stock Price Performance
                    price_perf_3y = None
                    prices = all_prices.get(ticker)
                    if prices is not None and len(prices) > 0:
                        p_latest = prices.iloc[-1]
                        p_3y = prices.iloc[-156] if len(prices) >= 156 else prices.iloc[0]
                        if p_3y > 0:
                            price_perf_3y = (p_latest / p_3y) - 1
                    
                    stock_copy['price_perf_3yr'] = float(price_perf_3y * 100) if price_perf_3y is not None else None
                    
                    undervalued_stocks.append(stock_copy)
                    print(f"  [Undervalued] {ticker} - Sharpe: {stock['expected_sharpe']:.2f}, Upside: {upside:.1f}%")
        except Exception as e:
            # Silently skip single ticker prediction failures
            pass
            
    db_conn.close()
    print(f"\nCompleted evaluation. Found {len(undervalued_stocks)} undervalued stocks.")

except Exception as e:
    print(f"Error during valuation filtering: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    # Restore CWD
    os.chdir(str(ORIGINAL_CWD))

# 7. Write Results to data/screened_stocks.json
output_data = {
    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "stocks": undervalued_stocks
}

try:
    with open(output_json_path, 'w') as f:
        json.dump(output_data, f, indent=4)
    print(f"\nSuccessfully wrote {len(undervalued_stocks)} screened stocks to {output_json_path}")
except Exception as e:
    print(f"Error writing output JSON: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("MASS SCREENING PROCESS COMPLETE")
print("="*60)
