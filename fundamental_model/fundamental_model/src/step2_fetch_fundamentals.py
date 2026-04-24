# ============================================================
# src/step2_fetch_fundamentals.py
#
# PURPOSE:
#   Downloads fundamental data for all 100 stocks from EODHD API
#   Saves one JSON file per stock in data/raw/fundamentals/
#   Safe to stop and re-run — already downloaded files are skipped
#
# RUN:
#   python src/step2_fetch_fundamentals.py
#
# OUTPUT:
#   data/raw/fundamentals/TSLA.json
#   data/raw/fundamentals/META.json
#   ... (one file per stock)
# ============================================================

import requests
import json
import time
import os
import sys

# This makes sure Python can find config.py in the root folder
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EODHD_API_KEY, UNIVERSE, DATA_RAW_FUND

# ─────────────────────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────────────────────
SLEEP_BETWEEN_CALLS = 0.5   # seconds to wait between API calls
                             # 0.5 = 2 calls per second (safe for EODHD limits)
EXCHANGE = "US"              # All our stocks are on US exchanges

# ─────────────────────────────────────────────────────────────
# FUNCTION: Fetch fundamentals for one ticker
# ─────────────────────────────────────────────────────────────
def fetch_fundamentals(ticker):
    """
    Calls EODHD API for one stock.
    Returns the JSON data as a Python dict, or None if it failed.

    The EODHD fundamentals endpoint returns:
    - General info (name, sector, industry, country)
    - Highlights (PE ratio, EPS, profit margins, ROE, ROA etc.)
    - Valuation (EV/EBITDA, EV/Revenue etc.)
    - Financials (income statement, balance sheet, cash flow)
    - Analyst ratings (buy/hold/sell counts, price targets)
    - Earnings history (quarterly EPS over time)
    """
    url = f"https://eodhd.com/api/fundamentals/{ticker}.{EXCHANGE}"
    params = {
        "api_token": EODHD_API_KEY,
        "fmt":       "json"
    }

    try:
        response = requests.get(url, params=params, timeout=30)

        # 200 = success
        if response.status_code == 200:
            data = response.json()

            # Basic validation: must be a dict with General section
            if not isinstance(data, dict):
                print(f" {ticker}: Response is not a dict — skipping")
                return None
            if "General" not in data:
                print(f" {ticker}: No General section — skipping")
                return None

            return data

        # 404 = stock not found on EODHD
        elif response.status_code == 404:
            print(f"{ticker}: Not found on EODHD (404)")
            return None

        # 429 = rate limit hit — wait longer and retry once
        elif response.status_code == 429:
            print(f"{ticker}: Rate limit hit — waiting 10 seconds...")
            time.sleep(10)
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            return None

        else:
            print(f" {ticker}: HTTP {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        print(f" {ticker}: Request timed out")
        return None
    except Exception as e:
        print(f" {ticker}: Unexpected error — {e}")
        return None


# ─────────────────────────────────────────────────────────────
# FUNCTION: Save one ticker's data to JSON file
# ─────────────────────────────────────────────────────────────
def save_json(ticker, data):
    """Saves the API response dict to data/raw/fundamentals/TICKER.json"""
    filepath = DATA_RAW_FUND / f"{ticker}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────
# FUNCTION: Quick check what we already have
# ─────────────────────────────────────────────────────────────
def already_downloaded():
    """Returns a set of tickers already saved as JSON files."""
    existing = set()
    for fname in os.listdir(DATA_RAW_FUND):
        if fname.endswith(".json"):
            existing.add(fname.replace(".json", ""))
    return existing


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("STEP 2: Fetching Fundamental Data from EODHD")
    print("=" * 55)
    print(f"Total stocks to fetch: {len(UNIVERSE)}")
    print(f"Saving to: {DATA_RAW_FUND}")
    print()

    # Check what's already downloaded
    done = already_downloaded()
    to_fetch = [t for t in UNIVERSE if t not in done]

    if done:
        print(f"Already downloaded: {len(done)} stocks — skipping these")
    print(f"Need to download  : {len(to_fetch)} stocks")
    print()

    # Counters for summary
    success = 0
    failed  = []

    # Loop through each stock
    for i, ticker in enumerate(to_fetch, 1):

        print(f"[{i:>3}/{len(to_fetch)}]  Fetching {ticker}...", end=" ")

        data = fetch_fundamentals(ticker)

        if data is not None:
            save_json(ticker, data)

            # Extract sector for confirmation message
            sector = data.get("General", {}).get("Sector", "Unknown")
            name   = data.get("General", {}).get("Name",   ticker)
            print(f" {name} | Sector: {sector}")
            success += 1
        else:
            print(f"Failed")
            failed.append(ticker)

        # Wait between calls to respect API rate limits
        time.sleep(SLEEP_BETWEEN_CALLS)

    # ─────────────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("STEP 2 COMPLETE")
    print("=" * 55)
    print(f"  Successfully downloaded : {success + len(done)}/{len(UNIVERSE)} stocks")
    print(f"  Newly downloaded        : {success}")
    print(f"  Already existed         : {len(done)}")
    print(f"  Failed                  : {len(failed)}")

    if failed:
        print(f"\n  Failed tickers: {failed}")
        print("  These will be excluded from training automatically.")
        print("  Re-run this script to retry failed tickers.")

    total_files = len(list(DATA_RAW_FUND.glob("*.json")))
    print(f"\n  JSON files in data/raw/fundamentals/ : {total_files}")

if __name__ == "__main__":
    main()
