"""
Model Diversity Analysis — Phase 4.2
Pairwise prediction correlation and Cohen's Kappa for decile agreement.

Usage: Run after multi-model training.
"""
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
MODELS_DIR = os.path.join(ARTIFACT_DIR, "models_v2")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    TARGET, TRAIN_SAFRAS, OOT_SAFRAS, LOCAL_DATA_PATH, GOLD_PATH,
)


def prediction_correlation(pipelines, X, labels=None):
    """Compute pairwise Pearson correlation of predicted probabilities."""
    if labels is None:
        labels = list(pipelines.keys())

    preds = {}
    for name, pipe in pipelines.items():
        preds[name] = pipe.predict_proba(X)[:, 1]

    pred_df = pd.DataFrame(preds)
    corr = pred_df.corr()

    print("\n  Prediction Correlation Matrix:")
    print(corr.round(4).to_string())

    # Find pairs with correlation > 0.98 (too similar)
    high_corr = []
    names = list(preds.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            c = corr.loc[names[i], names[j]]
            if c > 0.98:
                high_corr.append((names[i], names[j], round(float(c), 4)))

    if high_corr:
        print(f"\n  WARNING: {len(high_corr)} pairs with correlation > 0.98:")
        for n1, n2, c in high_corr:
            print(f"    {n1} x {n2}: {c}")
    else:
        print(f"\n  All pairs have correlation < 0.98 — good diversity")

    return corr, high_corr


def cohens_kappa_deciles(pipelines, X, n_deciles=10):
    """Cohen's Kappa for decile assignment agreement."""
    from sklearn.metrics import cohen_kappa_score

    decile_assignments = {}
    for name, pipe in pipelines.items():
        probs = pipe.predict_proba(X)[:, 1]
        deciles = pd.qcut(probs, q=n_deciles, labels=False, duplicates="drop")
        decile_assignments[name] = deciles

    names = list(pipelines.keys())
    kappa_matrix = pd.DataFrame(
        np.eye(len(names)),
        index=names, columns=names,
    )

    kappa_pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            kappa = cohen_kappa_score(
                decile_assignments[names[i]],
                decile_assignments[names[j]],
            )
            kappa_matrix.loc[names[i], names[j]] = kappa
            kappa_matrix.loc[names[j], names[i]] = kappa
            kappa_pairs.append((names[i], names[j], round(float(kappa), 4)))

    print("\n  Cohen's Kappa (Decile Agreement):")
    print(kappa_matrix.round(4).to_string())

    return kappa_matrix, kappa_pairs


def diversity_report(pipelines, X, y):
    """Generate full diversity report."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("MODEL DIVERSITY ANALYSIS")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # 1. Prediction correlation
    print(f"\n{'─' * 50}")
    print("1. PREDICTION CORRELATION")
    print(f"{'─' * 50}")

    corr, high_corr = prediction_correlation(pipelines, X)

    # 2. Cohen's Kappa
    print(f"\n{'─' * 50}")
    print("2. COHEN'S KAPPA (DECILE AGREEMENT)")
    print(f"{'─' * 50}")

    kappa_matrix, kappa_pairs = cohens_kappa_deciles(pipelines, X)

    # 3. Disagreement analysis — where models diverge most
    print(f"\n{'─' * 50}")
    print("3. DISAGREEMENT ANALYSIS")
    print(f"{'─' * 50}")

    preds = {name: pipe.predict_proba(X)[:, 1] for name, pipe in pipelines.items()}
    pred_df = pd.DataFrame(preds)
    pred_df["std"] = pred_df.std(axis=1)
    pred_df["range"] = pred_df.max(axis=1) - pred_df.min(axis=1)
    pred_df["y_true"] = y.values

    # High disagreement cases
    high_disagree = pred_df[pred_df["std"] > pred_df["std"].quantile(0.95)]
    print(f"  High disagreement cases (top 5% by std): {len(high_disagree):,}")
    if len(high_disagree) > 0:
        print(f"    Default rate in high-disagree: {high_disagree['y_true'].mean():.4f}")
        print(f"    Default rate overall: {y.mean():.4f}")

    # Quality gate: at least 2 pairs with correlation < 0.90
    names = list(pipelines.keys())
    low_corr_pairs = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if corr.loc[names[i], names[j]] < 0.90:
                low_corr_pairs += 1

    qg_passed = low_corr_pairs >= 2
    print(f"\n{'=' * 70}")
    print(f"QUALITY GATE QG-MM (Diversity)")
    print(f"  Pairs with corr < 0.90: {low_corr_pairs} (need >= 2)")
    print(f"  Status: {'PASSED' if qg_passed else 'FAILED'}")
    print(f"{'=' * 70}")

    # Save
    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "prediction_correlation": corr.to_dict(),
        "high_correlation_pairs": [
            {"model_1": p[0], "model_2": p[1], "corr": p[2]} for p in high_corr
        ],
        "kappa_pairs": [
            {"model_1": p[0], "model_2": p[1], "kappa": p[2]} for p in kappa_pairs
        ],
        "low_corr_pairs_count": low_corr_pairs,
        "qg_diversity_passed": qg_passed,
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(os.path.join(MODELS_DIR, f"diversity_analysis_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[SAVE] Diversity analysis saved to {MODELS_DIR}/")
    return report


if __name__ == "__main__":
    print("Diversity Analysis — run diversity_report(pipelines, X, y)")
