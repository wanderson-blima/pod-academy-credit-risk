"""
Ensemble Comparison — Top 3 vs All 5 — OCI Data Science
Compares Top 3 (LightGBM + XGBoost + CatBoost) vs All 5 ensemble strategies
using simple average, generating a formal JSON artifact and comparison plot.

Usage:
    python ensemble_comparison.py

    Environment variables (optional):
        ARTIFACT_DIR  — path to model artifacts (default: /home/datascience/artifacts)
        DATA_PATH     — path to Gold parquet data (default: /home/datascience/data/clientes_final/)
"""
import os
import sys
import json
import pickle
import logging
import warnings

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from datetime import datetime
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

# sklearn compat patch
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET = "FPD"
TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOT_SAFRAS = [202502, 202503]

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DATA_PATH = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_final/")

MODEL_FILES = {
    "LightGBM_v2":   "credit_risk_lgbm_v2.pkl",
    "XGBoost":        "credit_risk_xgboost.pkl",
    "CatBoost":       "credit_risk_catboost.pkl",
    "RandomForest":   "credit_risk_rf.pkl",
    "LR_L1_v2":      "credit_risk_lr_l1_v2.pkl",
}

TOP3_MODELS = ["LightGBM_v2", "XGBoost", "CatBoost"]
ALL5_MODELS = ["LightGBM_v2", "XGBoost", "CatBoost", "RandomForest", "LR_L1_v2"]

MAX_FEATURES = 110

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def compute_ks(y_true, y_prob):
    """Kolmogorov-Smirnov statistic between good/bad score distributions."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    if len(prob_good) == 0 or len(prob_bad) == 0:
        return 0.0
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def compute_gini(auc):
    """Gini coefficient from AUC (as percentage)."""
    return (2 * auc - 1) * 100


def compute_psi(expected, actual, bins=10):
    """Population Stability Index between two score distributions."""
    breakpoints = np.percentile(expected, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]
    expected_pct = (expected_counts + 1) / (len(expected) + len(breakpoints) - 1)
    actual_pct = (actual_counts + 1) / (len(actual) + len(breakpoints) - 1)
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return round(psi, 6)


# ---------------------------------------------------------------------------
# Data & model loading
# ---------------------------------------------------------------------------
def load_models():
    """Load the 5 trained model .pkl files from ARTIFACT_DIR/models."""
    model_dir = os.path.join(ARTIFACT_DIR, "models")
    models = {}
    for name, filename in MODEL_FILES.items():
        path = os.path.join(model_dir, filename)
        if not os.path.exists(path):
            log.warning("Model file not found: %s", path)
            continue
        with open(path, "rb") as f:
            models[name] = pickle.load(f)
        log.info("Loaded model: %s (%s)", name, filename)

    if len(models) == 0:
        raise FileNotFoundError(
            f"No model files found in {model_dir}. "
            f"Expected: {list(MODEL_FILES.values())}"
        )
    log.info("Total models loaded: %d / %d", len(models), len(MODEL_FILES))
    return models


def load_features():
    """Load selected features from ARTIFACT_DIR/selected_features.json."""
    features_path = os.path.join(ARTIFACT_DIR, "selected_features.json")
    if os.path.exists(features_path):
        with open(features_path) as f:
            feat_data = json.load(f)
        features = feat_data["features"]
        log.info("Loaded %d features from selected_features.json", len(features))
    else:
        log.warning("selected_features.json not found — will detect from models")
        features = None
    return features


def load_data(features):
    """Load Gold feature store parquet data and apply preprocessing."""
    log.info("Loading data from %s", DATA_PATH)
    import pyarrow.parquet as pq

    # Determine columns to load
    cols_to_load = None
    if features is not None:
        cols_to_load = list(set(features + [TARGET, "SAFRA", "NUM_CPF"]))

    if os.path.isdir(DATA_PATH):
        table = pq.read_table(DATA_PATH, columns=cols_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(DATA_PATH, columns=cols_to_load)

    log.info("Raw data shape: %s", df.shape)
    return df


def preprocess(df, features):
    """Select features, replace inf with NaN, fill NaN with training medians."""
    # Limit to MAX_FEATURES
    available = [f for f in features if f in df.columns]
    if len(available) > MAX_FEATURES:
        available = available[:MAX_FEATURES]
    log.info("Using %d features (max %d)", len(available), MAX_FEATURES)

    # Split train/OOT
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS)].copy()
    log.info("Split — Train: %d | OOT: %d", len(df_train), len(df_oot))

    # Replace inf -> NaN
    df_train[available] = df_train[available].replace([np.inf, -np.inf], np.nan)
    df_oot[available] = df_oot[available].replace([np.inf, -np.inf], np.nan)

    # Compute training medians and fill NaN
    train_medians = df_train[available].median()
    df_train[available] = df_train[available].fillna(train_medians)
    df_oot[available] = df_oot[available].fillna(train_medians)

    return df_train, df_oot, available


# ---------------------------------------------------------------------------
# Ensemble evaluation
# ---------------------------------------------------------------------------
def evaluate_ensemble(models, model_names, X_train, y_train, X_oot, y_oot):
    """Compute simple average ensemble predictions and metrics for given models."""
    # Generate base predictions
    preds_train = np.column_stack([
        models[name].predict_proba(X_train)[:, 1] for name in model_names
    ])
    preds_oot = np.column_stack([
        models[name].predict_proba(X_oot)[:, 1] for name in model_names
    ])

    # Simple average
    avg_train = preds_train.mean(axis=1)
    avg_oot = preds_oot.mean(axis=1)

    # Metrics — Train
    ks_train = compute_ks(y_train, avg_train)
    auc_train = roc_auc_score(y_train, avg_train)
    gini_train = compute_gini(auc_train)

    # Metrics — OOT
    ks_oot = compute_ks(y_oot, avg_oot)
    auc_oot = roc_auc_score(y_oot, avg_oot)
    gini_oot = compute_gini(auc_oot)

    # PSI (train vs OOT)
    psi = compute_psi(avg_train, avg_oot)

    # Overfit metrics
    ks_gap = round(ks_train - ks_oot, 6)
    overfit_ratio = round(ks_oot / ks_train, 6) if ks_train > 0 else 0.0

    return {
        "ks_train": round(ks_train, 6),
        "auc_train": round(auc_train, 6),
        "gini_train": round(gini_train, 6),
        "ks_oot": round(ks_oot, 6),
        "auc_oot": round(auc_oot, 6),
        "gini_oot": round(gini_oot, 6),
        "psi": psi,
        "ks_gap": ks_gap,
        "overfit_ratio": overfit_ratio,
    }


def evaluate_individual_models(models, X_oot, y_oot):
    """Compute KS and AUC for each individual model on OOT."""
    individual = {}
    for name, model in models.items():
        proba = model.predict_proba(X_oot)[:, 1]
        ks = compute_ks(y_oot, proba)
        auc = roc_auc_score(y_oot, proba)
        individual[name] = {
            "ks_oot": round(ks, 6),
            "auc_oot": round(auc, 6),
        }
    return individual


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def generate_comparison_plot(top3_metrics, all5_metrics, output_dir):
    """Generate KS/AUC/Gini comparison bar chart (Top 3 vs All 5)."""
    os.makedirs(output_dir, exist_ok=True)

    metrics_names = ["KS (OOT)", "AUC (OOT)", "Gini (OOT)", "KS (Train)", "PSI"]
    top3_vals = [
        top3_metrics["ks_oot"],
        top3_metrics["auc_oot"],
        top3_metrics["gini_oot"] / 100,  # normalize for chart scale
        top3_metrics["ks_train"],
        top3_metrics["psi"],
    ]
    all5_vals = [
        all5_metrics["ks_oot"],
        all5_metrics["auc_oot"],
        all5_metrics["gini_oot"] / 100,  # normalize for chart scale
        all5_metrics["ks_train"],
        all5_metrics["psi"],
    ]

    x = np.arange(len(metrics_names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width / 2, top3_vals, width, label="Top 3 (LGB+XGB+CB)",
                   color="#2196F3", edgecolor="white", alpha=0.85)
    bars2 = ax.bar(x + width / 2, all5_vals, width, label="All 5 (+RF+LR)",
                   color="#FF9800", edgecolor="white", alpha=0.85)

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.4f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center", va="bottom", fontsize=8,
            )

    ax.set_ylabel("Value")
    ax.set_title("Ensemble Comparison: Top 3 vs All 5 (Simple Average)")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # Add QG-05 threshold lines
    ax.axhline(y=0.20, color="red", linestyle="--", linewidth=1, alpha=0.5,
               label="KS threshold (0.20)")
    ax.axhline(y=0.65, color="green", linestyle="--", linewidth=1, alpha=0.5,
               label="AUC threshold (0.65)")

    fig.tight_layout()
    plot_path = os.path.join(output_dir, "ensemble_comparison_top3_vs_all5.png")
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Plot saved to %s", plot_path)
    return plot_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now().isoformat()

    log.info("=" * 60)
    log.info("Ensemble Comparison — Top 3 vs All 5")
    log.info("=" * 60)
    log.info("Run ID:       %s", run_id)
    log.info("ARTIFACT_DIR: %s", ARTIFACT_DIR)
    log.info("DATA_PATH:    %s", DATA_PATH)
    log.info("TARGET:       %s", TARGET)
    log.info("TRAIN_SAFRAS: %s", TRAIN_SAFRAS)
    log.info("OOT_SAFRAS:   %s", OOT_SAFRAS)

    # --- Load models ---
    models = load_models()

    # Validate required models
    missing_top3 = [m for m in TOP3_MODELS if m not in models]
    if missing_top3:
        log.error("Missing Top 3 models: %s — aborting.", missing_top3)
        sys.exit(1)

    missing_all5 = [m for m in ALL5_MODELS if m not in models]
    if missing_all5:
        log.warning("Missing models for All 5 ensemble: %s", missing_all5)

    # --- Load features ---
    features = load_features()
    if features is None:
        # Fallback: detect from first model
        first_model = models[TOP3_MODELS[0]]
        if hasattr(first_model, "feature_names_in_"):
            features = list(first_model.feature_names_in_)
        elif hasattr(first_model, "feature_name_"):
            features = list(first_model.feature_name_())
        else:
            log.error("Cannot detect features — provide selected_features.json")
            sys.exit(1)
        log.info("Detected %d features from model", len(features))

    # --- Load and preprocess data ---
    df = load_data(features)
    df_train, df_oot, used_features = preprocess(df, features)

    # Filter rows with non-null FPD
    df_train_labeled = df_train[df_train[TARGET].notna()].copy()
    df_oot_labeled = df_oot[df_oot[TARGET].notna()].copy()
    log.info("Labeled records — Train: %d | OOT: %d",
             len(df_train_labeled), len(df_oot_labeled))

    if len(df_train_labeled) == 0 or len(df_oot_labeled) == 0:
        log.error("No labeled records available for evaluation. Aborting.")
        sys.exit(1)

    X_train = df_train_labeled[used_features]
    y_train = df_train_labeled[TARGET].values.astype(int)
    X_oot = df_oot_labeled[used_features]
    y_oot = df_oot_labeled[TARGET].values.astype(int)

    # --- Evaluate Top 3 ensemble ---
    log.info("-" * 60)
    log.info("Evaluating Top 3 Ensemble: %s", TOP3_MODELS)
    top3_metrics = evaluate_ensemble(models, TOP3_MODELS, X_train, y_train, X_oot, y_oot)
    log.info("  KS OOT=%.4f  AUC OOT=%.4f  Gini=%.2f%%  PSI=%.6f",
             top3_metrics["ks_oot"], top3_metrics["auc_oot"],
             top3_metrics["gini_oot"], top3_metrics["psi"])

    # --- Evaluate All 5 ensemble ---
    available_all5 = [m for m in ALL5_MODELS if m in models]
    log.info("-" * 60)
    log.info("Evaluating All 5 Ensemble: %s", available_all5)
    all5_metrics = evaluate_ensemble(models, available_all5, X_train, y_train, X_oot, y_oot)
    log.info("  KS OOT=%.4f  AUC OOT=%.4f  Gini=%.2f%%  PSI=%.6f",
             all5_metrics["ks_oot"], all5_metrics["auc_oot"],
             all5_metrics["gini_oot"], all5_metrics["psi"])

    # --- Individual model metrics (OOT) ---
    log.info("-" * 60)
    log.info("Individual Model Metrics (OOT)")
    individual_metrics = evaluate_individual_models(models, X_oot, y_oot)
    for name, m in individual_metrics.items():
        log.info("  %-15s  KS=%.4f  AUC=%.4f", name, m["ks_oot"], m["auc_oot"])

    # --- Recommendation ---
    if top3_metrics["ks_oot"] >= all5_metrics["ks_oot"]:
        recommendation = "top3"
        rationale = (
            f"Top 3 ensemble (KS OOT={top3_metrics['ks_oot']:.4f}) matches or exceeds "
            f"All 5 (KS OOT={all5_metrics['ks_oot']:.4f}) with fewer models, "
            f"reducing complexity and inference latency. "
            f"Overfit ratio Top3={top3_metrics['overfit_ratio']:.4f} vs "
            f"All5={all5_metrics['overfit_ratio']:.4f}."
        )
    else:
        recommendation = "all5"
        rationale = (
            f"All 5 ensemble (KS OOT={all5_metrics['ks_oot']:.4f}) outperforms "
            f"Top 3 (KS OOT={top3_metrics['ks_oot']:.4f}). "
            f"The marginal gain of {all5_metrics['ks_oot'] - top3_metrics['ks_oot']:.4f} KS "
            f"justifies the additional model complexity. "
            f"PSI remains stable: Top3={top3_metrics['psi']:.6f}, All5={all5_metrics['psi']:.6f}."
        )

    # --- Build output JSON ---
    output = {
        "run_id": run_id,
        "timestamp": timestamp,
        "ensembles": {
            "top3": {
                "models": list(TOP3_MODELS),
                **top3_metrics,
            },
            "all5": {
                "models": list(available_all5),
                **all5_metrics,
            },
        },
        "recommendation": recommendation,
        "rationale": rationale,
        "individual_models_oot": individual_metrics,
    }

    # --- Save JSON artifact ---
    metrics_dir = os.path.join(ARTIFACT_DIR, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    json_path = os.path.join(metrics_dir, "ensemble_comparison.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    log.info("JSON artifact saved to %s", json_path)

    # --- Generate comparison plot ---
    plots_dir = os.path.join(ARTIFACT_DIR, "plots")
    generate_comparison_plot(top3_metrics, all5_metrics, plots_dir)

    # --- Print results table ---
    log.info("=" * 60)
    log.info("RESULTS SUMMARY")
    log.info("=" * 60)
    header = f"{'Ensemble':<12} {'KS Train':>10} {'KS OOT':>10} {'AUC OOT':>10} {'Gini OOT':>10} {'PSI':>10} {'KS Gap':>10} {'Overfit':>10}"
    log.info(header)
    log.info("-" * len(header))
    for label, m in [("Top 3", top3_metrics), ("All 5", all5_metrics)]:
        log.info(
            "%-12s %10.4f %10.4f %10.4f %9.2f%% %10.6f %10.4f %10.4f",
            label, m["ks_train"], m["ks_oot"], m["auc_oot"],
            m["gini_oot"], m["psi"], m["ks_gap"], m["overfit_ratio"],
        )

    log.info("")
    log.info("Recommendation: %s", recommendation.upper())
    log.info("Rationale: %s", rationale)
    log.info("")
    log.info("Artifacts:")
    log.info("  JSON:  %s", json_path)
    log.info("  Plot:  %s/ensemble_comparison_top3_vs_all5.png", plots_dir)
    log.info("=" * 60)
    log.info("DONE — Ensemble Comparison Complete")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
