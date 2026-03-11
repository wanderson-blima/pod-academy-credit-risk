"""
Ensemble Model — OCI Data Science
Implements 3 ensemble strategies using the Top 3 models (LightGBM, XGBoost, CatBoost):
  1. Simple Average of top 3 model probabilities
  2. Blend via SLSQP weight optimization (max KS on OOS)
  3. Stacking with LogisticRegression meta-learner on OOS predictions

Only the 3 best-performing models are used in the ensemble (selected by KS OOT).
LR L1 and Random Forest are excluded — they have lower discriminative power and
add noise without improving ensemble performance.

Selects champion by max KS on OOT, validates QG-05, saves artifacts.

Usage:
    python ensemble.py

    Environment variables (optional):
        ARTIFACT_DIR  — path to model artifacts (default: /home/datascience/artifacts)
        DATA_PATH     — path to Gold parquet data (default: /home/datascience/data/clientes_final/)
"""
import os
import sys
import json
import time
import pickle
import logging
import warnings

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy.optimize import minimize
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET = "FPD"
TRAIN_SAFRAS = [202410, 202411, 202412, 202501]
OOS_SAFRA = [202501]
OOT_SAFRAS = [202502, 202503]

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
LOCAL_DATA_PATH = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_final/")

# Top 3 models for ensemble (best KS OOT: LGBM > XGB > CatBoost)
# LR L1 and RF excluded — lower discriminative power, add noise
MODEL_FILES = {
    "LightGBM_v2":   "credit_risk_lgbm_v2.pkl",
    "XGBoost":        "credit_risk_xgboost.pkl",
    "CatBoost":       "credit_risk_catboost.pkl",
}

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
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def compute_gini(auc):
    """Gini coefficient from AUC."""
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
# _EnsembleModel
# ---------------------------------------------------------------------------
class _EnsembleModel:
    """Wrapper for ensemble predictions supporting all 3 modes."""

    def __init__(self, mode, base_models, weights=None, meta_model=None,
                 feature_names=None):
        """
        Parameters
        ----------
        mode : str
            One of 'average', 'blend', 'stacking'.
        base_models : dict
            Mapping of model name -> fitted estimator.
        weights : np.ndarray, optional
            Weight vector for blend mode. Must sum to 1.
        meta_model : estimator, optional
            Fitted meta-learner for stacking mode.
        feature_names : list[str], optional
            Feature names used by base models.
        """
        self.mode = mode
        self.base_models = base_models
        self.weights = weights
        self.meta_model = meta_model
        self.feature_names = feature_names

    def predict_proba(self, X):
        """Generate combined probability predictions.

        Returns array of shape (n_samples, 2) with columns [P(0), P(1)].
        """
        base_probs = np.column_stack([
            m.predict_proba(X)[:, 1] for m in self.base_models.values()
        ])

        if self.mode == "average":
            probs = base_probs.mean(axis=1)
        elif self.mode == "blend":
            probs = base_probs @ self.weights
        elif self.mode == "stacking":
            probs = self.meta_model.predict_proba(base_probs)[:, 1]
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        return np.column_stack([1 - probs, probs])

    def save(self, path):
        """Serialize ensemble to pickle file."""
        with open(path, "wb") as f:
            pickle.dump(self, f)
        log.info("Ensemble saved to %s", path)

    @staticmethod
    def load(path):
        """Load ensemble from pickle file."""
        with open(path, "rb") as f:
            return pickle.load(f)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_models():
    """Load the top 3 trained model .pkl files from ARTIFACT_DIR/models."""
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


def load_data(columns=None):
    """Load Gold feature store data from LOCAL_DATA_PATH (parquet).

    Args:
        columns: list of columns to load. If None, loads all (AVOID for large data).
    """
    import pyarrow.parquet as pq
    log.info("Loading data from %s", LOCAL_DATA_PATH)
    if columns:
        # Ensure SAFRA and TARGET are included
        cols = list(set(columns + [TARGET, "SAFRA"]))
        table = pq.read_table(LOCAL_DATA_PATH, columns=cols)
        df = table.to_pandas()
        del table
    else:
        df = pd.read_parquet(LOCAL_DATA_PATH)
    log.info("Feature store shape: %s", df.shape)
    return df


def split_data(df):
    """Temporal split into train, OOS, OOT."""
    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS)].copy()
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA)].copy()
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS)].copy()
    log.info(
        "Split — Train: %d | OOS: %d | OOT: %d",
        len(df_train), len(df_oos), len(df_oot),
    )
    return df_train, df_oos, df_oot


def detect_features(df, models):
    """Detect feature columns by inspecting the first model or falling back to
    numeric columns excluding known non-feature columns."""
    exclude = {TARGET, "SAFRA", "NUM_CPF", "DT_PROCESSAMENTO",
               "_execution_id", "_data_inclusao", "_data_alteracao_silver"}

    # Try to get feature names from a model
    first_model = next(iter(models.values()))
    if hasattr(first_model, "feature_names_in_"):
        features = list(first_model.feature_names_in_)
    elif hasattr(first_model, "feature_name_"):
        features = list(first_model.feature_name_())
    elif hasattr(first_model, "booster_") and hasattr(first_model.booster_, "feature_name"):
        features = first_model.booster_.feature_name()
    else:
        # Fallback: all numeric columns not in exclusion set
        features = [
            c for c in df.select_dtypes(include=[np.number]).columns
            if c not in exclude
        ]

    available = [f for f in features if f in df.columns]
    log.info("Features detected: %d (available in data: %d)", len(features), len(available))
    return available


# ---------------------------------------------------------------------------
# Ensemble strategies
# ---------------------------------------------------------------------------
def build_base_predictions(models, X):
    """Generate P(1) predictions from each base model."""
    preds = pd.DataFrame(index=X.index)
    for name, model in models.items():
        preds[name] = model.predict_proba(X)[:, 1]
    return preds


def strategy_average(preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models):
    """Strategy 1: Simple average of all model probabilities."""
    log.info("Strategy 1: Simple Average")

    pred_train = preds_train.mean(axis=1).values
    pred_oos = preds_oos.mean(axis=1).values
    pred_oot = preds_oot.mean(axis=1).values

    ks_train = compute_ks(y_train, pred_train)
    auc_train = roc_auc_score(y_train, pred_train)

    ks_oos = compute_ks(y_oos, pred_oos)
    auc_oos = roc_auc_score(y_oos, pred_oos)

    ks_oot = compute_ks(y_oot, pred_oot)
    auc_oot = roc_auc_score(y_oot, pred_oot)
    gini_oot = compute_gini(auc_oot)
    psi = compute_psi(pred_train, pred_oot)

    n_models = len(models)
    weights = np.ones(n_models) / n_models
    ensemble = _EnsembleModel(
        mode="average",
        base_models=models,
        weights=weights,
    )

    metrics = {
        "ks_train": round(ks_train, 5),
        "auc_train": round(auc_train, 5),
        "ks_oos": round(ks_oos, 5),
        "auc_oos": round(auc_oos, 5),
        "ks_oot": round(ks_oot, 5),
        "auc_oot": round(auc_oot, 5),
        "gini_oot": round(gini_oot, 2),
        "psi": round(psi, 6),
        "weights": {n: round(w, 4) for n, w in zip(models.keys(), weights)},
    }

    log.info("  KS OOT=%.4f  AUC OOT=%.4f  Gini=%.2f  PSI=%.6f",
             ks_oot, auc_oot, gini_oot, psi)
    return ensemble, metrics, pred_train, pred_oos, pred_oot


def strategy_blend(preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models):
    """Strategy 2: Blend via SLSQP weight optimization (max KS on OOS)."""
    log.info("Strategy 2: Blend (SLSQP)")
    model_names = list(models.keys())
    n_models = len(model_names)

    def neg_ks_objective(w):
        blended = np.dot(preds_oos.values, w)
        return -compute_ks(y_oos, blended)

    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    bounds = [(0.01, 1.0)] * n_models
    x0 = np.ones(n_models) / n_models

    result = minimize(
        neg_ks_objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    optimal_weights = result.x

    log.info("  Optimal weights:")
    for name, w in zip(model_names, optimal_weights):
        log.info("    %s: %.4f", name, w)

    pred_train = np.dot(preds_train.values, optimal_weights)
    pred_oos = np.dot(preds_oos.values, optimal_weights)
    pred_oot = np.dot(preds_oot.values, optimal_weights)

    ks_train = compute_ks(y_train, pred_train)
    auc_train = roc_auc_score(y_train, pred_train)

    ks_oos = compute_ks(y_oos, pred_oos)
    auc_oos = roc_auc_score(y_oos, pred_oos)

    ks_oot = compute_ks(y_oot, pred_oot)
    auc_oot = roc_auc_score(y_oot, pred_oot)
    gini_oot = compute_gini(auc_oot)
    psi = compute_psi(pred_train, pred_oot)

    ensemble = _EnsembleModel(
        mode="blend",
        base_models=models,
        weights=optimal_weights,
    )

    metrics = {
        "ks_train": round(ks_train, 5),
        "auc_train": round(auc_train, 5),
        "ks_oos": round(ks_oos, 5),
        "auc_oos": round(auc_oos, 5),
        "ks_oot": round(ks_oot, 5),
        "auc_oot": round(auc_oot, 5),
        "gini_oot": round(gini_oot, 2),
        "psi": round(psi, 6),
        "weights": {n: round(w, 4) for n, w in zip(model_names, optimal_weights)},
        "optimizer_success": bool(result.success),
        "optimizer_message": result.message,
    }

    log.info("  KS OOT=%.4f  AUC OOT=%.4f  Gini=%.2f  PSI=%.6f",
             ks_oot, auc_oot, gini_oot, psi)
    return ensemble, metrics, pred_train, pred_oos, pred_oot


def strategy_stacking(preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models):
    """Strategy 3: Stacking with LogisticRegression meta-learner."""
    log.info("Strategy 3: Stacking (LR Meta-Learner)")
    model_names = list(models.keys())

    meta_learner = LogisticRegression(
        C=1.0, penalty="l2", solver="lbfgs", max_iter=1000
    )
    meta_learner.fit(preds_oos.values, y_oos)

    log.info("  Meta-learner coefficients:")
    for name, coef in zip(model_names, meta_learner.coef_[0]):
        log.info("    %s: %.4f", name, coef)

    pred_train = meta_learner.predict_proba(preds_train.values)[:, 1]
    pred_oos = meta_learner.predict_proba(preds_oos.values)[:, 1]
    pred_oot = meta_learner.predict_proba(preds_oot.values)[:, 1]

    ks_train = compute_ks(y_train, pred_train)
    auc_train = roc_auc_score(y_train, pred_train)

    ks_oos = compute_ks(y_oos, pred_oos)
    auc_oos = roc_auc_score(y_oos, pred_oos)

    ks_oot = compute_ks(y_oot, pred_oot)
    auc_oot = roc_auc_score(y_oot, pred_oot)
    gini_oot = compute_gini(auc_oot)
    psi = compute_psi(pred_train, pred_oot)

    ensemble = _EnsembleModel(
        mode="stacking",
        base_models=models,
        meta_model=meta_learner,
    )

    metrics = {
        "ks_train": round(ks_train, 5),
        "auc_train": round(auc_train, 5),
        "ks_oos": round(ks_oos, 5),
        "auc_oos": round(auc_oos, 5),
        "ks_oot": round(ks_oot, 5),
        "auc_oot": round(auc_oot, 5),
        "gini_oot": round(gini_oot, 2),
        "psi": round(psi, 6),
        "meta_learner_coefs": {
            n: round(c, 4) for n, c in zip(model_names, meta_learner.coef_[0])
        },
        "meta_learner_intercept": round(float(meta_learner.intercept_[0]), 4),
    }

    log.info("  KS OOT=%.4f  AUC OOT=%.4f  Gini=%.2f  PSI=%.6f",
             ks_oot, auc_oot, gini_oot, psi)
    return ensemble, metrics, pred_train, pred_oos, pred_oot


# ---------------------------------------------------------------------------
# Quality Gate QG-05
# ---------------------------------------------------------------------------
def validate_qg05(metrics):
    """Validate quality gate thresholds. Returns dict of checks and pass/fail."""
    gates = {
        "KS > 0.20":  metrics["ks_oot"] > 0.20,
        "AUC > 0.65": metrics["auc_oot"] > 0.65,
        "Gini > 30":  metrics["gini_oot"] > 30,
        "PSI < 0.25": metrics["psi"] < 0.25,
    }
    all_pass = all(gates.values())

    log.info("=== Quality Gate QG-05 ===")
    for check, passed in gates.items():
        status = "PASS" if passed else "FAIL"
        log.info("  [%s] %s", status, check)
    log.info("  Result: %s", "APPROVED" if all_pass else "REJECTED")

    return gates, all_pass


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def generate_plots(results, y_oot, output_dir):
    """Generate comparison plots: ROC overlay, KS curves, score distributions."""
    os.makedirs(output_dir, exist_ok=True)

    strategy_labels = {
        "average": "Simple Average",
        "blend": "Blend (SLSQP)",
        "stacking": "Stacking (LR)",
    }
    colors = {"average": "#2196F3", "blend": "#FF9800", "stacking": "#4CAF50"}

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # --- Plot 1: ROC overlay ---
    ax = axes[0]
    for name, info in results.items():
        preds = info["preds_oot"]
        fpr, tpr, _ = roc_curve(y_oot, preds)
        auc_val = info["metrics"]["auc_oot"]
        label = f"{strategy_labels[name]} (AUC={auc_val:.4f})"
        ax.plot(fpr, tpr, color=colors[name], linewidth=2, label=label)
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves — Ensemble Strategies")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Plot 2: KS curves (cumulative distributions) ---
    ax = axes[1]
    for name, info in results.items():
        preds = info["preds_oot"]
        y = y_oot.values if hasattr(y_oot, "values") else y_oot
        sorted_idx = np.argsort(preds)
        sorted_preds = preds[sorted_idx]
        sorted_y = y[sorted_idx]

        n = len(sorted_y)
        cum_good = np.cumsum(sorted_y == 0) / np.sum(sorted_y == 0)
        cum_bad = np.cumsum(sorted_y == 1) / np.sum(sorted_y == 1)
        ks_val = info["metrics"]["ks_oot"]
        label = f"{strategy_labels[name]} (KS={ks_val:.4f})"
        ax.plot(
            np.linspace(0, 1, n), cum_good - cum_bad,
            color=colors[name], linewidth=2, label=label,
        )
    ax.axhline(y=0.20, color="red", linestyle="--", linewidth=1, alpha=0.7,
               label="Threshold 0.20")
    ax.set_xlabel("Population Proportion")
    ax.set_ylabel("KS (CDF Good - CDF Bad)")
    ax.set_title("KS Curves — Ensemble Strategies")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Plot 3: Score distributions ---
    ax = axes[2]
    for name, info in results.items():
        preds = info["preds_oot"]
        ax.hist(
            preds, bins=50, alpha=0.4, density=True,
            color=colors[name], label=strategy_labels[name],
        )
    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Density")
    ax.set_title("Score Distributions — OOT")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "ensemble_comparison.png")
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Plots saved to %s", plot_path)
    return plot_path


# ---------------------------------------------------------------------------
# Save artifacts
# ---------------------------------------------------------------------------
def save_artifacts(champion_ensemble, champion_name, champion_metrics,
                   all_results, gates, all_pass, models, features):
    """Save champion_ensemble.pkl, ensemble_results.json, champion_metadata.json."""
    models_dir = os.path.join(ARTIFACT_DIR, "models")
    metrics_dir = os.path.join(ARTIFACT_DIR, "metrics")
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(metrics_dir, exist_ok=True)

    # 1) Champion ensemble pickle
    ensemble_path = os.path.join(models_dir, "champion_ensemble.pkl")
    champion_ensemble.save(ensemble_path)

    # 2) Ensemble results JSON
    ensemble_results = {
        "champion_strategy": champion_name,
        "strategies": {},
        "quality_gate": {k: bool(v) for k, v in gates.items()},
        "quality_gate_passed": all_pass,
        "base_models": list(models.keys()),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    for s_name, s_info in all_results.items():
        ensemble_results["strategies"][s_name] = s_info["metrics"]

    results_path = os.path.join(metrics_dir, "ensemble_results.json")
    with open(results_path, "w") as f:
        json.dump(ensemble_results, f, indent=2, default=str)
    log.info("Ensemble results saved to %s", results_path)

    # 3) Champion metadata JSON
    champion_metadata = {
        "model_type": "ensemble",
        "strategy": champion_name,
        "n_base_models": len(models),
        "base_models": list(models.keys()),
        "metrics": {
            "ks_oot": champion_metrics["ks_oot"],
            "auc_oot": champion_metrics["auc_oot"],
            "gini_oot": champion_metrics["gini_oot"],
            "psi": champion_metrics["psi"],
            "ks_train": champion_metrics["ks_train"],
            "auc_train": champion_metrics["auc_train"],
            "ks_oos": champion_metrics["ks_oos"],
            "auc_oos": champion_metrics["auc_oos"],
        },
        "n_features": len(features),
        "target": TARGET,
        "train_safras": TRAIN_SAFRAS,
        "oos_safras": OOS_SAFRA,
        "oot_safras": OOT_SAFRAS,
        "quality_gate_passed": all_pass,
        "quality_gate_details": {k: bool(v) for k, v in gates.items()},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    metadata_path = os.path.join(metrics_dir, "champion_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(champion_metadata, f, indent=2, default=str)
    log.info("Champion metadata saved to %s", metadata_path)

    return ensemble_path, results_path, metadata_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("=" * 60)
    log.info("Ensemble Model — OCI Data Science")
    log.info("=" * 60)
    log.info("ARTIFACT_DIR:    %s", ARTIFACT_DIR)
    log.info("LOCAL_DATA_PATH: %s", LOCAL_DATA_PATH)
    log.info("TARGET:          %s", TARGET)
    log.info("TRAIN_SAFRAS:    %s", TRAIN_SAFRAS)
    log.info("OOS_SAFRA:       %s", OOS_SAFRA)
    log.info("OOT_SAFRAS:      %s", OOT_SAFRAS)

    # --- Load models ---
    models = load_models()

    # --- Detect features from models (before loading data) ---
    # Try selected_features.json first, then model introspection
    sel_path = os.path.join(ARTIFACT_DIR, "selected_features.json")
    if os.path.exists(sel_path):
        import json as _json
        with open(sel_path) as _f:
            _sel = _json.load(_f)
        feature_cols = _sel["selected_features"]
        log.info("Loaded %d features from %s", len(feature_cols), sel_path)
    else:
        first_model = next(iter(models.values()))
        if hasattr(first_model, "feature_names_in_"):
            feature_cols = list(first_model.feature_names_in_)
        elif hasattr(first_model, "feature_name_"):
            feature_cols = list(first_model.feature_name_())
        else:
            feature_cols = None
            log.warning("Could not detect features from models, loading all columns")

    # --- Load data (only needed columns) ---
    df = load_data(columns=feature_cols)

    # --- Drop rows with NaN target ---
    nan_count = df[TARGET].isna().sum()
    if nan_count > 0:
        log.info("Dropping %d rows with NaN target", nan_count)
        df = df.dropna(subset=[TARGET])

    # --- Split ---
    df_train, df_oos, df_oot = split_data(df)

    # --- Detect features ---
    features = detect_features(df, models)
    if len(features) == 0:
        log.error("No features detected. Aborting.")
        sys.exit(1)

    X_train = df_train[features]
    y_train = df_train[TARGET]
    X_oos = df_oos[features]
    y_oos = df_oos[TARGET]
    X_oot = df_oot[features]
    y_oot = df_oot[TARGET]

    # --- Base predictions ---
    log.info("Generating base predictions...")
    preds_train = build_base_predictions(models, X_train)
    preds_oos = build_base_predictions(models, X_oos)
    preds_oot = build_base_predictions(models, X_oot)

    log.info("Prediction correlation (OOT):\n%s", preds_oot.corr().round(3))

    # --- Run all 3 strategies ---
    all_results = {}

    ens_avg, met_avg, pt_avg, po_avg, po_avg_oot = strategy_average(
        preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models,
    )
    all_results["average"] = {
        "ensemble": ens_avg, "metrics": met_avg,
        "preds_train": pt_avg, "preds_oos": po_avg, "preds_oot": po_avg_oot,
    }

    ens_blend, met_blend, pt_blend, po_blend, po_blend_oot = strategy_blend(
        preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models,
    )
    all_results["blend"] = {
        "ensemble": ens_blend, "metrics": met_blend,
        "preds_train": pt_blend, "preds_oos": po_blend, "preds_oot": po_blend_oot,
    }

    ens_stack, met_stack, pt_stack, po_stack, po_stack_oot = strategy_stacking(
        preds_oos, y_oos, preds_oot, y_oot, preds_train, y_train, models,
    )
    all_results["stacking"] = {
        "ensemble": ens_stack, "metrics": met_stack,
        "preds_train": pt_stack, "preds_oos": po_stack, "preds_oot": po_stack_oot,
    }

    # --- Champion selection: max KS OOT ---
    log.info("=" * 60)
    log.info("Strategy Comparison")
    log.info("=" * 60)
    comparison = []
    for name, info in all_results.items():
        m = info["metrics"]
        comparison.append({
            "strategy": name,
            "ks_oot": m["ks_oot"],
            "auc_oot": m["auc_oot"],
            "gini_oot": m["gini_oot"],
            "psi": m["psi"],
        })
    comparison_df = pd.DataFrame(comparison).sort_values("ks_oot", ascending=False)
    log.info("\n%s", comparison_df.to_string(index=False))

    champion_name = comparison_df.iloc[0]["strategy"]
    champion_metrics = all_results[champion_name]["metrics"]
    champion_ensemble = all_results[champion_name]["ensemble"]
    champion_ensemble.feature_names = features

    log.info(">>> Champion selected: %s (KS OOT = %.4f)",
             champion_name, champion_metrics["ks_oot"])

    # --- Quality Gate QG-05 ---
    gates, all_pass = validate_qg05(champion_metrics)

    # --- Generate plots ---
    plots_dir = os.path.join(ARTIFACT_DIR, "plots")
    generate_plots(all_results, y_oot, plots_dir)

    # --- Save artifacts ---
    ensemble_path, results_path, metadata_path = save_artifacts(
        champion_ensemble, champion_name, champion_metrics,
        all_results, gates, all_pass, models, features,
    )

    # --- Summary ---
    log.info("=" * 60)
    log.info("DONE — Ensemble Pipeline Complete")
    log.info("=" * 60)
    log.info("  Champion:    %s", champion_name)
    log.info("  KS OOT:     %.4f", champion_metrics["ks_oot"])
    log.info("  AUC OOT:    %.4f", champion_metrics["auc_oot"])
    log.info("  Gini OOT:   %.2f", champion_metrics["gini_oot"])
    log.info("  PSI:         %.6f", champion_metrics["psi"])
    log.info("  QG-05:       %s", "APPROVED" if all_pass else "REJECTED")
    log.info("  Artifacts:")
    log.info("    Model:     %s", ensemble_path)
    log.info("    Results:   %s", results_path)
    log.info("    Metadata:  %s", metadata_path)

    if not all_pass:
        log.warning("Quality gate QG-05 FAILED — review metrics before deployment.")
        sys.exit(2)


if __name__ == "__main__":
    main()
