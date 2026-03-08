"""
Ensemble Blending — Phase 5.1
Weighted average ensemble with optimized weights (SLSQP on OOS).

Usage: Run after multi-model training.
"""
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
ENSEMBLE_DIR = os.path.join(ARTIFACT_DIR, "ensemble")


def compute_ks(y_true, y_prob):
    """KS statistic."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def optimize_blend_weights(base_predictions, y_true, metric="ks"):
    """Find optimal blend weights using SLSQP optimization.

    Args:
        base_predictions: dict of {model_name: probabilities}
        y_true: true labels
        metric: "ks" or "auc" to optimize

    Returns: dict of {model_name: weight}
    """
    model_names = list(base_predictions.keys())
    preds_matrix = np.column_stack([base_predictions[name] for name in model_names])
    n_models = len(model_names)

    def objective(weights):
        blended = np.average(preds_matrix, axis=1, weights=weights)
        if metric == "ks":
            return -compute_ks(y_true, blended)
        else:
            return -roc_auc_score(y_true, blended)

    # Constraints: weights >= 0, sum = 1
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    bounds = [(0, 1)] * n_models
    initial = np.ones(n_models) / n_models

    result = minimize(
        objective, initial,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000},
    )

    optimal_weights = result.x
    optimal_metric = -result.fun

    weights_dict = {name: round(float(w), 4) for name, w in zip(model_names, optimal_weights)}

    print(f"  Optimized weights (metric={metric}):")
    for name, w in weights_dict.items():
        print(f"    {name:20s}: {w:.4f}")
    print(f"  Optimal {metric.upper()}: {optimal_metric:.5f}")

    return weights_dict, optimal_metric


def blend_predictions(base_predictions, weights):
    """Compute weighted average of base model predictions."""
    model_names = list(base_predictions.keys())
    preds_matrix = np.column_stack([base_predictions[name] for name in model_names])
    w = np.array([weights.get(name, 0) for name in model_names])
    return np.average(preds_matrix, axis=1, weights=w)


def evaluate_blend(base_predictions, weights, y_true, label=""):
    """Evaluate blended ensemble predictions."""
    blended = blend_predictions(base_predictions, weights)

    ks = compute_ks(y_true, blended)
    auc = roc_auc_score(y_true, blended)
    gini = (2 * auc - 1) * 100

    print(f"  Blend {label}: KS={ks:.5f} AUC={auc:.5f} Gini={gini:.2f}")

    return {
        f"ks_{label}": round(ks, 5),
        f"auc_{label}": round(auc, 5),
        f"gini_{label}": round(gini, 2),
    }


def run_blend_optimization(pipelines, X_oos, y_oos, X_oot, y_oot, X_train=None, y_train=None):
    """Full blending pipeline: optimize on OOS, evaluate on OOT."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("ENSEMBLE: Weighted Blending")
    print(f"Run ID: {run_id} | Models: {len(pipelines)}")
    print("=" * 70)

    # Get OOS predictions for weight optimization
    oos_preds = {name: pipe.predict_proba(X_oos)[:, 1] for name, pipe in pipelines.items()}
    oot_preds = {name: pipe.predict_proba(X_oot)[:, 1] for name, pipe in pipelines.items()}

    # 1. Optimize weights on OOS (NOT on OOT)
    print(f"\n{'─' * 50}")
    print("1. WEIGHT OPTIMIZATION (on OOS)")
    print(f"{'─' * 50}")

    weights_ks, opt_ks = optimize_blend_weights(oos_preds, y_oos.values, metric="ks")
    weights_auc, opt_auc = optimize_blend_weights(oos_preds, y_oos.values, metric="auc")

    # 2. Evaluate on OOS (in-sample for weights)
    print(f"\n{'─' * 50}")
    print("2. BLEND EVALUATION (OOS — in-sample)")
    print(f"{'─' * 50}")

    oos_metrics_ks = evaluate_blend(oos_preds, weights_ks, y_oos.values, "oos_ks_opt")
    oos_metrics_auc = evaluate_blend(oos_preds, weights_auc, y_oos.values, "oos_auc_opt")

    # 3. Evaluate on OOT (true out-of-time)
    print(f"\n{'─' * 50}")
    print("3. BLEND EVALUATION (OOT — out-of-time)")
    print(f"{'─' * 50}")

    oot_metrics_ks = evaluate_blend(oot_preds, weights_ks, y_oot.values, "oot_ks_opt")
    oot_metrics_auc = evaluate_blend(oot_preds, weights_auc, y_oot.values, "oot_auc_opt")

    # 4. Simple average baseline
    print(f"\n{'─' * 50}")
    print("4. SIMPLE AVERAGE BASELINE")
    print(f"{'─' * 50}")

    equal_weights = {name: 1.0 / len(pipelines) for name in pipelines}
    simple_oot = evaluate_blend(oot_preds, equal_weights, y_oot.values, "oot_simple")

    # Select best weighting strategy
    best_strategy = "ks_opt" if oot_metrics_ks.get("ks_oot_ks_opt", 0) >= oot_metrics_auc.get("ks_oot_auc_opt", 0) else "auc_opt"
    best_weights = weights_ks if best_strategy == "ks_opt" else weights_auc

    print(f"\n{'=' * 70}")
    print(f"BEST STRATEGY: {best_strategy}")
    print(f"Best weights: {best_weights}")
    print(f"{'=' * 70}")

    # Save
    os.makedirs(ENSEMBLE_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "n_models": len(pipelines),
        "model_names": list(pipelines.keys()),
        "weights_ks_opt": weights_ks,
        "weights_auc_opt": weights_auc,
        "equal_weights": equal_weights,
        "best_strategy": best_strategy,
        "best_weights": best_weights,
        "metrics": {
            "oos_ks_opt": oos_metrics_ks,
            "oos_auc_opt": oos_metrics_auc,
            "oot_ks_opt": oot_metrics_ks,
            "oot_auc_opt": oot_metrics_auc,
            "oot_simple_avg": simple_oot,
        },
    }

    with open(os.path.join(ENSEMBLE_DIR, f"blend_results_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    with open(os.path.join(ENSEMBLE_DIR, f"blend_weights_{run_id}.pkl"), "wb") as f:
        pickle.dump(best_weights, f)

    print(f"\n[SAVE] Blend results saved to {ENSEMBLE_DIR}/")
    return best_weights, report


if __name__ == "__main__":
    print("Ensemble Blending — run run_blend_optimization(pipelines, X_oos, y_oos, X_oot, y_oot)")
