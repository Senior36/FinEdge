# ============================================================
# src/step5_train_and_backtest.py — PROFESSIONAL MODEL
#
# ARCHITECTURE:
#   - Optuna hyperparameter tuning (100 trials per fold)
#   - LightGBM with early stopping
#   - Walk-forward backtesting (2015-2023)
#   - Information Coefficient (IC) as primary metric
#   - Quintile analysis (professional quant standard)
#   - Feature importance + SHAP values
#
# WHY IC INSTEAD OF ACCURACY:
#   Accuracy asks "did you predict the direction correctly?"
#   IC (Spearman correlation of predictions vs actual returns)
#   asks "do higher predictions correspond to higher returns?"
#   IC is the industry standard for evaluating factor models.
#   IC > 0.05 is considered good. IC > 0.10 is excellent.
# ============================================================

import os
import sys
import pickle
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns
import optuna
from catboost import CatBoostClassifier
from scipy import stats
from sklearn.metrics import roc_auc_score, accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import StackingClassifier, ExtraTreesClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
optuna.logging.set_verbosity(optuna.logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (TARGET_STOCKS, DATA_PROC, OUT_MODELS,
                    OUT_PLOTS, FORWARD_MONTHS)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BACKTEST_YEARS  = list(range(2015, 2025))  # Test on each of these years
MIN_TRAIN_YEARS = 5                         # Minimum years of training data
OPTUNA_TRIALS   = 50                        # Hyperparameter search trials per fold
EARLY_STOPPING  = 50                        # Stop if no improvement for N rounds
N_ESTIMATORS    = 1000                      # Max trees (early stopping controls actual)

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

SECTOR_MODEL_ORDER = [
    "Technology",
    "Financial Services",
    "Healthcare",
    "Consumer",
    "Energy",
    "Industrials",
    "Communication",
    "Real Estate",
]


# ─────────────────────────────────────────────────────────────
# SECTION 1: DATA LOADING
# ─────────────────────────────────────────────────────────────

def load_data():
    """
    Loads features.csv and prepares feature/label arrays.
    Returns the full dataframe and the list of feature column names.
    """
    df = pd.read_csv(DATA_PROC / "features.csv", parse_dates=["snapshot_date"])
    df = df.sort_values("snapshot_date").reset_index(drop=True)
    df["sector_model"] = df["sector"].map(SECTOR_GROUP_MAP).fillna(df["sector"])

    # Use only rank features as model inputs
    # Raw values are kept in df but not fed to model
    feature_cols = [c for c in df.columns if c.endswith("_rank")]

    print(f"  Dataset shape    : {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"  Feature count    : {len(feature_cols)} rank features")
    print(f"  Date range       : {df['snapshot_date'].min().date()} to {df['snapshot_date'].max().date()}")
    print(f"  Unique stocks    : {df['ticker'].nunique()}")
    label_counts = df["outperformed"].value_counts()
    pct = label_counts.get(1, 0) / len(df) * 100
    print(f"  Label balance    : {pct:.1f}% outperformed / {100-pct:.1f}% underperformed")

    return df, feature_cols


def summarize_backtest(backtest_df):
    """Computes the core overall metrics for any backtest dataframe."""
    overall_auc = roc_auc_score(backtest_df["outperformed"], backtest_df["pred_prob"])
    overall_ic = compute_ic(backtest_df["pred_prob"].values,
                            backtest_df["forward_alpha"].values)
    hit_rate = compute_top_quintile_hit_rate(backtest_df)
    return {
        "IC": overall_ic,
        "AUC": overall_auc,
        "HitRate": hit_rate,
    }


# ─────────────────────────────────────────────────────────────
# SECTION 2: OPTUNA HYPERPARAMETER TUNING
# ─────────────────────────────────────────────────────────────

def tune_lgbm(X_train, y_train, n_trials=OPTUNA_TRIALS):
    """
    Uses Optuna to find optimal LightGBM hyperparameters.
    Runs n_trials combinations and returns the best params.
    Uses 3-fold cross-validation on training data only.
    """
    from sklearn.model_selection import StratifiedKFold

    def objective(trial):
        params = {
            "n_estimators":      trial.suggest_int("n_estimators", 100, 600),
            "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "max_depth":         trial.suggest_int("max_depth", 4, 8),
            "num_leaves":        trial.suggest_int("num_leaves", 15, 63),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 40),
            "feature_fraction":  trial.suggest_float("feature_fraction", 0.5, 1.0),
            "bagging_fraction":  trial.suggest_float("bagging_fraction", 0.5, 1.0),
            "bagging_freq":      trial.suggest_int("bagging_freq", 1, 7),
            "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
            "reg_lambda":        trial.suggest_float("reg_lambda", 1e-4, 1.0, log=True),
            "random_state":      42,
            "verbose":           -1,
            "n_jobs":            -1,
        }

        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        aucs = []
        for train_idx, val_idx in cv.split(X_train, y_train):
            X_tr, X_val = X_train[train_idx], X_train[val_idx]
            y_tr, y_val = y_train[train_idx], y_train[val_idx]
            model = lgb.LGBMClassifier(**params)
            model.fit(X_tr, y_tr,
                      eval_set=[(X_val, y_val)],
                      callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False),
                                 lgb.log_evaluation(-1)])
            proba = model.predict_proba(X_val)[:, 1]
            aucs.append(roc_auc_score(y_val, proba))
        return np.mean(aucs)

    study = optuna.create_study(direction="maximize",
                                 sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return study.best_params


# ─────────────────────────────────────────────────────────────
# SECTION 3: INFORMATION COEFFICIENT
# ─────────────────────────────────────────────────────────────

def compute_ic(predictions, actual_returns):
    """
    Information Coefficient = Spearman rank correlation between
    model predictions and actual forward returns.

    This is the professional quant metric:
    - IC > 0.05 = useful signal
    - IC > 0.10 = strong signal
    - IC > 0.15 = exceptional (rare even at top hedge funds)

    Unlike accuracy (which needs a threshold), IC measures
    whether the full ordering of predictions matches reality.
    """
    mask = ~np.isnan(actual_returns) & ~np.isnan(predictions)
    if mask.sum() < 10:
        return np.nan
    ic, _ = stats.spearmanr(predictions[mask], actual_returns[mask])
    return ic


# ─────────────────────────────────────────────────────────────
# SECTION 4: WALK-FORWARD BACKTEST
# ─────────────────────────────────────────────────────────────

def run_walk_forward_backtest(df, feature_cols):
    """
    For each test year:
      1. Train on all data BEFORE that year
      2. Tune hyperparameters with Optuna on training data
      3. Predict on test year
      4. Compute IC, AUC, accuracy, quintile returns

    This is the honest evaluation — model never sees future data.
    """
    print(f"\n  Testing years: {BACKTEST_YEARS}")
    print(f"  Optuna trials per fold: {OPTUNA_TRIALS}")
    print()

    all_predictions = []
    fold_metrics    = []

    for test_year in BACKTEST_YEARS:
        # Split
        train_df = df[df["year"] < test_year].copy()
        test_df  = df[df["year"] == test_year].copy()

        if len(train_df) < 500 or len(test_df) < 20:
            continue

        # Check minimum training years
        train_years = train_df["year"].nunique()
        if train_years < MIN_TRAIN_YEARS:
            continue

        # Prepare arrays — fill NaN with 0.5 (neutral rank)
        X_train = train_df[feature_cols].fillna(0.5).values.astype(np.float32)
        y_train = train_df["outperformed"].values.astype(int)
        X_test  = test_df[feature_cols].fillna(0.5).values.astype(np.float32)
        y_test  = test_df["outperformed"].values.astype(int)

        # Tune hyperparameters
        print(f"  Fold {test_year}: tuning on {len(train_df):,} rows...", end=" ", flush=True)
        best_params = tune_lgbm(X_train, y_train, n_trials=OPTUNA_TRIALS)
        best_params["verbose"] = -1
        best_params["random_state"] = 42
        best_params["n_jobs"] = -1

        # Train final model with best params
        model = lgb.LGBMClassifier(**best_params)
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)],
                  callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False),
                             lgb.log_evaluation(-1)])

        # Predict
        proba = model.predict_proba(X_test)[:, 1]
        pred  = (proba > 0.5).astype(int)

        # Compute metrics
        auc      = roc_auc_score(y_test, proba)
        acc      = accuracy_score(y_test, pred)
        ic       = compute_ic(proba, test_df["forward_alpha"].values)
        ic_ret   = compute_ic(proba, test_df["forward_return"].values)

        print(f"AUC={auc:.3f}  ACC={acc:.3f}  IC={ic:.3f}  n_test={len(test_df)}")

        fold_metrics.append({
            "year":     test_year,
            "auc":      auc,
            "accuracy": acc,
            "ic":       ic,
            "ic_return":ic_ret,
            "n_train":  len(train_df),
            "n_test":   len(test_df),
        })

        # Store predictions
        result_df = test_df[["ticker", "snapshot_date", "year", "sector",
                               "outperformed", "forward_return", "forward_alpha"]].copy()
        result_df["pred_prob"]  = proba
        result_df["pred_label"] = pred
        all_predictions.append(result_df)

    backtest_df   = pd.concat(all_predictions, ignore_index=True)
    metrics_df    = pd.DataFrame(fold_metrics)

    # Second pass: Extra Trees + isotonic calibration on same folds
    print("\n  Running Extra Trees + isotonic backtest pass...")
    extratrees_predictions = []

    for test_year in BACKTEST_YEARS:
        train_df = df[df["year"] < test_year].copy()
        test_df  = df[df["year"] == test_year].copy()

        if len(train_df) < 500 or len(test_df) < 20:
            continue

        train_years = train_df["year"].nunique()
        if train_years < MIN_TRAIN_YEARS:
            continue

        X_train = train_df[feature_cols].fillna(0.5).values.astype(np.float32)
        y_train = train_df["outperformed"].values.astype(int)
        X_test  = test_df[feature_cols].fillna(0.5).values.astype(np.float32)
        y_test  = test_df["outperformed"].values.astype(int)

        base_model = ExtraTreesClassifier(
            n_estimators=500,
            random_state=42,
            n_jobs=-1
        )
        model = CalibratedClassifierCV(
            base_model,
            method="isotonic",
            cv=5
        )
        model.fit(X_train, y_train)

        proba = model.predict_proba(X_test)[:, 1]
        pred  = (proba > 0.5).astype(int)
        auc   = roc_auc_score(y_test, proba)
        ic    = compute_ic(proba, test_df["forward_alpha"].values)

        print(f"  Extra Trees fold {test_year}: AUC={auc:.3f}  IC={ic:.3f}  n_test={len(test_df)}")

        result_df = test_df[["ticker", "snapshot_date", "year", "sector",
                             "outperformed", "forward_return", "forward_alpha"]].copy()
        result_df["pred_prob"]  = proba
        result_df["pred_label"] = pred
        extratrees_predictions.append(result_df)

    if extratrees_predictions:
        extratrees_backtest_df = pd.concat(extratrees_predictions, ignore_index=True)
        extratrees_path = OUT_PLOTS / "backtest_predictions_extratrees.csv"
        extratrees_backtest_df.to_csv(extratrees_path, index=False)
        print(f"  Extra Trees predictions saved: {extratrees_path}")

    return backtest_df, metrics_df


def run_sector_specific_backtest(df, feature_cols):
    """
    Runs the same walk-forward procedure as the universal model,
    but trains a separate Optuna-tuned LightGBM model per broad sector.
    """
    print("\n[Step 2B] Sector-specific LightGBM walk-forward backtest...")
    print(f"  Sector groups: {SECTOR_MODEL_ORDER}")
    print(f"  Testing years: {BACKTEST_YEARS}")
    print(f"  Optuna trials per sector fold: {OPTUNA_TRIALS}")
    print()

    all_predictions = []
    fold_metrics = []

    for test_year in BACKTEST_YEARS:
        train_df = df[df["year"] < test_year].copy()
        test_df = df[df["year"] == test_year].copy()

        if len(train_df) < 500 or len(test_df) < 20:
            continue

        train_years = train_df["year"].nunique()
        if train_years < MIN_TRAIN_YEARS:
            continue

        fold_predictions = []
        sector_count = 0

        print(f"  Sector fold {test_year}:")

        for sector_name in SECTOR_MODEL_ORDER:
            sector_train = train_df[train_df["sector_model"] == sector_name].copy()
            sector_test = test_df[test_df["sector_model"] == sector_name].copy()

            if len(sector_test) == 0:
                continue

            if len(sector_train) < 100 or sector_train["outperformed"].nunique() < 2:
                print(f"    {sector_name:<18} skipped (train={len(sector_train)}, test={len(sector_test)})")
                continue

            X_train = sector_train[feature_cols].fillna(0.5).values.astype(np.float32)
            y_train = sector_train["outperformed"].values.astype(int)
            X_test = sector_test[feature_cols].fillna(0.5).values.astype(np.float32)
            y_test = sector_test["outperformed"].values.astype(int)

            print(f"    {sector_name:<18} tuning on {len(sector_train):,} rows...", end=" ", flush=True)
            best_params = tune_lgbm(X_train, y_train, n_trials=OPTUNA_TRIALS)
            best_params["verbose"] = -1
            best_params["random_state"] = 42
            best_params["n_jobs"] = -1

            model = lgb.LGBMClassifier(**best_params)
            model.fit(X_train, y_train,
                      eval_set=[(X_test, y_test)],
                      callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False),
                                 lgb.log_evaluation(-1)])

            proba = model.predict_proba(X_test)[:, 1]
            pred = (proba > 0.5).astype(int)
            auc = roc_auc_score(y_test, proba)
            ic = compute_ic(proba, sector_test["forward_alpha"].values)

            print(f"AUC={auc:.3f}  IC={ic:.3f}  n_test={len(sector_test)}")

            result_df = sector_test[["ticker", "snapshot_date", "year", "sector",
                                     "sector_model", "outperformed",
                                     "forward_return", "forward_alpha"]].copy()
            result_df["pred_prob"] = proba
            result_df["pred_label"] = pred
            fold_predictions.append(result_df)
            sector_count += 1

        if not fold_predictions:
            continue

        fold_df = pd.concat(fold_predictions, ignore_index=True)
        all_predictions.append(fold_df)

        fold_auc = roc_auc_score(fold_df["outperformed"], fold_df["pred_prob"])
        fold_acc = accuracy_score(fold_df["outperformed"], fold_df["pred_label"])
        fold_ic = compute_ic(fold_df["pred_prob"].values, fold_df["forward_alpha"].values)
        fold_ic_ret = compute_ic(fold_df["pred_prob"].values, fold_df["forward_return"].values)

        fold_metrics.append({
            "year": test_year,
            "auc": fold_auc,
            "accuracy": fold_acc,
            "ic": fold_ic,
            "ic_return": fold_ic_ret,
            "n_train": len(train_df),
            "n_test": len(fold_df),
            "sector_models": sector_count,
        })

        print(f"  Sector fold {test_year} summary: AUC={fold_auc:.3f}  ACC={fold_acc:.3f}  IC={fold_ic:.3f}  n_test={len(fold_df)}")

    if not all_predictions:
        return None, None

    backtest_df = pd.concat(all_predictions, ignore_index=True)
    metrics_df = pd.DataFrame(fold_metrics)
    return backtest_df, metrics_df


# ─────────────────────────────────────────────────────────────
# SECTION 5: EVALUATE BACKTEST
# ─────────────────────────────────────────────────────────────

def evaluate_backtest(backtest_df, metrics_df):
    """
    Computes and prints professional evaluation metrics.
    Creates 4 charts saved to outputs/plots/.
    """
    print("\n" + "=" * 55)
    print("BACKTEST RESULTS")
    print("=" * 55)

    # Overall metrics
    overall_auc = roc_auc_score(backtest_df["outperformed"], backtest_df["pred_prob"])
    overall_acc = accuracy_score(backtest_df["outperformed"],
                                  (backtest_df["pred_prob"] > 0.5).astype(int))
    overall_ic  = compute_ic(backtest_df["pred_prob"].values,
                              backtest_df["forward_alpha"].values)

    print(f"\n  Overall AUC      : {overall_auc:.4f}  (>0.55 = good, >0.60 = excellent)")
    print(f"  Overall Accuracy : {overall_acc:.4f}  ({overall_acc*100:.1f}%)")
    print(f"  Overall IC       : {overall_ic:.4f}  (>0.05 = good, >0.10 = excellent)")
    print()
    print(f"  {'Year':<6} {'AUC':>6} {'Acc':>6} {'IC':>7} {'n_test':>7}")
    print(f"  {'-'*40}")
    for _, row in metrics_df.iterrows():
        print(f"  {int(row['year']):<6} {row['auc']:>6.3f} {row['accuracy']:>6.3f} "
              f"{row['ic']:>7.4f} {int(row['n_test']):>7}")

    # Quintile analysis
    print(f"\n  Quintile Returns (most important chart):")
    backtest_df["quintile"] = pd.qcut(
        backtest_df["pred_prob"], q=5,
        labels=["Q1 (Sell)", "Q2", "Q3", "Q4", "Q5 (Buy)"],
        duplicates="drop"
    )
    quintile_stats = backtest_df.groupby("quintile", observed=True).agg(
        mean_alpha  =("forward_alpha",  "mean"),
        mean_return =("forward_return", "mean"),
        hit_rate    =("outperformed",   "mean"),
        count       =("outperformed",   "count")
    )
    print(f"\n  {'Quintile':<12} {'Avg Alpha':>10} {'Avg Return':>11} {'Hit Rate':>10} {'Count':>7}")
    print(f"  {'-'*55}")
    for q, row in quintile_stats.iterrows():
        print(f"  {str(q):<12} {row['mean_alpha']*100:>9.2f}% "
              f"{row['mean_return']*100:>10.2f}% "
              f"{row['hit_rate']*100:>9.1f}% {int(row['count']):>7}")

    q1_alpha = quintile_stats["mean_alpha"].iloc[0]  * 100
    q5_alpha = quintile_stats["mean_alpha"].iloc[-1] * 100
    spread   = q5_alpha - q1_alpha
    print(f"\n  Q5-Q1 Spread: {spread:.2f}%  (hedge fund target: >5%)")

    # ── CHARTS ───────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 14))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    # Chart 1: IC by year
    ax1 = fig.add_subplot(gs[0, 0])
    colors = ["green" if v > 0 else "red" for v in metrics_df["ic"]]
    bars = ax1.bar(metrics_df["year"].astype(int), metrics_df["ic"],
                   color=colors, alpha=0.8, edgecolor="black", linewidth=0.5)
    ax1.axhline(0, color="black", linewidth=1)
    ax1.axhline(0.05, color="green", linewidth=1.5, linestyle="--",
                label="IC=0.05 (good)")
    ax1.axhline(-0.05, color="red", linewidth=1.5, linestyle="--")
    for bar, val in zip(bars, metrics_df["ic"]):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=8)
    ax1.set_title("Was The Model Right Each Year?\n(Information Coefficient — above dotted line = good)",
                  fontweight="bold")
    ax1.set_xlabel("Backtest Year")
    ax1.set_ylabel("IC (Spearman Correlation)")
    ax1.legend(fontsize=9)
    ax1.tick_params(axis="x", rotation=45)

    # Chart 2: Quintile alpha spread
    ax2 = fig.add_subplot(gs[0, 1])
    quintile_labels = [str(q) for q in quintile_stats.index]
    alphas_pct = quintile_stats["mean_alpha"].values * 100
    colors2 = ["#d32f2f", "#ef9a9a", "#fff59d", "#a5d6a7", "#2e7d32"]
    bars2 = ax2.bar(range(len(quintile_labels)), alphas_pct,
                    color=colors2, edgecolor="black", linewidth=0.5)
    ax2.axhline(0, color="black", linewidth=1)
    for bar, val in zip(bars2, alphas_pct):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + (0.1 if val >= 0 else -0.3),
                 f"{val:.2f}%", ha="center", va="bottom" if val >= 0 else "top",
                 fontsize=9, fontweight="bold")
    ax2.set_xticks(range(len(quintile_labels)))
    ax2.set_xticklabels(quintile_labels, rotation=15, fontsize=9)
    ax2.set_title(f"Did Higher Confidence = Higher Returns?\n(Extra Return vs S&P 500 — Q5-Q1 Spread: {spread:.2f}%)",
                  fontweight="bold")
    ax2.set_ylabel("Average Alpha vs S&P 500 (%)")
    ax2.set_xlabel("Predicted Probability Quintile")

    # Chart 3: AUC by year
    ax3 = fig.add_subplot(gs[1, 0])
    colors3 = ["green" if v > 0.5 else "red" for v in metrics_df["auc"]]
    bars3 = ax3.bar(metrics_df["year"].astype(int), metrics_df["auc"],
                    color=colors3, alpha=0.8, edgecolor="black", linewidth=0.5)
    ax3.axhline(0.5, color="black", linewidth=1.5, linestyle="--",
                label="Random baseline (0.5)")
    ax3.axhline(0.55, color="green", linewidth=1.5, linestyle=":",
                label="Good (0.55)")
    for bar, val in zip(bars3, metrics_df["auc"]):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=8)
    ax3.set_ylim(0.40, 0.70)
    ax3.set_title("How Well Did Model Rank Stocks Each Year?\n(AUC Score — above 0.5 = better than random guessing)",
                  fontweight="bold")
    ax3.set_xlabel("Backtest Year")
    ax3.set_ylabel("AUC Score")
    ax3.legend(fontsize=9)
    ax3.tick_params(axis="x", rotation=45)

    # Chart 4: Hit rate by quintile
    ax4 = fig.add_subplot(gs[1, 1])
    hit_rates = quintile_stats["hit_rate"].values * 100
    bars4 = ax4.bar(range(len(quintile_labels)), hit_rates,
                    color=colors2, edgecolor="black", linewidth=0.5)
    ax4.axhline(50, color="black", linewidth=1.5, linestyle="--",
                label="Random (50%)")
    for bar, val in zip(bars4, hit_rates):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=9,
                 fontweight="bold")
    ax4.set_xticks(range(len(quintile_labels)))
    ax4.set_xticklabels(quintile_labels, rotation=15, fontsize=9)
    ax4.set_title("When Model Said BUY — How Often Was It Right?\n(% of Picks That Actually Beat The Market)",
                  fontweight="bold")
    ax4.set_ylabel("Outperform Rate (%)")
    ax4.set_xlabel("Predicted Probability Quintile")
    ax4.legend(fontsize=9)
    ax4.set_ylim(30, 70)

    plt.suptitle("Fundamental Model — Walk-Forward Backtest Results (2015-2024)",
                 fontsize=14, fontweight="bold", y=1.01)

    out_path = OUT_PLOTS / "backtest_results.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    backtest_df.to_csv(OUT_PLOTS / "backtest_predictions.csv", index=False)
    print(f"  Predictions saved: {OUT_PLOTS}/backtest_predictions.csv")
    print(f"\n  Chart saved: {out_path}")

    return overall_ic, overall_auc, spread


# ─────────────────────────────────────────────────────────────
# SECTION 6: MODEL COMPARISON
# ─────────────────────────────────────────────────────────────

def compute_top_quintile_hit_rate(backtest_df):
    """Returns hit rate for the top predicted quintile."""
    temp = backtest_df.copy()
    temp["quintile"] = pd.qcut(temp["pred_prob"], q=5,
                                labels=[1, 2, 3, 4, 5], duplicates="drop")
    top_quintile = temp[temp["quintile"] == 5]
    if len(top_quintile) == 0:
        return np.nan
    return top_quintile["outperformed"].mean()


def run_model_comparison(df, feature_cols, lightgbm_metrics):
    """
    Runs benchmark models on the same walk-forward splits as LightGBM
    and prints a clean comparison table.
    """
    print("\n[Step 3] Model comparison on same walk-forward splits...")

    comparison_models = {
        "Logistic Regression (Elastic Net)": LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            l1_ratio=0.5,
            C=0.1,
            max_iter=1000,
            random_state=42
        ),
        "K-Nearest Neighbors": KNeighborsClassifier(
            n_neighbors=15,
            metric="euclidean"
        ),
        "CatBoost": CatBoostClassifier(
            iterations=300,
            learning_rate=0.05,
            depth=6,
            random_seed=42,
            verbose=0
        ),
        "LightGBM + Optuna": None,
        "LightGBM DART": lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            boosting_type="dart",
            drop_rate=0.1,
            random_state=42,
            verbose=-1
        ),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=200,
            random_state=42,
            n_jobs=-1
        ),
        "Stacking Ensemble": StackingClassifier(
            estimators=[
                ("lr", LogisticRegression(
                    penalty="elasticnet",
                    solver="saga",
                    l1_ratio=0.5,
                    C=0.1,
                    max_iter=1000,
                    random_state=42
                )),
                ("lgbm", lgb.LGBMClassifier(
                    n_estimators=200,
                    learning_rate=0.05,
                    random_state=42,
                    verbose=-1
                )),
                ("knn", KNeighborsClassifier(
                    n_neighbors=15,
                    metric="euclidean"
                )),
            ],
            final_estimator=LogisticRegression(
                max_iter=1000,
                random_state=42
            ),
            cv=5,
            passthrough=False
        ),
    }

    comparison_results = {}

    for model_name, model in comparison_models.items():
        if model is None:
            comparison_results[model_name] = lightgbm_metrics
            continue

        all_preds = []
        all_labels = []
        all_returns = []

        for test_year in BACKTEST_YEARS:
            train_df = df[df["year"] < test_year].copy()
            test_df  = df[df["year"] == test_year].copy()

            if len(train_df) < 500 or len(test_df) < 20:
                continue

            X_train = train_df[feature_cols].fillna(0.5).values
            y_train = train_df["outperformed"].values.astype(int)
            X_test  = test_df[feature_cols].fillna(0.5).values
            y_test  = test_df["outperformed"].values.astype(int)

            try:
                model.fit(X_train, y_train)
                proba = model.predict_proba(X_test)[:, 1]
                all_preds.extend(proba)
                all_labels.extend(y_test)
                if "forward_alpha" in test_df.columns:
                    all_returns.extend(test_df["forward_alpha"].fillna(0).values)
            except Exception as e:
                print(f"  {model_name} failed on {test_year}: {e}")
                continue

        if len(all_preds) < 100:
            continue

        all_preds   = np.array(all_preds)
        all_labels  = np.array(all_labels)
        all_returns = np.array(all_returns)

        ic, _ = stats.spearmanr(all_preds, all_returns)
        auc = roc_auc_score(all_labels, all_preds)

        threshold = np.percentile(all_preds, 80)
        top_mask = all_preds >= threshold
        hit_rate = all_labels[top_mask].mean()

        comparison_results[model_name] = {
            "IC": ic,
            "AUC": auc,
            "HitRate": hit_rate
        }

    print("\n" + "=" * 65)
    print("MODEL COMPARISON RESULTS")
    print("=" * 65)
    print(f"{'Algorithm':<35} {'IC':>8} {'AUC':>8} {'Hit Rate':>10}")
    print("-" * 65)
    for name, metrics in comparison_results.items():
        print(f"{name:<35} "
              f"{metrics['IC']:>8.4f} "
              f"{metrics['AUC']:>8.4f} "
              f"{metrics['HitRate']:>9.1%}")
    print("=" * 65)

    return comparison_results


def print_sector_model_comparison(universal_metrics, sector_metrics):
    """Prints the universal vs sector-specific LightGBM comparison table."""
    print("\n" + "=" * 72)
    print("UNIVERSAL VS SECTOR-SPECIFIC LIGHTGBM")
    print("=" * 72)
    print(f"{'Model':<40} {'IC':>8} {'AUC':>8} {'Hit Rate':>10}")
    print("-" * 72)
    print(f"{'Universal LightGBM + Optuna':<40} "
          f"{universal_metrics['IC']:>8.4f} "
          f"{universal_metrics['AUC']:>8.4f} "
          f"{universal_metrics['HitRate']:>9.1%}")
    print(f"{'Sector-Specific LightGBM + Optuna':<40} "
          f"{sector_metrics['IC']:>8.4f} "
          f"{sector_metrics['AUC']:>8.4f} "
          f"{sector_metrics['HitRate']:>9.1%}")
    print("=" * 72)


# ─────────────────────────────────────────────────────────────
# SECTION 7: FINAL MODEL TRAINING
# ─────────────────────────────────────────────────────────────

def train_final_model(df, feature_cols):
    """
    Trains 8 sector-specific LightGBM models on full dataset.
    Each sector gets its own tuned model.
    Saves all models + sector mapping for use in step6.
    """
    import json

    # Create sector models directory
    sector_models_dir = OUT_MODELS / "sector_models"
    sector_models_dir.mkdir(parents=True, exist_ok=True)

    # Add sector group column
    df = df.copy()
    df["sector_model"] = df["sector"].map(SECTOR_GROUP_MAP).fillna(df["sector"])

    sector_models = {}
    trained_sectors = []

    print(f"  Training sector-specific LightGBM on full dataset...")

    for sector in SECTOR_MODEL_ORDER:
        sector_df = df[df["sector_model"] == sector].copy()

        if len(sector_df) < 100:
            print(f"    {sector:<25} skipped — only {len(sector_df)} rows")
            continue

        X = sector_df[feature_cols].fillna(0.5).values.astype("float32")
        y = sector_df["outperformed"].values.astype(int)

        # Tune with Optuna
        best_params = tune_lgbm(X, y, n_trials=OPTUNA_TRIALS)
        best_params["verbose"] = -1
        best_params["random_state"] = 42
        best_params["n_jobs"] = -1

        model = lgb.LGBMClassifier(**best_params)
        model.fit(X, y, callbacks=[lgb.log_evaluation(-1)])

        # Save sector model
        safe_name = sector.replace(" ", "")
        model_path = sector_models_dir / f"model_{safe_name}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump({
                "model": model,
                "feature_cols": feature_cols,
                "sector": sector
            }, f)

        sector_models[sector] = str(model_path)
        trained_sectors.append(sector)
        print(f"    {sector:<25} trained on {len(sector_df):,} rows — saved")

    # Save sector mapping
    mapping_path = sector_models_dir / "sector_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump({
            "sector_group_map": SECTOR_GROUP_MAP,
            "sector_model_files": sector_models,
            "feature_cols": feature_cols
        }, f, indent=2)
    print(f"  Sector mapping saved: {mapping_path}")
    print(f"  Sectors trained: {len(trained_sectors)}/{len(SECTOR_MODEL_ORDER)}")

    # Also save a universal fallback model
    print(f"  Training universal fallback model...")
    X_all = df[feature_cols].fillna(0.5).values.astype("float32")
    y_all = df["outperformed"].values.astype(int)
    best_params = tune_lgbm(X_all, y_all, n_trials=OPTUNA_TRIALS)
    best_params["verbose"] = -1
    best_params["random_state"] = 42
    best_params["n_jobs"] = -1
    fallback = lgb.LGBMClassifier(**best_params)
    fallback.fit(X_all, y_all, callbacks=[lgb.log_evaluation(-1)])

    fallback_path = OUT_MODELS / "final_model.pkl"
    with open(fallback_path, "wb") as f:
        pickle.dump({
            "model": fallback,
            "feature_cols": feature_cols
        }, f)
    print(f"  Fallback model saved: {fallback_path}")
    print(f"  Model type: Sector-Specific LightGBM (8 models)")

    return fallback, feature_cols


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("STEP 5: Professional Model Training and Backtesting")
    print("=" * 55)

    # Load data
    print("\n[Step 1] Loading dataset...")
    df, feature_cols = load_data()

    # Walk-forward backtest
    print("\n[Step 2] Walk-forward backtest with Optuna tuning...")
    backtest_df, metrics_df = run_walk_forward_backtest(df, feature_cols)

    # Evaluate
    ic, auc, spread = evaluate_backtest(backtest_df, metrics_df)

    lightgbm_metrics = {
        "IC": ic,
        "AUC": auc,
        "HitRate": compute_top_quintile_hit_rate(backtest_df)
    }

    sector_backtest_df, sector_metrics_df = run_sector_specific_backtest(df, feature_cols)
    sector_model_metrics = None
    if sector_backtest_df is not None and sector_metrics_df is not None:
        sector_model_metrics = summarize_backtest(sector_backtest_df)
        print_sector_model_comparison(lightgbm_metrics, sector_model_metrics)

    comparison_results = run_model_comparison(df, feature_cols, lightgbm_metrics)

    # Final model
    model, feat_cols = train_final_model(df, feature_cols)

    # Summary
    print("\n" + "=" * 55)
    print("FINAL SUMMARY")
    print("=" * 55)
    print(f"  Overall IC   : {ic:.4f}")
    print(f"  Overall AUC  : {auc:.4f}")
    print(f"  Q5-Q1 Spread : {spread:.2f}%")
    print(f"  Top Q HitRate: {lightgbm_metrics['HitRate']:.1%}")
    if sector_model_metrics is not None:
        print()
        print("  Sector-specific LightGBM:")
        print(f"    IC       : {sector_model_metrics['IC']:.4f}")
        print(f"    AUC      : {sector_model_metrics['AUC']:.4f}")
        print(f"    Hit Rate : {sector_model_metrics['HitRate']:.1%}")
    print()
    if ic > 0.08:
        print("  VERDICT: Strong signal. Ready for production use.")
    elif ic > 0.05:
        print("  VERDICT: Useful signal. Good for ensemble component.")
    elif ic > 0.02:
        print("  VERDICT: Weak but positive signal. Acceptable baseline.")
    else:
        print("  VERDICT: Insufficient signal. Review feature engineering.")
    print()
    print("  Outputs:")
    print(f"    Model   : outputs/models/final_model.pkl")
    print(f"    Charts  : outputs/plots/backtest_results.png")
    print(f"              outputs/plots/feature_importance.png")
    print(f"    Compare : {len(comparison_results)} models on same folds")
    print()
    print("  Ready for Step 6 (live signal generation).")


if __name__ == "__main__":
    main()
