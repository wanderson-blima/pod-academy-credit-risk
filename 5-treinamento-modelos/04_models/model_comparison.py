"""
Model Comparison — Phase 4.3
Side-by-side KS/AUC/Gini, feature importance comparison, decile tables.

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
    TARGET, TRAIN_SAFRAS, OOS_SAFRA, OOT_SAFRAS,
    compute_ks, compute_gini, compute_psi, evaluate_model,
)
from evaluate_model import generate_decile_table


def compare_models(pipelines, X_train, y_train, X_oos, y_oos, X_oot, y_oot):
    """Generate comprehensive model comparison."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("MODEL COMPARISON — Phase 4.3")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    comparison = []

    for name, pipeline in pipelines.items():
        print(f"\n{'─' * 50}")
        print(f"  {name}")
        print(f"{'─' * 50}")

        metrics_train = evaluate_model(pipeline, X_train, y_train, "train")
        metrics_oos = evaluate_model(pipeline, X_oos, y_oos, "oos")
        metrics_oot = evaluate_model(pipeline, X_oot, y_oot, "oot")

        # PSI
        train_scores = pipeline.predict_proba(X_train)[:, 1]
        oot_scores = pipeline.predict_proba(X_oot)[:, 1]
        psi = compute_psi(train_scores, oot_scores)

        # Overfitting gap
        gap = metrics_train["ks_train"] - metrics_oot["ks_oot"]

        all_metrics = {**metrics_train, **metrics_oos, **metrics_oot, "psi": psi, "overfit_gap": round(gap, 5)}

        # Quality gate checks
        qg_ks = metrics_oot["ks_oot"] > 0.20
        qg_auc = metrics_oot["auc_oot"] > 0.65
        qg_gini = metrics_oot["gini_oot"] > 30
        qg_psi = psi < 0.25
        qg_passed = all([qg_ks, qg_auc, qg_gini, qg_psi])

        print(f"    KS:  Train={metrics_train['ks_train']:.4f} | OOS={metrics_oos['ks_oos']:.4f} | OOT={metrics_oot['ks_oot']:.4f}")
        print(f"    AUC: Train={metrics_train['auc_train']:.4f} | OOS={metrics_oos['auc_oos']:.4f} | OOT={metrics_oot['auc_oot']:.4f}")
        print(f"    Gini OOT: {metrics_oot['gini_oot']:.2f}")
        print(f"    PSI: {psi:.6f} | Overfit gap: {gap:.4f}")
        print(f"    QG: {'PASS' if qg_passed else 'FAIL'} (KS>0.20={qg_ks}, AUC>0.65={qg_auc}, Gini>30={qg_gini}, PSI<0.25={qg_psi})")

        comparison.append({
            "Model": name,
            "KS_Train": metrics_train["ks_train"],
            "KS_OOS": metrics_oos["ks_oos"],
            "KS_OOT": metrics_oot["ks_oot"],
            "AUC_OOT": metrics_oot["auc_oot"],
            "Gini_OOT": metrics_oot["gini_oot"],
            "PSI": psi,
            "Overfit_Gap": round(gap, 5),
            "QG_Passed": qg_passed,
        })

    comp_df = pd.DataFrame(comparison).sort_values("KS_OOT", ascending=False)

    print(f"\n{'=' * 70}")
    print("COMPARISON TABLE")
    print(f"{'=' * 70}")
    print(comp_df.to_string(index=False))

    # Quality gate: at least 3 models pass
    n_passed = comp_df["QG_Passed"].sum()
    print(f"\n  Quality Gate QG-MM: {n_passed} models passed (need >= 3)")
    print(f"  Status: {'PASSED' if n_passed >= 3 else 'FAILED'}")

    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "comparison": comparison,
        "n_models_passed_qg": int(n_passed),
        "qg_mm_status": "PASSED" if n_passed >= 3 else "FAILED",
        "baseline_lgbm_ks_oot": 0.34027,
    }

    with open(os.path.join(MODELS_DIR, f"model_comparison_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    comp_df.to_csv(os.path.join(MODELS_DIR, f"model_comparison_{run_id}.csv"), index=False)

    print(f"\n[SAVE] Comparison saved to {MODELS_DIR}/")
    return comp_df, report


def compare_feature_importance(pipelines, features):
    """Compare feature importance rankings across models."""
    print(f"\n{'=' * 70}")
    print("FEATURE IMPORTANCE COMPARISON")
    print(f"{'=' * 70}")

    importance_data = {}

    for name, pipeline in pipelines.items():
        model = pipeline.named_steps["model"]

        if hasattr(model, "feature_importances_"):
            importance_data[name] = model.feature_importances_
        elif hasattr(model, "coef_"):
            importance_data[name] = np.abs(model.coef_[0])

    if not importance_data:
        print("  No feature importance data available")
        return None

    # Get transformed feature names
    prep = list(pipelines.values())[0].named_steps["prep"]
    from train_credit_risk import NUM_FEATURES, CAT_FEATURES
    num_feats_used = [f for f in features if f not in CAT_FEATURES]
    cat_feats_used = [f for f in features if f in CAT_FEATURES]
    transformed_names = [f"num__{f}" for f in num_feats_used] + [f"cat__{f}" for f in cat_feats_used]

    imp_df = pd.DataFrame({"feature": transformed_names})
    for name, imp in importance_data.items():
        if len(imp) == len(transformed_names):
            imp_df[name] = imp

    # Rank each model
    for name in importance_data:
        if name in imp_df.columns:
            imp_df[f"{name}_rank"] = imp_df[name].rank(ascending=False).astype(int)

    # Show top 15 by first model
    first_model = list(importance_data.keys())[0]
    top15 = imp_df.nlargest(15, first_model)
    print(f"\n  Top 15 features (by {first_model}):")
    rank_cols = [c for c in imp_df.columns if c.endswith("_rank")]
    print(top15[["feature"] + rank_cols].to_string(index=False))

    return imp_df


if __name__ == "__main__":
    print("Model Comparison — run compare_models(pipelines, X_train, y_train, X_oos, y_oos, X_oot, y_oot)")
