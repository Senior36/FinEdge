# ============================================================
# src/step3_fetch_prices.py
#
# PURPOSE:
#   Downloads full historical price data for all 100 stocks
#   Uses Yahoo Finance (free, no API key needed)
#   Saves one CSV per stock in data/raw/prices/
#
#   IMPORTANT: Price data is used ONLY to calculate the target
#   variable (did the stock go up 6 months later?).
#   It is NEVER used as a model feature — that would be cheating.
#
# RUN:
#   python src/step3_fetch_prices.py
#
# OUTPUT:
#   data/raw/prices/TSLA.csv
#   data/raw/prices/META.csv
#   ... (one file per stock, columns: Date, Open, High, Low, Close, Volume)
# ============================================================

import yfinance as yf
import pandas as pd
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import UNIVERSE, DATA_RAW_PRICE, MIN_QUARTERS

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────
SLEEP_BETWEEN_CALLS = 0.3    # seconds between downloads
MIN_ROWS = MIN_QUARTERS * 63 # minimum trading days needed
                             # (MIN_QUARTERS quarters × ~63 trading days per quarter)

# ─────────────────────────────────────────────────────────────
# FUNCTION: Download price history for one ticker
# ─────────────────────────────────────────────────────────────
def fetch_prices(ticker):
    """
    Downloads maximum available price history from Yahoo Finance.
    Returns a cleaned DataFrame or None if failed/insufficient data.

    Uses period="max" to get everything Yahoo has — could go back
    to the 1980s for older stocks like MSFT, KO, JNJ etc.
    Newer stocks like SNOW, LYFT will have less history — that is fine.
    """
    try:
        ticker_obj = yf.Ticker(ticker)

        # period="max" = get everything available
        df = ticker_obj.history(period="max", auto_adjust=True)

        if df is None or len(df) == 0:
            return None, "No data returned"

        # Remove timezone info from index (causes issues later)
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df.index.name = "Date"

        # Keep only the columns we need
        cols_to_keep = [c for c in ["Open", "High", "Low", "Close", "Volume"]
                        if c in df.columns]
        df = df[cols_to_keep]

        # Remove rows where Close price is missing or zero
        df = df[df["Close"].notna() & (df["Close"] > 0)]

        # Check we have enough history
        if len(df) < MIN_ROWS:
            return None, f"Only {len(df)} rows (need {MIN_ROWS})"

        return df, "ok"

    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────
# FUNCTION: Check already downloaded
# ─────────────────────────────────────────────────────────────
def already_downloaded():
    existing = set()
    for fname in os.listdir(DATA_RAW_PRICE):
        if fname.endswith(".csv"):
            existing.add(fname.replace(".csv", ""))
    return existing


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("STEP 3: Fetching Price History from Yahoo Finance")
    print("=" * 55)
    print(f"Total stocks : {len(UNIVERSE)}")
    print(f"Period       : Maximum available history per stock")
    print(f"Saving to    : {DATA_RAW_PRICE}")
    print()

    done     = already_downloaded()
    to_fetch = [t for t in UNIVERSE if t not in done]

    if done:
        print(f"Already downloaded : {len(done)} stocks — skipping")
    print(f"Need to download   : {len(to_fetch)} stocks")
    print()

    success  = 0
    failed   = []
    skipped  = []

    for i, ticker in enumerate(to_fetch, 1):
        print(f"[{i:>3}/{len(to_fetch)}]  Fetching {ticker}...", end=" ")

        df, status = fetch_prices(ticker)

        if df is not None:
            # Save to CSV
            out_path = DATA_RAW_PRICE / f"{ticker}.csv"
            df.to_csv(out_path)

            # Calculate date range for confirmation message
            start_date = df.index.min().strftime("%Y-%m-%d")
            end_date   = df.index.max().strftime("%Y-%m-%d")
            years      = round(len(df) / 252, 1)

            print(f"{len(df):,} days  |  {start_date} → {end_date}  ({years} yrs)")
            success += 1

        else:
            print(f"Skipped — {status}")
            skipped.append((ticker, status))

        time.sleep(SLEEP_BETWEEN_CALLS)

    # ─────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────
    total_saved = success + len(done)

    print()
    print("=" * 55)
    print("STEP 3 COMPLETE")
    print("=" * 55)
    print(f"  Successfully downloaded : {total_saved}/{len(UNIVERSE)} stocks")
    print(f"  Newly downloaded        : {success}")
    print(f"  Already existed         : {len(done)}")
    print(f"  Skipped (not enough data): {len(skipped)}")

    if skipped:
        print(f"\n  Skipped tickers:")
        for ticker, reason in skipped:
            print(f"    {ticker:8s} → {reason}")
        print("  These will be excluded from training automatically.")

    # Print a small data coverage table
    print()
    print("  Price data coverage (sample of your 5 target stocks):")
    print(f"  {'Ticker':<8} {'Start Date':<14} {'End Date':<14} {'Years':<8}")
    print(f"  {'-'*8} {'-'*14} {'-'*14} {'-'*8}")

    target_stocks = ["TSLA", "META", "GOOGL", "MSFT", "AAPL"]
    for ticker in target_stocks:
        csv_path = DATA_RAW_PRICE / f"{ticker}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
            start  = df.index.min().strftime("%Y-%m-%d")
            end    = df.index.max().strftime("%Y-%m-%d")
            years  = round(len(df) / 252, 1)
            print(f"  {ticker:<8} {start:<14} {end:<14} {years} yrs")

    total_files = len(list(DATA_RAW_PRICE.glob("*.csv")))
    print(f"\n  CSV files in data/raw/prices/ : {total_files}")

if __name__ == "__main__":
    main()
