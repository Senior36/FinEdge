# ============================================================
# src/step6_generate_signals.py — INVESTOR-FRIENDLY DASHBOARD
# ============================================================

import os
import sys
import pickle
import warnings
from datetime import date

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    DATA_PROC, OUT_MODELS, OUT_SIGNALS, OUT_PLOTS,
    TARGET_STOCKS, SIGNAL_BUY_RANKS, SIGNAL_SELL_RANKS,
    STRONG_SIGNAL_THRESHOLD,
)


# ─────────────────────────────────────────────────────────────
# PLAIN ENGLISH REASONS — what to tell the investor
# ─────────────────────────────────────────────────────────────
def get_reason(row, signal):
    reasons = []

    # VALUATION — check first, most important for SELL signals
    pe = row.get("pe_ratio_rank", np.nan)
    pb = row.get("pb_ratio_rank", np.nan)
    ev = row.get("ev_ebitda_rank", np.nan)

    if not np.isnan(pe) and pe > 0.75:
        reasons.append("expensive valuation vs peers")
    elif not np.isnan(pb) and pb > 0.75:
        reasons.append("high price-to-book vs peers")
    elif not np.isnan(ev) and ev > 0.75:
        reasons.append("high EV/EBITDA vs peers")

    # EPS MOMENTUM
    eps_mom = row.get("eps_momentum_rank", np.nan)
    if not np.isnan(eps_mom):
        if eps_mom > 0.7:
            reasons.append("earnings trending up strongly")
        elif eps_mom < 0.3:
            reasons.append("earnings trend declining")

    # EPS BEAT RATE
    beat = row.get("eps_beat_rate_rank", np.nan)
    if not np.isnan(beat):
        if beat > 0.7:
            reasons.append("consistently beats expectations")
        elif beat < 0.3:
            reasons.append("frequently misses expectations")

    # DEBT
    dte = row.get("debt_to_equity_rank", np.nan)
    if not np.isnan(dte):
        if dte < 0.25:
            reasons.append("very low debt")
        elif dte > 0.75:
            reasons.append("high debt vs peers")

    # FCF
    fcf = row.get("fcf_conversion_rank", np.nan)
    if not np.isnan(fcf):
        if fcf > 0.7:
            reasons.append("strong cash generation")
        elif fcf < 0.3:
            reasons.append("weak cash generation")

    # REVENUE GROWTH
    rev = row.get("revenue_growth_yoy_rank", np.nan)
    if not np.isnan(rev):
        if rev > 0.7:
            reasons.append("revenue growing fast")
        elif rev < 0.3:
            reasons.append("revenue growth lagging")

    # STRICT FILTER — only show reasons matching signal direction
    if "BUY" in signal:
        positive = [r for r in reasons if any(w in r.lower() for w in
            ["trending up", "beats", "low debt", "strong cash",
             "growing fast", "attractively", "very low debt",
             "consistently beats"])]
        if positive:
            return " & ".join(positive[:2]).capitalize()
        return "Strong fundamentals vs peers"

    if "SELL" in signal or "AVOID" in signal:
        negative = [r for r in reasons if any(w in r.lower() for w in
            ["expensive", "high price", "declining", "misses",
             "weak cash", "lagging", "high debt"])]
        if negative:
            return " & ".join(negative[:2]).capitalize()
        return "Weak fundamentals vs peers"

    # HOLD
    return "Mixed signals — monitor closely"

# ─────────────────────────────────────────────────────────────
# SIGNAL LOGIC
# ─────────────────────────────────────────────────────────────

def make_signal(relative_rank, universe_percentile):
    if relative_rank in SIGNAL_BUY_RANKS:
        return "BUY"
    if relative_rank == 3:
        return "HOLD"
    return "AVOID"


def signal_color(signal):
    return {
        "BUY":   "#1a7a1a",
        "HOLD":  "#8c8c8c",
        "AVOID": "#c0392b",
    }.get(signal, "#8c8c8c")


def signal_display_text(signal, score):
    if signal == "BUY":
        if score >= 0.65:
            return "✅ STRONG BUY"
        else:
            return "✅ BUY"
    if signal == "HOLD":
        return "⏸️  HOLD"
    if signal == "AVOID":
        if score <= 0.38:
            return "❌ STRONG SELL"
        else:
            return "❌ SELL"
    return signal


# ─────────────────────────────────────────────────────────────
# MARKET WARNING — check if conditions are extreme
# ─────────────────────────────────────────────────────────────

def get_market_warning():
    """
    Tries to fetch VIX and oil price to detect market stress.
    Returns a warning string if conditions are extreme.
    """
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(period="2d")["Close"].iloc[-1]
        oil = yf.Ticker("CL=F").history(period="2d")["Close"].iloc[-1]

        warnings_list = []
        if vix > 30:
            warnings_list.append(f"⚠️  Market Fear Index (VIX) = {vix:.0f} — EXTREME FEAR")
        elif vix > 20:
            warnings_list.append(f"⚠️  Market Fear Index (VIX) = {vix:.0f} — ELEVATED RISK")

        if oil > 90:
            warnings_list.append(f"⚠️  Oil Price = ${oil:.0f}/barrel — ENERGY SHOCK ACTIVE")

        if warnings_list:
            warnings_list.append(
                "📌  IMPORTANT: Fundamental signals are based on financial statements.\n"
                "     During geopolitical crises or market shocks, treat all signals\n"
                "     with extra caution. Consider waiting for stability."
            )
            return warnings_list
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────────────────────
# MAIN DASHBOARD CHART
# ─────────────────────────────────────────────────────────────

def build_dashboard(plot_df, warnings_list, today_str, universe_df):
    """
    Builds a clean investor-friendly card dashboard.
    One row per stock showing:
    - Signal badge (color coded)
    - Confidence meter
    - Universe percentile
    - Plain English reason
    """
    n = len(plot_df)
    has_warning = len(warnings_list) > 0

    fig_height = 3.5 + n * 1.6 + (1.5 if has_warning else 0)
    fig, ax = plt.subplots(figsize=(13, fig_height))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, fig_height)
    ax.axis("off")

    # ── Title ────────────────────────────────────────────────
    fig.patch.set_facecolor("#f7f9fc")
    ax.set_facecolor("#f7f9fc")

    ax.text(6.5, fig_height - 0.5,
            "📊  Your Stock Report Card",
            fontsize=18, fontweight="bold", ha="center", va="top",
            color="#1a1a2e")
    ax.text(6.5, fig_height - 1.1,
            f"Based on latest quarterly financial statements  •  Generated {today_str}",
            fontsize=10, ha="center", va="top", color="#555555",
            style="italic")
    ax.text(6.5, fig_height - 1.55,
            "Each stock is scored by reading its financial report card and comparing it to all other stocks.",
            fontsize=9, ha="center", va="top", color="#777777")
    ax.text(6.5, fig_height - 1.85,
            "Green = likely to beat the market over next 6 months  |  Red = likely to underperform",
            fontsize=8, ha="center", va="top", color="#999999")

    y_start = fig_height - 2.2

    # ── Warning Banner ───────────────────────────────────────
    if has_warning:
        warn_box = FancyBboxPatch((0.3, y_start - 1.2), 12.4, 1.1,
                                   boxstyle="round,pad=0.1",
                                   facecolor="#fff3cd", edgecolor="#e6a817",
                                   linewidth=2)
        ax.add_patch(warn_box)
        warning_text = "  ".join(warnings_list[:2])
        ax.text(6.5, y_start - 0.6, warning_text,
                fontsize=9, ha="center", va="center",
                color="#856404", fontweight="bold", wrap=True)
        y_start -= 1.5

    # ── Column Headers ───────────────────────────────────────
    ax.text(1.0,  y_start, "STOCK",       fontsize=9, color="#888888", fontweight="bold")
    ax.text(3.2,  y_start, "SIGNAL",      fontsize=9, color="#888888", fontweight="bold")
    ax.text(5.8, y_start,   "MODEL CONFIDENCE", fontsize=9, color="#888888", fontweight="bold")
    ax.text(5.8, y_start - 0.22, "(how sure the model is)", fontsize=7, color="#aaaaaa")
    ax.text(10.0, y_start, "UNIVERSE RANK", fontsize=9, color="#888888", fontweight="bold")
    ax.text(11.9, y_start,   "WHY THIS SIGNAL?", fontsize=9, color="#888888", fontweight="bold")

    ax.axhline(y=y_start - 0.15, xmin=0.02, xmax=0.98,
               color="#cccccc", linewidth=1)

    y_start -= 0.35

    # ── Stock Cards ──────────────────────────────────────────
    for i, (_, row) in enumerate(plot_df.sort_values("relative_rank").iterrows()):
        y = y_start - i * 1.45
        card_color = "#ffffff" if i % 2 == 0 else "#f0f4f8"

        # Card background
        card = FancyBboxPatch((0.2, y - 1.05), 12.6, 1.2,
                               boxstyle="round,pad=0.08",
                               facecolor=card_color,
                               edgecolor="#e0e0e0", linewidth=1)
        ax.add_patch(card)

        signal  = row["signal"]
        score   = row["score"]
        pct     = row["universe_percentile"]
        color   = signal_color(signal)
        reason  = get_reason(row, signal)

        # Rank number
        ax.text(0.45, y - 0.28, f"#{int(row['relative_rank'])}",
                fontsize=11, fontweight="bold", va="center",
                color="#aaaaaa")
        ax.text(0.45, y - 0.58, "of 5",
                fontsize=7, va="center", color="#cccccc", ha="center")

        # Ticker name
        ax.text(1.1, y - 0.35, row["ticker"],
                fontsize=16, fontweight="bold", va="center",
                color="#1a1a2e")

        # Signal badge
        badge = FancyBboxPatch((3.0, y - 0.65), 2.5, 0.55,
                                boxstyle="round,pad=0.05",
                                facecolor=color, edgecolor="none")
        ax.add_patch(badge)
        ax.text(4.25, y - 0.38,
                signal_display_text(signal, score),
                fontsize=8, fontweight="bold", ha="center", va="center",
                color="white")

        # Confidence bar (out of 10 blocks)
        bar_x = 5.7
        bar_y = y - 0.52
        bar_w = 0.28
        bar_h = 0.35
        n_filled = round(score * 10)
        for b in range(10):
            fill = color if b < n_filled else "#e8e8e8"
            rect = plt.Rectangle((bar_x + b * (bar_w + 0.04), bar_y),
                                   bar_w, bar_h,
                                   facecolor=fill, edgecolor="white",
                                   linewidth=0.5)
            ax.add_patch(rect)
        confidence_label = (
            "Very High" if score >= 0.75 else
            "High"      if score >= 0.60 else
            "Moderate"  if score >= 0.50 else
            "Low"       if score >= 0.35 else
            "Very Low"
        )
        ax.text(bar_x + 10 * (bar_w + 0.04) + 0.1, y - 0.32,
                confidence_label,
                fontsize=8, va="center", color="#444444", fontweight="bold")
        ax.text(bar_x + 10 * (bar_w + 0.04) + 0.1, y - 0.58,
                f"{score*100:.0f}%",
                fontsize=7, va="center", color="#888888")

        # Universe percentile
        universe_size = len(universe_df)
        universe_rank = int(row.get("universe_rank", int((1 - pct) * universe_size) + 1))
        pct_color = "#1a7a1a" if universe_rank <= universe_size * 0.33 else (
                    "#c0392b" if universe_rank >= universe_size * 0.66 else "#8c8c8c")
        ax.text(10.3, y - 0.32,
                f"#{universe_rank}",
                fontsize=15, fontweight="bold", va="center",
                color=pct_color, ha="center", zorder=5)
        ax.text(10.3, y - 0.65,
                f"out of {universe_size} stocks",
                fontsize=8, va="center", color="#888888", ha="center")

        # Reason
        # Word wrap manually at ~28 chars
        words = reason.split()
        line1, line2 = [], []
        for w in words:
            if len(" ".join(line1 + [w])) <= 26:
                line1.append(w)
            else:
                line2.append(w)
        ax.text(11.9, y - 0.28, " ".join(line1),
                fontsize=8, va="center", color="#444444")
        if line2:
            ax.text(11.1, y - 0.52, " ".join(line2),
                    fontsize=8, va="center", color="#444444")

    # ── Footer ───────────────────────────────────────────────
    footer_y = y_start - n * 1.45 - 0.3
    ax.axhline(y=footer_y, xmin=0.02, xmax=0.98,
               color="#cccccc", linewidth=0.8)
    ax.text(6.5, footer_y - 0.25,
            "⚠️  This is not financial advice. Signals are based on historical patterns in financial statements.",
            fontsize=8, ha="center", color="#999999", style="italic")
    ax.text(6.5, footer_y - 0.5,
            "Past performance does not guarantee future results. Always do your own research before investing.",
            fontsize=8, ha="center", color="#999999", style="italic")

    plt.tight_layout(pad=0)
    return fig


# ─────────────────────────────────────────────────────────────
# RISK RATING
# ─────────────────────────────────────────────────────────────

def compute_risk_rating(ticker, df_all):
    """
    Computes risk rating based on volatility of quarterly returns.
    HIGH   = top 33% most volatile stocks
    MEDIUM = middle 33%
    LOW    = bottom 33% least volatile
    """
    stock_data = df_all[df_all["ticker"] == ticker].copy()
    if "forward_return" not in stock_data.columns:
        return "UNKNOWN", "❓"
    returns = stock_data["forward_return"].dropna()
    if len(returns) < 4:
        return "UNKNOWN", "❓"
    volatility = returns.std()

    all_vols = df_all.groupby("ticker")["forward_return"].std().dropna()
    pct = (all_vols < volatility).mean()

    if pct > 0.66:
        return "HIGH", "⚡"
    elif pct > 0.33:
        return "MEDIUM", "〰️"
    else:
        return "LOW", "🛡️"


# ─────────────────────────────────────────────────────────────
# SIGNAL TREND HISTORY
# ─────────────────────────────────────────────────────────────

def compute_signal_trend(ticker, df_all, model, feature_cols):
    """
    Computes signals for the last 4 quarters for a stock.
    Returns a trend arrow and list of last 4 signals.
    """
    stock_rows = df_all[df_all["ticker"] == ticker].copy()
    stock_rows = stock_rows.sort_values("snapshot_date").tail(5)

    if len(stock_rows) < 2:
        return "→ STABLE", []

    signals_history = []
    signal_map = {
        "STRONG BUY": 4, "WEAK BUY": 3,
        "HOLD": 2,
        "WEAK SELL": 1, "STRONG SELL": 0
    }

    for _, row in stock_rows.iterrows():
        X = pd.DataFrame([row[feature_cols].fillna(0.5)])
        score = model.predict_proba(X)[0][1]
        if score >= 0.65:
            sig = "STRONG BUY"
        elif score >= 0.52:
            sig = "WEAK BUY"
        elif score >= 0.48:
            sig = "HOLD"
        elif score >= 0.35:
            sig = "WEAK SELL"
        else:
            sig = "STRONG SELL"
        signals_history.append(sig)

    if len(signals_history) >= 2:
        last = signal_map.get(signals_history[-1], 2)
        prev = signal_map.get(signals_history[-2], 2)
        if last > prev:
            trend = "↑ IMPROVING"
        elif last < prev:
            trend = "↓ DETERIORATING"
        else:
            trend = "→ STABLE"
    else:
        trend = "→ STABLE"

    return trend, signals_history[-4:]


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

SECTOR_GROUP_MAP = {
    "Technology": "Technology",
    "Financial Services": "Financial Services",
    "Healthcare": "Healthcare",
    "Consumer Cyclical": "Consumer",
    "Consumer Defensive": "Consumer",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Basic Materials": "Industrials",
    "Utilities": "Industrials",
    "Communication Services": "Communication",
    "Real Estate": "Real Estate",
}


def load_sector_models(out_models):
    """
    Loads all sector-specific LightGBM models.
    Falls back to universal model if sector models not found.
    """
    import json
    sector_models_dir = out_models / "sector_models"
    mapping_path = sector_models_dir / "sector_mapping.json"

    if not mapping_path.exists():
        return None, None, None

    with open(mapping_path) as f:
        mapping = json.load(f)

    sector_group_map = mapping["sector_group_map"]
    feature_cols = mapping["feature_cols"]
    sector_model_files = mapping["sector_model_files"]

    sector_models = {}
    for sector, path in sector_model_files.items():
        with open(path, "rb") as f:
            obj = pickle.load(f)
        sector_models[sector] = obj["model"]

    print(f"  Loaded {len(sector_models)} sector models")
    return sector_models, sector_group_map, feature_cols


def score_with_sector_models(df, sector_models, sector_group_map, feature_cols, fallback_model):
    """
    Scores each stock using its sector-specific model.
    Falls back to universal model if sector model not available.
    """
    df = df.copy()
    df["score"] = np.nan
    df["sector_group"] = df["sector"].map(sector_group_map).fillna(df["sector"])

    for sector, model in sector_models.items():
        mask = df["sector_group"] == sector
        if mask.sum() == 0:
            continue
        X = df.loc[mask, feature_cols].fillna(0.5)
        df.loc[mask, "score"] = model.predict_proba(X)[:, 1]

    # Fill any remaining with fallback
    missing = df["score"].isna()
    if missing.sum() > 0 and fallback_model is not None:
        X = df.loc[missing, feature_cols].fillna(0.5)
        df.loc[missing, "score"] = fallback_model.predict_proba(X)[:, 1]

    return df


def main():
    print("=" * 55)
    print("STEP 6: Generate Today Signals")
    print("=" * 55)

    # Try loading sector models first
    sector_models, sector_group_map, feature_cols = load_sector_models(OUT_MODELS)

    # Load universal fallback model
    model_path = OUT_MODELS / "final_model.pkl"
    with open(model_path, "rb") as f:
        model_obj = pickle.load(f)
    fallback_model = model_obj["model"]
    if feature_cols is None:
        feature_cols = model_obj["feature_cols"]

    if sector_models:
        print("  Using sector-specific LightGBM models")
        model = fallback_model
    else:
        print("  Sector models not found — using universal model")
        model = fallback_model
        sector_models = None

    # Load features
    df = pd.read_csv(DATA_PROC / "features.csv")
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")

    # Get most recent row per ticker
    def latest(frame):
        return frame.sort_values("snapshot_date").groupby(
            "ticker", as_index=False).tail(1).copy()

    target_df   = latest(df[df["ticker"].isin(TARGET_STOCKS)])
    universe_df = latest(df)

    # Score using sector models or fallback
    if sector_models:
        target_df   = score_with_sector_models(
            target_df, sector_models, sector_group_map, feature_cols, fallback_model)
        universe_df = score_with_sector_models(
            universe_df, sector_models, sector_group_map, feature_cols, fallback_model)
    else:
        target_df["score"]   = model.predict_proba(
            target_df[feature_cols].fillna(0.5))[:, 1]
        universe_df["score"] = model.predict_proba(
            universe_df[feature_cols].fillna(0.5))[:, 1]

    # Ranks
    target_df["relative_rank"] = (
        target_df["score"].rank(ascending=False, method="first").astype(int))
    universe_df["universe_rank"] = universe_df["score"].rank(
        ascending=False,
        method="first"
    ).astype(int)
    universe_df["universe_percentile"] = 1 - (
        (universe_df["universe_rank"] - 1) / len(universe_df)
    )

    today_file = date.today().strftime("%Y%m%d")

    # ── TOP 7 BEST BUYS FROM ENTIRE UNIVERSE ────────────────
    top7 = universe_df.nlargest(7, "score")[
        ["ticker", "score", "universe_percentile"]
    ].copy()
    top7["signal"] = "STRONG BUY"
    top7["rank"] = range(1, 8)

    print("\n🏆 TOP 7 BEST BUYS FROM FULL UNIVERSE:")
    print("-" * 55)
    print(f"{'Rank':<5} {'Ticker':<8} {'Score':>6} {'Percentile':>11}")
    print("-" * 55)
    for _, r in top7.iterrows():
        print(f"#{int(r['rank']):<4} {r['ticker']:<8} "
              f"{r['score']:.4f} {r['universe_percentile']:>10.2%}")

    # Save top 7
    top7_path = OUT_SIGNALS / f"top7_buys_{today_file}.csv"
    top7.to_csv(top7_path, index=False)
    print(f"\nSaved Top 7: {top7_path}")

    target_df = target_df.merge(
        universe_df[["ticker", "universe_rank", "universe_percentile"]], on="ticker", how="left")

    target_df["signal"] = target_df.apply(
        lambda r: make_signal(int(r["relative_rank"]),
                               float(r["universe_percentile"])), axis=1)

    # Add risk ratings
    target_df["risk_label"] = ""
    target_df["risk_emoji"] = ""
    for idx, row in target_df.iterrows():
        risk, emoji = compute_risk_rating(row["ticker"], df)
        target_df.at[idx, "risk_label"] = risk
        target_df.at[idx, "risk_emoji"] = emoji

    # Add signal trends
    target_df["trend"] = ""
    for idx, row in target_df.iterrows():
        trend, history = compute_signal_trend(
            row["ticker"], df, fallback_model, feature_cols)
        target_df.at[idx, "trend"] = trend

    # Print table
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"\nTicker | Score  | Rank | Universe %ile | Signal")
    print("-" * 58)
    for _, r in target_df.sort_values("relative_rank").iterrows():
        print(f"{r['ticker']:<6} | {r['score']:.4f} | "
              f"{int(r['relative_rank']):>4} | "
              f"{r['universe_percentile']:>13.2%} | {r['signal']}")

    # Save CSV
    out_csv = OUT_SIGNALS / f"signals_{today_file}.csv"
    cols = ["ticker", "score", "relative_rank", "universe_percentile", "signal"]
    target_df.sort_values("relative_rank")[cols].to_csv(out_csv, index=False)
    print(f"\nSaved signals CSV: {out_csv}")

    # Market warnings
    warnings_list = get_market_warning()
    if warnings_list:
        print("\n⚠️  MARKET WARNING DETECTED:")
        for w in warnings_list:
            print(f"   {w}")

    # Build dashboard
    # Merge raw feature values back in for plain English reasons
    raw_cols = [c for c in df.columns if c.endswith("_rank")]
    latest_df = latest(df)[["ticker"] + raw_cols].copy()
    latest_df.columns = ["ticker"] + raw_cols
    target_with_features = target_df.drop(columns=[c for c in raw_cols if c in target_df.columns], errors="ignore")
    target_with_features = target_with_features.merge(latest_df, on="ticker", how="left")

    fig = build_dashboard(target_with_features, warnings_list, today_str, universe_df)
    out_plot = OUT_PLOTS / "signals_dashboard.png"
    fig.savefig(out_plot, dpi=200, bbox_inches="tight",
                facecolor="#f7f9fc")
    plt.close()
    print(f"Saved dashboard  : {out_plot}")


if __name__ == "__main__":
    main()
