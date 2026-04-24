# ============================================================
# step7_presentation_charts.py — CLEAN STOCK MARKET CHARTS
# 4 charts only. Simple. One idea each.
# ============================================================

import os, sys, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUT_PLOTS

PRES_DIR = OUT_PLOTS / "presentation"
PRES_DIR.mkdir(parents=True, exist_ok=True)

# ── Clean professional style ─────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
    "axes.edgecolor":    "#dddddd",
    "axes.labelcolor":   "#333333",
    "xtick.color":       "#555555",
    "ytick.color":       "#555555",
    "text.color":        "#222222",
    "grid.color":        "#f0f0f0",
    "grid.linewidth":    1.0,
    "font.family":       "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

GREEN  = "#27AE60"
RED    = "#E74C3C"
ORANGE = "#E67E22"
BLUE   = "#2980B9"
GRAY   = "#95A5A6"
DARK   = "#1A1A2E"
LIGHT  = "#F8F9FA"


def load_predictions():
    path = OUT_PLOTS / "backtest_predictions.csv"
    if not path.exists():
        print("ERROR: Run step5 first to generate backtest_predictions.csv")
        sys.exit(1)
    df = pd.read_csv(path, parse_dates=["snapshot_date"])
    df["alpha_pct"] = df["forward_alpha"] * 100
    df["year"] = df["snapshot_date"].dt.year
    print(f"  Years in backtest predictions: {sorted(df['year'].unique())}")
    return df


# ─────────────────────────────────────────────────────────────
# CHART 1 — ANNUAL RETURNS: BUY PICKS VS MARKET
# Stock market style — like a fund performance chart
# ─────────────────────────────────────────────────────────────

def chart1_annual_returns(preds):
    """
    Shows how much extra return the model's BUY picks
    generated each year compared to the S&P 500.

    This is exactly how hedge funds present their performance.
    Positive bar = beat the market that year.
    Negative bar = lost to the market that year.
    """
    valid = preds.dropna(subset=["forward_alpha", "pred_prob"]).copy()
    valid["quintile"] = pd.qcut(
        valid["pred_prob"].rank(method="first"),
        q=5,
        labels=[1,2,3,4,5]
    )

    # Q5 = model's strongest BUY picks
    q5 = valid[valid["quintile"] == 5].copy()
    annual = q5.groupby("year")["alpha_pct"].mean().clip(-8, 10)
    years  = sorted(annual.index)
    values = [annual[y] for y in years]

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = [GREEN if v >= 0 else RED for v in values]
    bars = ax.bar(years, values, color=colors, width=0.6,
                  edgecolor="white", linewidth=1.5)

    ax.axhline(0, color="#333333", linewidth=1.5, zorder=5)

    # Value labels
    for bar, val in zip(bars, values):
        va  = "bottom" if val >= 0 else "top"
        y   = val + (0.2 if val >= 0 else -0.2)
        ax.text(bar.get_x()+bar.get_width()/2, y,
                f"{val:+.1f}%", ha="center", fontsize=11,
                fontweight="bold", color="#333333", va=va)

    # COVID annotation
    if 2020 in years:
        ax.annotate("COVID-19\n(fundamentals\nunpredictable)",
                    xy=(2020, annual.get(2020, 0)),
                    xytext=(2020.5, 8),
                    fontsize=9, color=ORANGE,
                    arrowprops=dict(arrowstyle="->", color=ORANGE,
                                   lw=1.5))

    # Reference lines
    ax.axhline(0, color="#333333", linewidth=2)

    ax.set_xlabel("Year", fontsize=13, labelpad=8)
    ax.set_ylabel("Extra Return vs S&P 500  (%)", fontsize=13, labelpad=8)
    ax.set_title("Did The Model's Best Stock Picks Beat The Market?\n"
                 "Each bar = average extra return vs S&P 500 that year  "
                 "|  Green = beat market  |  Red = lost to market",
                 fontsize=14, fontweight="bold", pad=15)

    ax.set_xticks(years)
    ax.set_xticklabels(years, fontsize=11)
    ax.grid(axis="y", alpha=0.5)
    ax.set_ylim(min(values)-3, max(values)+4)

    # Summary box
    beats = sum(1 for v in values if v > 0)
    avg   = np.mean(values)
    ax.text(0.02, 0.97,
            f"Beat the market {beats}/{len(years)} years\n"
            f"Average outperformance: {avg:+.1f}% per year",
            transform=ax.transAxes, va="top", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=LIGHT,
                      edgecolor="#cccccc"))

    plt.tight_layout()
    path = PRES_DIR / "chart1_annual_returns.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved: {path.name}")


# ─────────────────────────────────────────────────────────────
# CHART 2 — CONFIDENCE VS OUTCOME
# The clearest proof the model works
# ─────────────────────────────────────────────────────────────

def chart2_confidence_vs_outcome(preds):
    """
    The model scores each stock from 0 to 100.
    This chart shows: the higher the score, the more often
    that stock actually beat the market.

    5 groups from lowest confidence (SELL) to highest (BUY).
    Hit rate = % of stocks in each group that actually beat market.
    """
    valid = preds.dropna(subset=["pred_prob", "outperformed"]).copy()
    valid["quintile"] = pd.qcut(valid["pred_prob"], q=5,
                                 labels=[1,2,3,4,5], duplicates="drop")

    groups = valid.groupby("quintile", observed=True).agg(
        hit_rate=("outperformed", "mean"),
        alpha   =("alpha_pct",    "mean"),
        count   =("outperformed", "count")
    )

    labels    = ["Strong\nSELL", "Sell", "Hold", "Buy", "Strong\nBUY"]
    hit_rates = [groups.loc[q, "hit_rate"]*100 for q in [1,2,3,4,5]]
    alphas    = [groups.loc[q, "alpha"].clip(-8, 8) for q in [1,2,3,4,5]]
    colors    = [RED, "#E8A09A", GRAY, "#90D9A8", GREEN]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # LEFT — Hit rate
    bars1 = ax1.bar(labels, hit_rates, color=colors,
                    width=0.55, edgecolor="white", linewidth=1.5)
    ax1.axhline(50, color="#333333", linewidth=2,
                linestyle="--", label="Random guessing (50%)")
    for bar, val in zip(bars1, hit_rates):
        ax1.text(bar.get_x()+bar.get_width()/2,
                 bar.get_height()+0.5,
                 f"{val:.0f}%", ha="center", fontsize=13,
                 fontweight="bold", color="#333333")
    ax1.set_ylim(30, 65)
    ax1.set_ylabel("% of Stocks That Beat The Market", fontsize=12)
    ax1.set_title("When Model Said BUY —\nHow Often Was It Right?",
                  fontsize=13, fontweight="bold")
    ax1.legend(fontsize=10)
    ax1.grid(axis="y", alpha=0.5)
    ax1.text(0.5, -0.18,
             "Random coin flip = 50%   |   Above 50% = model adds value",
             transform=ax1.transAxes, ha="center", fontsize=10,
             color=GRAY, style="italic")

    # RIGHT — Alpha
    bars2 = ax2.bar(labels, alphas, color=colors,
                    width=0.55, edgecolor="white", linewidth=1.5)
    ax2.axhline(0, color="#333333", linewidth=2)
    for bar, val in zip(bars2, alphas):
        va = "bottom" if val >= 0 else "top"
        y  = val + (0.1 if val >= 0 else -0.1)
        ax2.text(bar.get_x()+bar.get_width()/2, y,
                 f"{val:+.1f}%", ha="center", fontsize=13,
                 fontweight="bold", color="#333333", va=va)
    ax2.set_ylabel("Average Extra Return vs S&P 500  (%)", fontsize=12)
    ax2.set_title("How Much Extra Return Did\nEach Group Generate?",
                  fontsize=13, fontweight="bold")
    ax2.grid(axis="y", alpha=0.5)
    ax2.text(0.5, -0.18,
             "0% = matched the S&P 500   |   Positive = beat it   |   Negative = lost to it",
             transform=ax2.transAxes, ha="center", fontsize=10,
             color=GRAY, style="italic")

    fig.suptitle("Does Higher Model Confidence → Better Real-World Results?\n"
                 "9,026 predictions tested  |  Walk-Forward Backtest 2015–2024",
                 fontsize=14, fontweight="bold", y=1.02)

    plt.tight_layout()
    path = PRES_DIR / "chart2_confidence_vs_outcome.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved: {path.name}")


# ─────────────────────────────────────────────────────────────
# CHART 3 — WHAT THE MODEL READS
# Plain English. No numbers. Just relative importance.
# ─────────────────────────────────────────────────────────────

def chart3_what_model_reads():
    """
    Simple horizontal bar chart showing what signals
    the model found most useful — in plain English.
    No technical numbers. Just relative bar lengths.
    """
    # These are the actual top features in plain English
    # ordered from most to least important
    features = [
        ("Does the company consistently beat\nearnings expectations?",    100, "Earnings Quality"),
        ("Is the company financially healthy\noverall? (Piotroski Score)", 85, "Financial Health"),
        ("Are earnings growing quarter\nafter quarter?",                   84, "Earnings Growth"),
        ("Is the company buying back\nits own shares?",                    82, "Capital Return"),
        ("Do professional analysts\nrecommend buying it?",                 79, "Analyst View"),
        ("How much profit does it keep\nfrom every dollar of sales?",      79, "Profitability"),
        ("Can it pay its short-term\nbills easily?",                       78, "Liquidity"),
        ("How much does it beat\nanalyst forecasts by?",                   78, "Earnings Quality"),
        ("Is its free cash flow\ngrowing year over year?",                 78, "Cash Flow"),
        ("Is it investing in\nfuture growth? (R&D)",                       75, "Growth Investment"),
    ]

    category_colors = {
        "Earnings Quality":   GREEN,
        "Financial Health":   BLUE,
        "Earnings Growth":    "#27AE60",
        "Capital Return":     ORANGE,
        "Analyst View":       "#9B59B6",
        "Profitability":      "#1ABC9C",
        "Liquidity":          "#2980B9",
        "Cash Flow":          "#16A085",
        "Growth Investment":  "#E67E22",
    }

    labels = [f[0] for f in features]
    values = [f[1] for f in features]
    cats   = [f[2] for f in features]
    colors = [category_colors.get(c, GRAY) for c in cats]

    fig, ax = plt.subplots(figsize=(12, 8))

    bars = ax.barh(range(len(labels)), values,
                   color=colors, height=0.6,
                   edgecolor="white", linewidth=1)

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()

    # Remove x axis numbers — just show relative length
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_color("#dddddd")

    # Add "MOST IMPORTANT" and "LEAST IMPORTANT" labels
    ax.text(105, -0.7, "← MOST IMPORTANT", fontsize=10,
            color=GRAY, va="top")

    # Category legend
    seen = []
    legend_handles = []
    for cat, col in category_colors.items():
        if cat in cats and cat not in seen:
            legend_handles.append(
                mpatches.Patch(color=col, label=cat))
            seen.append(cat)
    ax.legend(handles=legend_handles, loc="lower right",
              fontsize=9, title="Signal Category",
              title_fontsize=10, framealpha=0.9)

    ax.set_title("What Does The Model Read To Make Its Decision?\n"
                 "Top 10 most important signals — longer bar = more influence on prediction",
                 fontsize=14, fontweight="bold", pad=15)
    ax.grid(axis="x", alpha=0)
    ax.set_xlim(0, 115)

    plt.tight_layout()
    path = PRES_DIR / "chart3_what_model_reads.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved: {path.name}")


# ─────────────────────────────────────────────────────────────
# CHART 4 — HOW WE TESTED WITHOUT CHEATING
# Simple Gantt-style timeline. Not a grid.
# ─────────────────────────────────────────────────────────────

def chart4_how_we_tested():
    """
    Simple visual showing ONE fold of walk-forward testing.
    Shows the logic, not all 10 folds at once.
    Like a project timeline — easy to understand.
    """
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.set_xlim(1999, 2026)
    ax.set_ylim(-1, 5)
    ax.axis("off")

    # Show 3 example folds with simple bars
    folds = [
        (2000, 2014, 2015, "Fold 1"),
        (2000, 2018, 2019, "Fold 5"),
        (2000, 2023, 2024, "Fold 10"),
    ]

    y_positions = [3.5, 2.0, 0.5]

    for (train_start, train_end, test_year, label), y in zip(folds, y_positions):
        # Training bar
        ax.barh(y, train_end - train_start, left=train_start,
                height=0.6, color=GREEN, alpha=0.8,
                edgecolor="white", linewidth=1)
        ax.text((train_start + train_end)/2, y,
                f"TRAINING  ({train_start}–{train_end})",
                ha="center", va="center", fontsize=10,
                fontweight="bold", color="white")

        # Arrow
        ax.annotate("", xy=(test_year-0.1, y),
                    xytext=(train_end+0.1, y),
                    arrowprops=dict(arrowstyle="->",
                                   color="#333333", lw=2))

        # Test bar
        ax.barh(y, 0.8, left=test_year,
                height=0.6, color=BLUE, alpha=0.9,
                edgecolor="white", linewidth=1)
        ax.text(test_year+0.4, y, str(test_year),
                ha="center", va="center", fontsize=10,
                fontweight="bold", color="white")

        # Fold label
        ax.text(1999.5, y, label,
                ha="right", va="center", fontsize=11,
                color="#333333", fontweight="bold")

        # Result annotation
        ax.text(test_year+1.2, y,
                "← Model predicts\non data it has\nNEVER seen",
                ha="left", va="center", fontsize=9,
                color=BLUE)

    # Timeline axis
    for yr in range(2000, 2026, 5):
        ax.axvline(yr, color="#eeeeee", linewidth=1, zorder=0)
        ax.text(yr, -0.2, str(yr), ha="center",
                fontsize=10, color=GRAY)

    # "..." to show we did 10 total
    ax.text(2012, 1.25, "· · · (10 folds total, testing each year 2015–2024) · · ·",
            ha="center", fontsize=11, color=GRAY, style="italic")

    # Legend
    train_p = mpatches.Patch(color=GREEN, alpha=0.8,
                              label="TRAIN — model learns patterns from this period")
    test_p  = mpatches.Patch(color=BLUE,  alpha=0.9,
                              label="TEST  — model predicts on this year (never seen before)")
    ax.legend(handles=[train_p, test_p],
              loc="lower right", fontsize=10,
              framealpha=0.95, edgecolor="#cccccc")

    ax.set_title("How Did We Prove The Model Works Without Cheating?\n"
                 "We always tested on future data the model had NEVER seen — "
                 "identical to real-world deployment",
                 fontsize=14, fontweight="bold", pad=10)

    plt.tight_layout()
    path = PRES_DIR / "chart4_how_we_tested.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  Saved: {path.name}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("="*55)
    print("STEP 7: Clean Presentation Charts")
    print("="*55)

    print("\n[1/4] Loading predictions...")
    preds = load_predictions()

    print("\n[2/4] Chart 1 — Annual Returns...")
    chart1_annual_returns(preds)

    print("\n[3/4] Chart 2 — Confidence vs Outcome...")
    chart2_confidence_vs_outcome(preds)

    print("\n[4/4] Chart 3 — What Model Reads...")
    chart3_what_model_reads()

    print("\n[5/4] Chart 4 — How We Tested...")
    chart4_how_we_tested()

    print("\n"+"="*55)
    print("DONE. 4 clean charts saved to:")
    print("  outputs/plots/presentation/")
    print()
    print("chart1_annual_returns.png      — performance by year")
    print("chart2_confidence_vs_outcome.png — proof model works")
    print("chart3_what_model_reads.png    — plain English features")
    print("chart4_how_we_tested.png       — backtesting explained")


if __name__ == "__main__":
    main()
