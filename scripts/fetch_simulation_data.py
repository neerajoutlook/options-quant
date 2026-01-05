import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

# Mapping of Shoonya Tokens/Symbols to Yahoo Finance Tickers
# Bank Nifty Constituents + Indices
SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "SBIN": "SBIN.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "AXISBANK": "AXISBANK.NS",
    "INDUSINDBK": "INDUSINDBK.NS",
    "AUBANK": "AUBANK.NS",
    "BANDHANBNK": "BANDHANBNK.NS",
    "FEDERALBNK": "FEDERALBNK.NS",
    "IDFCFIRSTB": "IDFCFIRSTB.NS",
    "PNB": "PNB.NS",
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
OUTPUT_FILE = os.path.join(DATA_DIR, "simulation_history.csv")

def fetch_data():
    print("Fetching 1-minute data for simulation...")
    
    # 1. Determine last trading day (approx)
    # We fetch last 5 days to be safe and pick the latest full day
    tickers = list(SYMBOL_MAP.values())
    
    # Fetch data
    # group_by='ticker' ensures we get a MultiIndex if multiple tickers
    df = yf.download(tickers, period="5d", interval="1m", group_by='ticker', progress=False)
    
    if df.empty:
        print("Error: No data fetched.")
        return

    # 2. Extract specific day
    # Get the latest date available in the index
    latest_date = df.index[-1].date()
    print(f"Latest data date: {latest_date}")
    
    # Filter for that date
    day_df = df[df.index.date == latest_date]
    
    # 3. Reshape into long format expected by Simulator
    # We want: timestamp, symbol, close (or ltp)
    # Currently columns are (Ticker, PriceType) e.g. (^NSEBANK, Close)
    
    records = []
    
    # Improve iteration: Iterate by timestamp, then by ticker
    for ts, row in day_df.iterrows():
        # Convert TS to IST if needed (yfinance usually returns localized if requested, or UTC)
        # Assuming UTC from yfinance, convert to IST
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts)
        ts_ist = ts.astimezone(pytz.timezone('Asia/Kolkata'))
        
        # Format: YYYY-MM-DD HH:MM:SS
        ts_str = ts_ist.strftime("%Y-%m-%d %H:%M:%S")
        
        for name, yf_ticker in SYMBOL_MAP.items():
            try:
                # Access price for this ticker
                # row is a Series with MultiIndex (Ticker, PriceType)
                price = row[(yf_ticker, 'Close')]
                if pd.notna(price):
                    records.append({
                        "timestamp": ts_str,
                        "symbol": name,
                        "price": float(price)
                    })
            except KeyError:
                continue

    if not records:
        print("No records found for the latest date.")
        return

    result_df = pd.DataFrame(records)
    
    # Sort by timestamp
    result_df.sort_values("timestamp", inplace=True)
    
    # Save
    os.makedirs(DATA_DIR, exist_ok=True)
    result_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(result_df)} records to {OUTPUT_FILE}")
    print(f"Example:\n{result_df.head()}")

if __name__ == "__main__":
    fetch_data()
