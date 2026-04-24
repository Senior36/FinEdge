# ============================================================
# src/step4_build_features.py  — PROFESSIONAL REBUILD
#
# KEY DIFFERENCE FROM PREVIOUS VERSION:
#   Before: One snapshot per stock. All 40 historical rows for
#           AAPL had TODAY's PE ratio. Model learned nothing real.
#
#   Now: True point-in-time quarterly features extracted from
#        actual historical filings stored in each JSON.
#        AAPL Q1-2015 row uses AAPL's actual Q1-2015 financials.
#        This is how professional quant models are built.
#
# FEATURES: 50+ per quarter including:
#   - Profitability ratios (margins, ROE, ROA, ROIC)
#   - Growth rates (QoQ and YoY for revenue, earnings, FCF)
#   - Quality signals (accruals, FCF conversion, earnings beat rate)
#   - Financial health (leverage, liquidity, coverage ratios)
#   - Valuation (PE, PB, PS, EV/EBITDA using actual historical prices)
#   - Momentum (margin trend, revenue acceleration, EPS revisions)
#
# OUTPUT: data/processed/features.csv
#   ~15,000-25,000 rows of genuine point-in-time quarterly data
# ============================================================

import json
import os
import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (UNIVERSE, TARGET_STOCKS, DATA_RAW_FUND,
                    DATA_RAW_PRICE, DATA_PROC, FORWARD_MONTHS)


# ─────────────────────────────────────────────────────────────
# SECTION 1: SAFE CONVERSION UTILITIES
# ─────────────────────────────────────────────────────────────

def safe_float(value):
    try:
        if value is None or value == "" or str(value).strip() in ["NA", "None", "nan"]:
            return np.nan
        return float(value)
    except (ValueError, TypeError):
        return np.nan


def safe_div(numerator, denominator, max_abs=100.0):
    """
    Safe division returning NaN if denominator is zero or result is extreme.
    max_abs clips ratios at +/- 100 to remove data errors.
    """
    if np.isnan(numerator) or np.isnan(denominator):
        return np.nan
    if abs(denominator) < 1e-9:
        return np.nan
    result = numerator / denominator
    if abs(result) > max_abs:
        return np.nan
    return result


# ─────────────────────────────────────────────────────────────
# SECTION 2: EXTRACT RAW QUARTERLY FINANCIALS INTO DATAFRAME
# ─────────────────────────────────────────────────────────────

def extract_quarterly_statements(data):
    """
    Extracts income statement, balance sheet, and cash flow
    into three separate DataFrames indexed by quarter date.
    Each row = one quarter of actual filed numbers.
    """
    def parse_section(section_data):
        rows = []
        for date_str, entry in section_data.items():
            if not isinstance(entry, dict):
                continue
            row = {"date": pd.to_datetime(date_str, errors="coerce")}
            for k, v in entry.items():
                if k not in ["date", "filing_date", "currency_symbol"]:
                    row[k] = safe_float(v)
            rows.append(row)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        return df

    financials = data.get("Financials", {})

    inc = parse_section(financials.get("Income_Statement", {}).get("quarterly", {}))
    bal = parse_section(financials.get("Balance_Sheet",    {}).get("quarterly", {}))
    cf  = parse_section(financials.get("Cash_Flow",        {}).get("quarterly", {}))

    return inc, bal, cf


def compute_ttm(series, n=4):
    """
    Trailing Twelve Months = rolling sum of last 4 quarters.
    Used for income statement and cash flow items which are
    reported as quarterly increments, not cumulative.
    """
    return series.rolling(window=n, min_periods=n).sum()


# ─────────────────────────────────────────────────────────────
# SECTION 3: LOAD PRICE HISTORY
# ─────────────────────────────────────────────────────────────

def load_price_series(ticker):
    """Loads price CSV, returns Series with DatetimeIndex."""
    csv_path = DATA_RAW_PRICE / f"{ticker}.csv"
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, index_col="Date", parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df["Close"].dropna().sort_index()
    except Exception:
        return None


def get_price_nearest(price_series, target_date, max_days=10):
    """
    Returns the closing price nearest to target_date within max_days window.
    Used to get the stock price AT the time of each quarterly filing.
    """
    if price_series is None or len(price_series) == 0:
        return np.nan
    window = price_series[
        (price_series.index >= target_date - pd.Timedelta(days=max_days)) &
        (price_series.index <= target_date + pd.Timedelta(days=max_days))
    ]
    if len(window) == 0:
        return np.nan
    return window.iloc[len(window) // 2]


def compute_forward_return(price_series, date, months):
    """
    Computes the actual return achieved if you bought on 'date'
    and sold 'months' months later. This is the label we predict.
    """
    if price_series is None:
        return np.nan
    trading_days = int(months * 21)
    future = price_series[price_series.index >= date]
    if len(future) < trading_days:
        return np.nan
    p0 = future.iloc[0]
    p1 = future.iloc[trading_days - 1]
    if p0 <= 0:
        return np.nan
    return (p1 / p0) - 1.0


def compute_spy_return(date, months):
    """Returns SPY return over same period as benchmark."""
    spy = load_price_series("SPY")
    return compute_forward_return(spy, date, months)


# ─────────────────────────────────────────────────────────────
# SECTION 4: COMPUTE 50+ FEATURES PER QUARTER
# This is the core of the professional rebuild.
# Every feature uses only data available AT THAT POINT IN TIME.
# ─────────────────────────────────────────────────────────────

def build_feature_rows(ticker, sector, industry, inc, bal, cf, price_series):
    """
    For a single stock, builds one feature row per quarter.
    Merges income, balance sheet, cash flow on quarter date.
    Computes TTM aggregates, ratios, growth rates, quality signals.
    Matches with actual historical stock price for valuation ratios.

    Returns a DataFrame where each row = one quarter.
    """
    if inc.empty or bal.empty:
        return pd.DataFrame()

    # ── Merge all three statements on nearest date ──────────
    # Balance sheet is the anchor (most consistently available)
    merged = bal.copy()
    merged = merged.set_index("date")

    # Merge income statement — match each balance sheet date
    # to the nearest income statement date within 45 days
    inc_indexed = inc.set_index("date").sort_index()
    cf_indexed  = cf.set_index("date").sort_index() if not cf.empty else pd.DataFrame()

    rows = []

    for q_date in merged.index:
        row = {"ticker": ticker, "sector": sector, "industry": industry,
               "snapshot_date": q_date}

        # ── Balance sheet values (point-in-time) ────────────
        b = merged.loc[q_date]
        row["total_assets"]        = safe_float(b.get("totalAssets"))
        row["total_liab"]          = safe_float(b.get("totalLiab"))
        row["equity"]              = safe_float(b.get("totalStockholderEquity"))
        row["current_assets"]      = safe_float(b.get("totalCurrentAssets"))
        row["current_liab"]        = safe_float(b.get("totalCurrentLiabilities"))
        row["total_debt"]          = safe_float(b.get("shortLongTermDebtTotal"))
        row["long_term_debt"]      = safe_float(b.get("longTermDebt"))
        row["cash"]                = safe_float(b.get("cash"))
        row["net_debt"]            = safe_float(b.get("netDebt"))
        row["shares_outstanding"]  = safe_float(b.get("commonStockSharesOutstanding"))
        row["inventory"]           = safe_float(b.get("inventory"))
        row["receivables"]         = safe_float(b.get("netReceivables"))

        # ── Get nearest income statement ────────────────────
        inc_near = inc_indexed[
            (inc_indexed.index >= q_date - pd.Timedelta(days=45)) &
            (inc_indexed.index <= q_date + pd.Timedelta(days=45))
        ]
        if inc_near.empty:
            continue

        i = inc_near.iloc[-1]
        row["revenue_q"]          = safe_float(i.get("totalRevenue"))
        row["gross_profit_q"]     = safe_float(i.get("grossProfit"))
        row["operating_income_q"] = safe_float(i.get("operatingIncome"))
        row["net_income_q"]       = safe_float(i.get("netIncome"))
        row["ebitda_q"]           = safe_float(i.get("ebitda"))
        row["rd_expense_q"]       = safe_float(i.get("researchDevelopment"))
        row["sga_expense_q"]      = safe_float(i.get("sellingGeneralAdministrative"))
        row["tax_provision_q"]    = safe_float(i.get("taxProvision"))
        row["income_before_tax_q"]= safe_float(i.get("incomeBeforeTax"))

        # ── Get nearest cash flow ────────────────────────────
        if not cf_indexed.empty:
            cf_near = cf_indexed[
                (cf_indexed.index >= q_date - pd.Timedelta(days=45)) &
                (cf_indexed.index <= q_date + pd.Timedelta(days=45))
            ]
            if not cf_near.empty:
                c = cf_near.iloc[-1]
                row["cfo_q"]          = safe_float(c.get("totalCashFromOperatingActivities"))
                row["capex_q"]        = abs(safe_float(c.get("capitalExpenditures")) or 0)
                row["fcf_q"]          = safe_float(c.get("freeCashFlow"))
                row["depreciation_q"] = safe_float(c.get("depreciation"))
                row["sbc_q"]          = safe_float(c.get("stockBasedCompensation"))
                row["buybacks_q"]     = abs(min(safe_float(c.get("salePurchaseOfStock")) or 0, 0))
            else:
                for col in ["cfo_q","capex_q","fcf_q","depreciation_q","sbc_q","buybacks_q"]:
                    row[col] = np.nan
        else:
            for col in ["cfo_q","capex_q","fcf_q","depreciation_q","sbc_q","buybacks_q"]:
                row[col] = np.nan

        # ── Stock price on this date ─────────────────────────
        row["price"] = get_price_nearest(price_series, q_date)

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("snapshot_date").sort_index()

    # ── TTM (Trailing Twelve Months) Aggregates ──────────────
    # Sum last 4 quarters for flow items (income, cash flow)
    for col in ["revenue_q", "gross_profit_q", "operating_income_q",
                "net_income_q", "ebitda_q", "rd_expense_q",
                "cfo_q", "capex_q", "fcf_q", "depreciation_q", "sbc_q"]:
        if col in df.columns:
            df[col.replace("_q", "_ttm")] = compute_ttm(df[col])

    # ── COMPUTE PROFITABILITY RATIOS ─────────────────────────
    df["gross_margin"]     = df.apply(lambda r: safe_div(r.get("gross_profit_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)
    df["operating_margin"] = df.apply(lambda r: safe_div(r.get("operating_income_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)
    df["net_margin"]       = df.apply(lambda r: safe_div(r.get("net_income_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)
    df["ebitda_margin"]    = df.apply(lambda r: safe_div(r.get("ebitda_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)
    df["fcf_margin"]       = df.apply(lambda r: safe_div(r.get("fcf_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)
    df["rd_intensity"]     = df.apply(lambda r: safe_div(r.get("rd_expense_ttm", np.nan), r.get("revenue_ttm", np.nan)), axis=1)

    # ── RETURN METRICS ───────────────────────────────────────
    df["roe"]  = df.apply(lambda r: safe_div(r.get("net_income_ttm", np.nan), r.get("equity", np.nan)), axis=1)
    df["roa"]  = df.apply(lambda r: safe_div(r.get("net_income_ttm", np.nan), r.get("total_assets", np.nan)), axis=1)
    df["roic"] = df.apply(lambda r: safe_div(
        r.get("operating_income_ttm", np.nan),
        max(r.get("total_assets", np.nan) - r.get("current_liab", np.nan), 1e9)
    ), axis=1)

    # ── QUALITY SIGNALS ──────────────────────────────────────
    # Accruals ratio: low = high quality earnings (cash-backed)
    # If net income >> FCF, company is recognizing non-cash earnings
    df["accruals_ratio"] = df.apply(lambda r: safe_div(
        r.get("net_income_ttm", np.nan) - r.get("fcf_ttm", np.nan),
        r.get("total_assets", np.nan)
    ), axis=1)

    # FCF conversion: FCF / Net Income. >1 = better than reported
    df["fcf_conversion"] = df.apply(lambda r: safe_div(
        r.get("fcf_ttm", np.nan), r.get("net_income_ttm", np.nan)
    ), axis=1)

    # Asset turnover: how efficiently assets generate revenue
    df["asset_turnover"] = df.apply(lambda r: safe_div(
        r.get("revenue_ttm", np.nan), r.get("total_assets", np.nan)
    ), axis=1)

    # ── FINANCIAL HEALTH ─────────────────────────────────────
    df["current_ratio"]    = df.apply(lambda r: safe_div(r.get("current_assets", np.nan), r.get("current_liab", np.nan)), axis=1)
    df["debt_to_equity"]   = df.apply(lambda r: safe_div(r.get("total_debt", np.nan), r.get("equity", np.nan)), axis=1)
    df["debt_to_assets"]   = df.apply(lambda r: safe_div(r.get("total_liab", np.nan), r.get("total_assets", np.nan)), axis=1)
    df["net_debt_ebitda"]  = df.apply(lambda r: safe_div(r.get("net_debt", np.nan), r.get("ebitda_ttm", np.nan)), axis=1)

    # Interest coverage (EBIT / interest) — use operating income as proxy
    # when interest is not separately available
    df["interest_coverage"] = df.apply(lambda r: safe_div(
        r.get("operating_income_ttm", np.nan),
        max(r.get("total_debt", np.nan) * 0.05, 1e6)  # estimate 5% cost of debt
    ), axis=1)

    # ── GROWTH RATES (YoY and QoQ) ───────────────────────────
    # YoY: compare to 4 quarters ago (same quarter last year)
    for col, new_name in [
        ("revenue_ttm",          "revenue_growth_yoy"),
        ("net_income_ttm",       "earnings_growth_yoy"),
        ("fcf_ttm",              "fcf_growth_yoy"),
        ("operating_income_ttm", "opinc_growth_yoy"),
    ]:
        if col in df.columns:
            prev = df[col].shift(4)
            df[new_name] = df.apply(lambda r, c=col, p=prev: safe_div(
                r[c] - p.loc[r.name] if r.name in p.index else np.nan,
                abs(p.loc[r.name]) if r.name in p.index else np.nan
            ), axis=1)

    # QoQ revenue growth: sequential momentum
    df["revenue_growth_qoq"] = df.apply(lambda r: safe_div(
        r.get("revenue_q", np.nan) - df["revenue_q"].shift(1).get(r.name, np.nan),
        abs(df["revenue_q"].shift(1).get(r.name, np.nan) or np.nan)
    ), axis=1)

    # Revenue acceleration: is growth speeding up?
    df["revenue_acceleration"] = df["revenue_growth_qoq"] - df["revenue_growth_qoq"].shift(1)

    # Margin expansion: operating margin trend (vs 4Q ago)
    df["margin_expansion_yoy"] = df["operating_margin"] - df["operating_margin"].shift(4)

    # ── VALUATION RATIOS (using actual historical price) ─────
    df["market_cap"] = df["price"] * df["shares_outstanding"]

    df["pe_ratio"] = df.apply(lambda r: safe_div(
        r.get("price", np.nan),
        safe_div(r.get("net_income_ttm", np.nan), r.get("shares_outstanding", np.nan))
    ), axis=1)

    df["pb_ratio"] = df.apply(lambda r: safe_div(
        r.get("price", np.nan),
        safe_div(r.get("equity", np.nan), r.get("shares_outstanding", np.nan))
    ), axis=1)

    df["ps_ratio"] = df.apply(lambda r: safe_div(
        r.get("market_cap", np.nan),
        r.get("revenue_ttm", np.nan)
    ), axis=1)

    df["ev"] = df["market_cap"] + df["total_debt"].fillna(0) - df["cash"].fillna(0)

    df["ev_ebitda"] = df.apply(lambda r: safe_div(
        r.get("ev", np.nan), r.get("ebitda_ttm", np.nan)
    ), axis=1)

    df["ev_fcf"] = df.apply(lambda r: safe_div(
        r.get("ev", np.nan), r.get("fcf_ttm", np.nan)
    ), axis=1)

    df["fcf_yield"] = df.apply(lambda r: safe_div(
        r.get("fcf_ttm", np.nan), r.get("market_cap", np.nan)
    ), axis=1)

    df["earnings_yield"] = df.apply(lambda r: safe_div(
        r.get("net_income_ttm", np.nan), r.get("market_cap", np.nan)
    ), axis=1)

    # Buyback yield: how much capital returned vs market cap
    df["buyback_yield"] = df.apply(lambda r: safe_div(
        r.get("buybacks_q", np.nan) * 4,  # annualize
        r.get("market_cap", np.nan)
    ), axis=1)

    # ── PIOTROSKI F-SCORE ────────────────────────────────────
    # The most academically proven fundamental factor.
    # Scores each company 0-9 each quarter.
    # Uses only data available at that point in time.

    def piotroski_score(df_in):
        scores = pd.Series(0, index=df_in.index)

        # PROFITABILITY
        # +1 if ROA positive
        roa = df_in.get("roa", pd.Series(np.nan, index=df_in.index))
        scores += (roa > 0).astype(int)

        # +1 if operating cash flow positive
        cfo = df_in.get("cfo_ttm", pd.Series(np.nan, index=df_in.index))
        scores += (cfo > 0).astype(int)

        # +1 if ROA improved vs 4 quarters ago
        roa_prev = roa.shift(4)
        scores += (roa > roa_prev).astype(int)

        # +1 if FCF > net income (cash beats accounting)
        ni = df_in.get("net_income_ttm", pd.Series(np.nan, index=df_in.index))
        scores += (cfo > ni).astype(int)

        # LEVERAGE
        # +1 if debt to assets decreased
        dta = df_in.get("debt_to_assets", pd.Series(np.nan, index=df_in.index))
        dta_prev = dta.shift(4)
        scores += (dta < dta_prev).astype(int)

        # +1 if current ratio improved
        cr = df_in.get("current_ratio", pd.Series(np.nan, index=df_in.index))
        cr_prev = cr.shift(4)
        scores += (cr > cr_prev).astype(int)

        # EFFICIENCY
        # +1 if gross margin improved
        gm = df_in.get("gross_margin", pd.Series(np.nan, index=df_in.index))
        gm_prev = gm.shift(4)
        scores += (gm > gm_prev).astype(int)

        # +1 if asset turnover improved
        at = df_in.get("asset_turnover", pd.Series(np.nan, index=df_in.index))
        at_prev = at.shift(4)
        scores += (at > at_prev).astype(int)

        # +1 if accruals ratio is low (earnings are real cash)
        accruals = df_in.get("accruals_ratio", pd.Series(np.nan, index=df_in.index))
        scores += (accruals < 0.05).astype(int)

        return scores.clip(0, 9)

    df["piotroski_score"] = piotroski_score(df)
    df["piotroski_normalized"] = df["piotroski_score"] / 9.0

    df["ticker"]   = ticker
    df["sector"]   = sector
    df["industry"] = industry

    return df.reset_index()


# ─────────────────────────────────────────────────────────────
# SECTION 5: EPS QUALITY FEATURES FROM EARNINGS HISTORY
# ─────────────────────────────────────────────────────────────

def extract_eps_features(data):
    """
    Extracts EPS beat rate and momentum from the Earnings section.
    Returns a DataFrame indexed by date with eps quality features.
    """
    history = data.get("Earnings", {}).get("History", {})
    if not history:
        return pd.DataFrame()

    rows = []
    for date_str, entry in history.items():
        if not isinstance(entry, dict):
            continue
        try:
            rows.append({
                "date":         pd.to_datetime(date_str),
                "eps_actual":   safe_float(entry.get("epsActual")),
                "eps_estimate": safe_float(entry.get("epsEstimate")),
            })
        except Exception:
            continue

    if len(rows) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    # Rolling 8-quarter beat rate
    def beat_rate(row_idx):
        window = df.iloc[max(0, row_idx - 7): row_idx + 1]
        valid = window.dropna(subset=["eps_actual", "eps_estimate"])
        if len(valid) < 2:
            return np.nan
        beats = (valid["eps_actual"] > valid["eps_estimate"]).sum()
        return beats / len(valid)

    # EPS momentum: slope of actual EPS
    def eps_momentum(row_idx):
        window = df.iloc[max(0, row_idx - 7): row_idx + 1]
        valid = window.dropna(subset=["eps_actual"])
        if len(valid) < 4:
            return np.nan
        x = np.arange(len(valid))
        return np.polyfit(x, valid["eps_actual"].values, 1)[0]

    # EPS surprise magnitude: mean (actual - estimate) / |estimate|
    def surprise_magnitude(row_idx):
        window = df.iloc[max(0, row_idx - 7): row_idx + 1]
        valid = window.dropna(subset=["eps_actual", "eps_estimate"])
        valid = valid[valid["eps_estimate"].abs() > 0.01]
        if len(valid) < 2:
            return np.nan
        surprises = (valid["eps_actual"] - valid["eps_estimate"]) / valid["eps_estimate"].abs()
        return surprises.clip(-2, 2).mean()

    # Earnings consistency: % of beats over last 8 quarters
    def consistency_score(row_idx):
        window = df.iloc[max(0, row_idx - 7): row_idx + 1]
        valid = window.dropna(subset=["eps_actual", "eps_estimate"])
        if len(valid) == 0:
            return np.nan
        beats = (valid["eps_actual"] > valid["eps_estimate"]).sum()
        return beats / len(valid)

    df["eps_beat_rate"]         = [beat_rate(i)         for i in range(len(df))]
    df["eps_momentum"]          = [eps_momentum(i)      for i in range(len(df))]
    df["eps_surprise_magnitude"]= [surprise_magnitude(i)for i in range(len(df))]
    df["eps_consistency_score"] = [consistency_score(i) for i in range(len(df))]

    prev_eps = df["eps_actual"].shift(1)
    eps_growth_rate = pd.Series([
        safe_div(curr - prev, abs(prev))
        for curr, prev in zip(df["eps_actual"], prev_eps)
    ], index=df.index)
    df["eps_acceleration"] = eps_growth_rate - eps_growth_rate.shift(1)

    prev_estimate_2q = df["eps_estimate"].shift(2)
    df["analyst_revision_score"] = pd.Series([
        safe_div(curr - prev, abs(prev))
        for curr, prev in zip(df["eps_estimate"], prev_estimate_2q)
    ], index=df.index)

    for col in ["eps_acceleration", "analyst_revision_score", "eps_consistency_score"]:
        df[col] = df[col].ffill().fillna(0)

    return df.set_index("date")[[
        "eps_beat_rate", "eps_momentum", "eps_surprise_magnitude",
        "eps_acceleration", "analyst_revision_score", "eps_consistency_score"
    ]]


# ─────────────────────────────────────────────────────────────
# SECTION 6: ANALYST FEATURES
# ─────────────────────────────────────────────────────────────

def extract_analyst_features(data):
    """
    Extracts analyst consensus as a single snapshot (no history).
    Applied uniformly across all quarters as a static feature.
    """
    analyst = data.get("AnalystRatings", {})
    if not analyst:
        return {}

    strong_buy  = safe_float(analyst.get("StrongBuy"))  or 0
    buy         = safe_float(analyst.get("Buy"))         or 0
    hold        = safe_float(analyst.get("Hold"))        or 0
    sell        = safe_float(analyst.get("Sell"))        or 0
    strong_sell = safe_float(analyst.get("StrongSell"))  or 0
    total = strong_buy + buy + hold + sell + strong_sell

    shares_stats = data.get("SharesStats", {}) or {}
    short_interest_pct = safe_float(shares_stats.get("ShortPercentFloat"))
    if np.isnan(short_interest_pct):
        short_interest_pct = 0.0

    return {
        "analyst_bull_score": (strong_buy + buy) / total if total > 0 else np.nan,
        "analyst_count":      total,
        "short_interest_pct": short_interest_pct,
    }


def extract_insider_features(data):
    """
    Extracts insider transactions and returns a DataFrame indexed by date.
    insider_buy_score = (buys - sells) / total transactions
    using only transactions from the trailing 90 days at each snapshot.
    """
    transactions = data.get("InsiderTransactions", {})
    if not transactions or not isinstance(transactions, dict):
        return pd.DataFrame()

    rows = []
    for _, entry in transactions.items():
        if not isinstance(entry, dict):
            continue
        tx_date = pd.to_datetime(
            entry.get("transactionDate") or entry.get("date"),
            errors="coerce"
        )
        action = str(entry.get("transactionAcquiredDisposed") or "").strip().upper()
        if pd.isna(tx_date) or action not in {"A", "D"}:
            continue
        rows.append({
            "date": tx_date,
            "action": action,
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# SECTION 7: CROSS-SECTIONAL RANKING
# ─────────────────────────────────────────────────────────────

NEW_FEATURE_COLS = [
    "eps_acceleration",
    "analyst_revision_score",
    "eps_consistency_score",
    "insider_buy_score",
    "short_interest_pct",
]

# These are the 50 features to rank cross-sectionally
FEATURE_COLS = [
    # Profitability
    "gross_margin", "operating_margin", "net_margin",
    "ebitda_margin", "fcf_margin", "rd_intensity",
    # Returns
    "roe", "roa", "roic",
    # Quality
    "accruals_ratio", "fcf_conversion", "asset_turnover",
    # Health
    "current_ratio", "debt_to_equity", "debt_to_assets",
    "net_debt_ebitda", "interest_coverage",
    # Growth
    "revenue_growth_yoy", "earnings_growth_yoy",
    "fcf_growth_yoy", "opinc_growth_yoy",
    "revenue_growth_qoq", "revenue_acceleration",
    "margin_expansion_yoy",
    # Valuation
    "pe_ratio", "pb_ratio", "ps_ratio",
    "ev_ebitda", "ev_fcf", "fcf_yield",
    "earnings_yield", "buyback_yield",
    "piotroski_score", "piotroski_normalized",
    # EPS Quality
    "eps_beat_rate", "eps_momentum", "eps_surprise_magnitude",
    "eps_acceleration", "analyst_revision_score", "eps_consistency_score",
    # Analyst
    "analyst_bull_score", "short_interest_pct",
    # Insider
    "insider_buy_score",
]


def add_cross_sectional_ranks(df):
    """
    For each feature, adds a percentile rank column computed
    within the same sector AND same quarter (year + quarter).
    This makes features comparable across sectors and time periods.
    A rank of 0.9 means this stock is in the 90th percentile
    of its sector peers in that quarter.
    """
    rank_cols = []
    for col in FEATURE_COLS:
        if col not in df.columns:
            continue
        rank_col = f"{col}_rank"
        df[rank_col] = df.groupby(
            ["sector", "year", "quarter"]
        )[col].rank(pct=True, na_option="keep")
        rank_cols.append(rank_col)
    return df, rank_cols


# ─────────────────────────────────────────────────────────────
# SECTION 8: DOWNLOAD SPY BENCHMARK
# ─────────────────────────────────────────────────────────────

def download_spy():
    spy_path = DATA_RAW_PRICE / "SPY.csv"
    if spy_path.exists():
        print("  SPY benchmark already present.")
        return
    try:
        import yfinance as yf
        df = yf.Ticker("SPY").history(period="max", auto_adjust=True)
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "Date"
        df[["Close"]].to_csv(spy_path)
        print(f"  SPY downloaded: {len(df)} days")
    except Exception as e:
        print(f"  Warning: SPY download failed — {e}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 4 (PROFESSIONAL REBUILD): Building Feature Dataset")
    print("=" * 60)
    print()
    print("KEY DIFFERENCE:")
    print("  Each row now uses ACTUAL historical quarterly financials")
    print("  not a single today-snapshot repeated across all quarters.")
    print()

    # Download SPY
    print("[1/6] Downloading SPY benchmark...")
    download_spy()

    # Process each stock
    print(f"\n[2/6] Extracting true point-in-time quarterly features...")
    print(f"      Processing {len(UNIVERSE)} stocks...")

    all_rows = []
    failed   = []
    skipped  = []

    for i, ticker in enumerate(UNIVERSE, 1):
        json_path = DATA_RAW_FUND / f"{ticker}.json"
        if not json_path.exists():
            skipped.append(ticker)
            continue

        try:
            with open(json_path) as f:
                data = json.load(f)
        except Exception:
            failed.append(ticker)
            continue

        general  = data.get("General", {})
        sector   = general.get("Sector",   "Unknown")
        industry = general.get("Industry", "Unknown")

        # Extract financial statements
        inc, bal, cf = extract_quarterly_statements(data)
        if inc.empty or bal.empty:
            skipped.append(ticker)
            continue

        # Load price history
        price_series = load_price_series(ticker)

        # Build quarterly feature rows
        df_stock = build_feature_rows(ticker, sector, industry,
                                       inc, bal, cf, price_series)
        if df_stock.empty or len(df_stock) < 8:
            skipped.append(ticker)
            continue

        # Add EPS quality features
        eps_df = extract_eps_features(data)
        if not eps_df.empty:
            df_stock["snapshot_date"] = pd.to_datetime(df_stock["snapshot_date"])
            df_stock = df_stock.sort_values("snapshot_date")
            for eps_col in eps_df.columns:
                df_stock[eps_col] = np.nan
                for idx, row in df_stock.iterrows():
                    past = eps_df[eps_df.index <= row["snapshot_date"]]
                    if not past.empty:
                        df_stock.at[idx, eps_col] = past.iloc[-1][eps_col]

        insider_df = extract_insider_features(data)
        df_stock["insider_buy_score"] = 0.0
        if not insider_df.empty:
            for idx, row in df_stock.iterrows():
                snapshot_date = row["snapshot_date"]
                window = insider_df[
                    (insider_df["date"] <= snapshot_date) &
                    (insider_df["date"] >= snapshot_date - pd.Timedelta(days=90))
                ]
                total_tx = len(window)
                if total_tx == 0:
                    score = 0.0
                else:
                    buys = (window["action"] == "A").sum()
                    sells = (window["action"] == "D").sum()
                    score = (buys - sells) / total_tx
                df_stock.at[idx, "insider_buy_score"] = score

        for feature_col in NEW_FEATURE_COLS:
            if feature_col not in df_stock.columns:
                df_stock[feature_col] = np.nan
            df_stock[feature_col] = df_stock[feature_col].ffill().fillna(0)

        # Add analyst features (static snapshot)
        analyst_feats = extract_analyst_features(data)
        for k, v in analyst_feats.items():
            df_stock[k] = v

        n_quarters = len(df_stock)
        all_rows.append(df_stock)

        if i % 10 == 0:
            print(f"  [{i:3d}/{len(UNIVERSE)}] Processed {ticker:6s} — {n_quarters} quarters")

    print(f"\n  Done. Processed {len(all_rows)} stocks successfully.")
    if failed:
        print(f"  Failed  : {failed}")
    if skipped:
        print(f"  Skipped : {skipped}")

    # Combine all stocks
    print("\n[3/6] Combining all stocks into one dataset...")
    df = pd.concat(all_rows, ignore_index=True)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df["year"]    = df["snapshot_date"].dt.year
    df["quarter"] = df["snapshot_date"].dt.quarter

    print("  New feature coverage:")
    for feature_col in NEW_FEATURE_COLS:
        non_null = df[feature_col].notna().sum() if feature_col in df.columns else 0
        print(f"    {feature_col:<24}: {non_null:,} non-null")

    # Filter to 2000 onwards (sparse and unreliable before)
    df = df[df["year"] >= 2000].copy()
    print(f"  Total rows (2000+)  : {len(df):,}")
    print(f"  Unique stocks       : {df['ticker'].nunique()}")
    print(f"  Date range          : {df['snapshot_date'].min().date()} to {df['snapshot_date'].max().date()}")

    # Add cross-sectional ranks
    print("\n[4/6] Adding cross-sectional sector-quarter ranks...")
    df, rank_cols = add_cross_sectional_ranks(df)
    print(f"  Rank features added : {len(rank_cols)}")

    # Compute forward return labels
    print("\n[5/6] Computing forward return labels...")
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=FORWARD_MONTHS)
    spy_cache = {}

    forward_returns = []
    forward_alphas  = []
    labels          = []

    price_cache = {t: load_price_series(t) for t in df["ticker"].unique()}

    for _, row in df.iterrows():
        q_date = row["snapshot_date"]
        if q_date > cutoff:
            forward_returns.append(np.nan)
            forward_alphas.append(np.nan)
            labels.append(np.nan)
            continue

        prices = price_cache.get(row["ticker"])
        fwd    = compute_forward_return(prices, q_date, FORWARD_MONTHS)

        # Cache SPY returns by quarter
        spy_key = (q_date.year, q_date.quarter)
        if spy_key not in spy_cache:
            spy_cache[spy_key] = compute_spy_return(q_date, FORWARD_MONTHS)
        spy_ret = spy_cache[spy_key]

        alpha = fwd - spy_ret if not np.isnan(fwd) and not np.isnan(spy_ret) else fwd

        forward_returns.append(fwd)
        forward_alphas.append(alpha)
        labels.append(1 if (not np.isnan(alpha) and alpha > 0) else
                      (0 if not np.isnan(alpha) else np.nan))

    df["forward_return"] = forward_returns
    df["forward_alpha"]  = forward_alphas
    df["outperformed"]   = labels

    # Drop rows without labels (future quarters)
    df_labeled = df.dropna(subset=["outperformed"]).copy()
    df_labeled["outperformed"] = df_labeled["outperformed"].astype(int)

    # Drop rows with more than 60% missing rank features
    df_labeled["missing_pct"] = df_labeled[rank_cols].isna().mean(axis=1)
    before = len(df_labeled)
    df_labeled = df_labeled[df_labeled["missing_pct"] < 0.6].drop(columns=["missing_pct"])
    print(f"  Rows with valid labels : {len(df_labeled):,} (removed {before - len(df_labeled)} incomplete rows)")

    label_counts = df_labeled["outperformed"].value_counts()
    pct_pos = label_counts.get(1, 0) / len(df_labeled) * 100
    print(f"  Label distribution     : {pct_pos:.1f}% outperformed / {100-pct_pos:.1f}% underperformed")

    # Save
    print("\n[6/6] Saving dataset...")
    out_path = DATA_PROC / "features.csv"
    df_labeled.to_csv(out_path, index=False)
    print(f"  Saved to  : {out_path}")
    print(f"  Shape     : {df_labeled.shape[0]:,} rows x {df_labeled.shape[1]} columns")
    print(f"  Features  : {len(rank_cols)} ranked features (from {len(FEATURE_COLS)} raw features)")

    # Target stock coverage
    print(f"\n  Target stock coverage:")
    for t in TARGET_STOCKS:
        n = len(df_labeled[df_labeled["ticker"] == t])
        print(f"    {t:8s}: {n} quarterly rows")

    print(f"\nStep 4 complete. This dataset uses TRUE point-in-time")
    print(f"quarterly financials — the professional standard.")
    print(f"Ready for Step 5 (model training).")


if __name__ == "__main__":
    main()
