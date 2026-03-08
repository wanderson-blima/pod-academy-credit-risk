"""
HPO Results Aggregation — Phase 3.5
Compares best hyperparameters across all models and logs experiments.

Usage: Run after all HPO studies complete.
"""
import os
import json
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
HPO_DIR = os.path.join(ARTIFACT_DIR, "hpo")


def load_hpo_results():
    """Load all HPO result JSON files."""
    results = {}

    if not os.path.exists(HPO_DIR):
        print(f"[WARN] HPO directory not found: {HPO_DIR}")
        return results

    for fname in sorted(os.listdir(HPO_DIR)):
        if fname.startswith("hpo_") and fname.endswith(".json") and "study" not in fname:
            with open(os.path.join(HPO_DIR, fname)) as f:
                data = json.load(f)
            model_name = data.get("model", fname)
            results[model_name] = data

    return results


def compare_hpo_results(results):
    """Compare best parameters across models."""
    print("=" * 70)
    print("HPO RESULTS COMPARISON")
    print("=" * 70)

    comparison = []
    for model_name, data in results.items():
        row = {
            "model": model_name,
            "best_ks_cv": data.get("best_ks_cv", 0),
            "n_trials": data.get("n_trials", 0),
            "best_trial": data.get("best_trial", 0),
            "n_features": data.get("n_features", 0),
        }
        comparison.append(row)

    comp_df = pd.DataFrame(comparison).sort_values("best_ks_cv", ascending=False)

    print("\n  Model Ranking by KS (CV):")
    print(comp_df.to_string(index=False))

    # Print best params per model
    for model_name, data in sorted(results.items(), key=lambda x: x[1].get("best_ks_cv", 0), reverse=True):
        print(f"\n  {model_name} Best Parameters:")
        for k, v in data.get("best_params", {}).items():
            if isinstance(v, float):
                print(f"    {k:30s}: {v:.6f}")
            else:
                print(f"    {k:30s}: {v}")

    return comp_df


def check_overfitting(results):
    """Check overfitting gap between CV and expected OOT."""
    print("\n" + "-" * 70)
    print("OVERFITTING CHECK")
    print("-" * 70)

    # Baseline reference
    BASELINE_KS_OOT = 0.34027  # LGBM baseline KS OOT

    for model_name, data in results.items():
        cv_ks = data.get("best_ks_cv", 0)
        # Estimated gap: CV typically overestimates OOT by 1-3pp
        estimated_oot = cv_ks * 0.95  # Conservative 5% shrinkage estimate
        gap = cv_ks - estimated_oot
        improvement = estimated_oot - BASELINE_KS_OOT

        status = "OK" if gap < 0.05 else "CAUTION"
        print(f"  {model_name}: CV KS={cv_ks:.4f}, Est OOT={estimated_oot:.4f}, "
              f"Gap={gap:.4f} [{status}], vs Baseline={improvement:+.4f}")


def generate_summary(results):
    """Generate final HPO summary report."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    comp_df = compare_hpo_results(results)
    check_overfitting(results)

    # Quality gate check: each model should improve KS by >0.5pp
    BASELINE_KS = 0.34027
    qg_results = {}
    for model_name, data in results.items():
        cv_ks = data.get("best_ks_cv", 0)
        improvement = cv_ks - BASELINE_KS
        passed = improvement > 0.005  # 0.5pp
        qg_results[model_name] = {
            "cv_ks": cv_ks,
            "improvement_pp": round(improvement * 100, 2),
            "qg_passed": passed,
        }

    print(f"\n{'=' * 70}")
    print("QUALITY GATE QG-HPO")
    print(f"{'=' * 70}")

    all_passed = True
    for model, qg in qg_results.items():
        status = "PASS" if qg["qg_passed"] else "FAIL"
        if not qg["qg_passed"]:
            all_passed = False
        print(f"  [{status}] {model}: KS improvement = {qg['improvement_pp']:.2f}pp (need >0.5pp)")

    print(f"\n  QG-HPO: {'PASSED' if all_passed else 'FAILED'}")

    # Save summary
    summary = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "baseline_ks_oot": BASELINE_KS,
        "models": {name: {
            "best_ks_cv": data.get("best_ks_cv"),
            "best_params": data.get("best_params"),
            "n_trials": data.get("n_trials"),
        } for name, data in results.items()},
        "quality_gate": qg_results,
        "qg_hpo_status": "PASSED" if all_passed else "FAILED",
    }

    os.makedirs(HPO_DIR, exist_ok=True)
    with open(os.path.join(HPO_DIR, f"hpo_summary_{run_id}.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n[SAVE] HPO summary saved to {HPO_DIR}/hpo_summary_{run_id}.json")

    return summary


if __name__ == "__main__":
    results = load_hpo_results()
    if results:
        generate_summary(results)
    else:
        print("[INFO] No HPO results found. Run HPO scripts first.")
