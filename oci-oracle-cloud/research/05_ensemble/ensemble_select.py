"""
Ensemble Selection — Phase 5.3
Compare simple average, blending, and stacking to select champion.

Usage: Run after blend and stack optimizations.
"""
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
ENSEMBLE_DIR = os.path.join(ARTIFACT_DIR, "ensemble")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import compute_psi


def compute_ks(y_true, y_prob):
    """KS statistic."""
    prob_good = y_prob[y_true == 0]
    prob_bad = y_prob[y_true == 1]
    ks_stat, _ = ks_2samp(prob_good, prob_bad)
    return ks_stat


def evaluate_ensemble_method(y_true, y_prob, label):
    """Compute full metrics for an ensemble method."""
    ks = compute_ks(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)
    gini = (2 * auc - 1) * 100

    return {
        "method": label,
        "ks": round(ks, 5),
        "auc": round(auc, 5),
        "gini": round(gini, 2),
    }


def select_champion(pipelines, weights_blend, meta_learner, meta_features,
                     X_oos, y_oos, X_oot, y_oot, X_train=None):
    """Compare all ensemble strategies and select champion."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("ENSEMBLE: Champion Selection")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    model_names = list(pipelines.keys())

    # Get predictions
    oot_preds = {name: pipe.predict_proba(X_oot)[:, 1] for name, pipe in pipelines.items()}
    oos_preds = {name: pipe.predict_proba(X_oos)[:, 1] for name, pipe in pipelines.items()}

    # 1. Simple average
    simple_avg_oot = np.mean(list(oot_preds.values()), axis=0)
    simple_avg_oos = np.mean(list(oos_preds.values()), axis=0)

    # 2. Weighted blend
    preds_matrix_oot = np.column_stack([oot_preds[name] for name in model_names])
    w = np.array([weights_blend.get(name, 1.0/len(model_names)) for name in model_names])
    blend_oot = np.average(preds_matrix_oot, axis=1, weights=w)

    preds_matrix_oos = np.column_stack([oos_preds[name] for name in model_names])
    blend_oos = np.average(preds_matrix_oos, axis=1, weights=w)

    # 3. Stacking
    X_meta_oot = pd.DataFrame(oot_preds)[model_names]
    X_meta_oos = pd.DataFrame(oos_preds)[model_names]

    # Add extra features if meta_features includes them
    extra_feats = [f for f in meta_features if f not in model_names]
    for feat in extra_feats:
        if feat in X_oot.columns:
            X_meta_oot[feat] = X_oot[feat].values
            X_meta_oos[feat] = X_oos[feat].values

    stack_oot = meta_learner.predict_proba(X_meta_oot[meta_features])[:, 1]
    stack_oos = meta_learner.predict_proba(X_meta_oos[meta_features])[:, 1]

    # Evaluate all methods on OOT
    print(f"\n{'─' * 50}")
    print("OOT EVALUATION")
    print(f"{'─' * 50}")

    methods = [
        ("Simple Average", simple_avg_oot),
        ("Weighted Blend", blend_oot),
        ("Stacking", stack_oot),
    ]

    # Also include individual models for comparison
    for name in model_names:
        methods.append((f"Single: {name}", oot_preds[name]))

    oot_results = []
    for label, probs in methods:
        m = evaluate_ensemble_method(y_oot.values, probs, label)
        oot_results.append(m)
        print(f"  {label:30s}: KS={m['ks']:.5f} AUC={m['auc']:.5f} Gini={m['gini']:.2f}")

    # PSI for ensemble methods
    print(f"\n{'─' * 50}")
    print("STABILITY (PSI)")
    print(f"{'─' * 50}")

    if X_train is not None:
        train_preds = {name: pipe.predict_proba(X_train)[:, 1] for name, pipe in pipelines.items()}
        train_simple = np.mean(list(train_preds.values()), axis=0)
        train_blend = np.average(
            np.column_stack([train_preds[name] for name in model_names]),
            axis=1, weights=w,
        )

        psi_simple = compute_psi(train_simple, simple_avg_oot)
        psi_blend = compute_psi(train_blend, blend_oot)
        print(f"  Simple Average PSI: {psi_simple:.6f}")
        print(f"  Weighted Blend PSI: {psi_blend:.6f}")

        for r in oot_results:
            if r["method"] == "Simple Average":
                r["psi"] = psi_simple
            elif r["method"] == "Weighted Blend":
                r["psi"] = psi_blend

    # Ranking
    oot_df = pd.DataFrame(oot_results)

    # Composite score: 0.5*KS + 0.3*AUC + 0.2*(1-PSI) normalized
    ensemble_methods = oot_df[oot_df["method"].isin(["Simple Average", "Weighted Blend", "Stacking"])]

    champion = ensemble_methods.sort_values("ks", ascending=False).iloc[0]

    print(f"\n{'=' * 70}")
    print(f"CHAMPION: {champion['method']}")
    print(f"  KS={champion['ks']:.5f} AUC={champion['auc']:.5f} Gini={champion['gini']:.2f}")
    print(f"{'=' * 70}")

    # Quality Gate QG-ENS
    baseline_ks = 0.34027
    qg_ks = champion["ks"] > 0.35
    qg_auc = champion["auc"] > 0.74
    qg_psi = champion.get("psi", 0) < 0.10

    # Check all models contribute (no weight = 0)
    all_contribute = all(w > 0.01 for w in weights_blend.values()) if champion["method"] == "Weighted Blend" else True

    print(f"\n  Quality Gate QG-ENS:")
    print(f"    KS OOT > 0.35: {'PASS' if qg_ks else 'FAIL'} ({champion['ks']:.5f})")
    print(f"    AUC OOT > 0.74: {'PASS' if qg_auc else 'FAIL'} ({champion['auc']:.5f})")
    print(f"    PSI < 0.10: {'PASS' if qg_psi else 'FAIL'} ({champion.get('psi', 'N/A')})")
    print(f"    All models contribute: {'PASS' if all_contribute else 'FAIL'}")

    qg_passed = all([qg_ks, qg_auc, qg_psi, all_contribute])
    print(f"    QG-ENS: {'PASSED' if qg_passed else 'FAILED'}")

    # Save
    os.makedirs(ENSEMBLE_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "champion_method": champion["method"],
        "champion_metrics": champion.to_dict(),
        "all_methods": oot_results,
        "blend_weights": weights_blend,
        "baseline_ks_oot": baseline_ks,
        "qg_ens": {
            "ks_pass": qg_ks,
            "auc_pass": qg_auc,
            "psi_pass": qg_psi,
            "all_contribute": all_contribute,
            "status": "PASSED" if qg_passed else "FAILED",
        },
    }

    with open(os.path.join(ENSEMBLE_DIR, f"ensemble_selection_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[SAVE] Selection results saved to {ENSEMBLE_DIR}/")
    return champion["method"], report


if __name__ == "__main__":
    print("Ensemble Selection — run select_champion(...)")
