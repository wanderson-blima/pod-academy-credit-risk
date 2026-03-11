"""
Feature Stability Analysis — Phase 1.2
SHAP values per SAFRA to check feature importance stability over time.
Focus on REC_DIAS_ENTRE_RECARGAS (PSI=1.35 RED drift).

Usage: Run in OCI Data Science notebook after model training.
"""
import os
import json
import pickle
import time
from datetime import datetime

NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    force_val = kw.pop("force_all_finite", None)
    if force_val is not None and "ensure_all_finite" not in kw:
        kw["ensure_all_finite"] = force_val
    return _original_check(*a, **kw)
_val.check_array = _patched_check

ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", "/home/datascience/artifacts")
DIAGNOSTIC_DIR = os.path.join(ARTIFACT_DIR, "diagnostic")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "oci", "model"))
from train_credit_risk import (
    SELECTED_FEATURES, CAT_FEATURES, NUM_FEATURES, TARGET,
    TRAIN_SAFRAS, OOT_SAFRAS, LOCAL_DATA_PATH, GOLD_PATH, compute_psi,
)

# Features with known drift
DRIFT_WATCH_FEATURES = [
    "REC_DIAS_ENTRE_RECARGAS",  # PSI=1.35 RED
    "REC_SCORE_RISCO",
    "TARGET_SCORE_02",
    "TARGET_SCORE_01",
]


def compute_shap_per_safra(pipeline, df, safras, sample_per_safra=2000):
    """Compute SHAP values for each SAFRA separately."""
    try:
        import shap
    except ImportError:
        print("[WARN] shap not installed. Using permutation importance as fallback.")
        return compute_permutation_importance_per_safra(pipeline, df, safras)

    lgbm_model = pipeline.named_steps["model"]
    prep = pipeline.named_steps["prep"]

    feature_names = [f"num__{f}" for f in NUM_FEATURES] + [f"cat__{f}" for f in CAT_FEATURES]
    shap_by_safra = {}

    for safra in safras:
        df_s = df[df["SAFRA"] == safra].copy()
        if len(df_s) < 100:
            continue

        # Sample for efficiency
        if len(df_s) > sample_per_safra:
            df_s = df_s.sample(sample_per_safra, random_state=42)

        X_s = df_s[SELECTED_FEATURES]
        X_transformed = prep.transform(X_s)

        explainer = shap.TreeExplainer(lgbm_model)
        shap_values = explainer.shap_values(X_transformed)

        # For binary classification, shap_values may be a list [class0, class1]
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        shap_df = pd.DataFrame({
            "feature": feature_names,
            "mean_abs_shap": mean_abs_shap,
        }).sort_values("mean_abs_shap", ascending=False)

        shap_by_safra[int(safra)] = shap_df.set_index("feature")["mean_abs_shap"].to_dict()
        print(f"  SAFRA {safra}: top feature = {shap_df.iloc[0]['feature']} "
              f"(SHAP={shap_df.iloc[0]['mean_abs_shap']:.4f})")

    return shap_by_safra


def compute_permutation_importance_per_safra(pipeline, df, safras, n_repeats=5):
    """Fallback: permutation importance when SHAP is not available."""
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import roc_auc_score

    importance_by_safra = {}

    for safra in safras:
        df_s = df[(df["SAFRA"] == safra) & (df[TARGET].notna())].copy()
        if len(df_s) < 100:
            continue

        X_s = df_s[SELECTED_FEATURES]
        y_s = df_s[TARGET].astype(int)

        result = permutation_importance(
            pipeline, X_s, y_s,
            scoring="roc_auc", n_repeats=n_repeats,
            random_state=42, n_jobs=NCPUS,
        )

        imp = pd.DataFrame({
            "feature": SELECTED_FEATURES,
            "importance_mean": result.importances_mean,
        }).sort_values("importance_mean", ascending=False)

        importance_by_safra[int(safra)] = imp.set_index("feature")["importance_mean"].to_dict()
        print(f"  SAFRA {safra}: top feature = {imp.iloc[0]['feature']} "
              f"(imp={imp.iloc[0]['importance_mean']:.4f})")

    return importance_by_safra


def analyze_rank_stability(importance_by_safra, top_n=20):
    """Check if feature importance ranking is stable across SAFRAs."""
    safras = sorted(importance_by_safra.keys())
    if len(safras) < 2:
        print("  [SKIP] Need at least 2 SAFRAs for stability analysis")
        return {}

    # Get top-N features per SAFRA
    top_features_by_safra = {}
    for safra in safras:
        features_sorted = sorted(
            importance_by_safra[safra].items(),
            key=lambda x: x[1], reverse=True,
        )[:top_n]
        top_features_by_safra[safra] = [f[0] for f in features_sorted]

    # Jaccard similarity between consecutive SAFRAs
    stability = {}
    for i in range(len(safras) - 1):
        s1, s2 = safras[i], safras[i + 1]
        set1 = set(top_features_by_safra[s1])
        set2 = set(top_features_by_safra[s2])
        jaccard = len(set1 & set2) / len(set1 | set2)
        stability[f"{s1}_vs_{s2}"] = round(jaccard, 4)
        print(f"  Top-{top_n} Jaccard ({s1} vs {s2}): {jaccard:.4f}")

    # Features that change rank by >5 positions
    rank_changes = {}
    all_features = set()
    for safra in safras:
        all_features.update(top_features_by_safra[safra])

    for feat in all_features:
        ranks = []
        for safra in safras:
            if feat in top_features_by_safra[safra]:
                ranks.append(top_features_by_safra[safra].index(feat) + 1)
            else:
                ranks.append(top_n + 1)
        max_change = max(ranks) - min(ranks)
        if max_change > 5:
            rank_changes[feat] = {
                "ranks": {str(s): r for s, r in zip(safras, ranks)},
                "max_change": max_change,
            }

    if rank_changes:
        print(f"\n  Features with rank change > 5 positions:")
        for feat, info in sorted(rank_changes.items(), key=lambda x: x[1]["max_change"], reverse=True):
            print(f"    {feat}: change={info['max_change']}, ranks={info['ranks']}")

    return {"jaccard_stability": stability, "volatile_features": rank_changes}


def analyze_drift_features(df, features=None):
    """PSI analysis for specific features across SAFRAs."""
    if features is None:
        features = DRIFT_WATCH_FEATURES

    available = [f for f in features if f in df.columns]
    safras = sorted(df["SAFRA"].unique())
    reference_safra = safras[0]

    drift_results = {}
    for feat in available:
        ref_vals = df[df["SAFRA"] == reference_safra][feat].dropna().values
        feat_drift = {}
        for safra in safras[1:]:
            curr_vals = df[df["SAFRA"] == safra][feat].dropna().values
            if len(ref_vals) < 100 or len(curr_vals) < 100:
                continue
            psi = compute_psi(ref_vals, curr_vals)
            status = "OK" if psi < 0.10 else ("WARNING" if psi < 0.25 else "RED")
            feat_drift[int(safra)] = {"psi": psi, "status": status}
            if status != "OK":
                print(f"  DRIFT: {feat} SAFRA {safra}: PSI={psi:.4f} [{status}]")

        drift_results[feat] = feat_drift

    return drift_results


def run_feature_stability():
    """Full feature stability analysis."""
    import pyarrow.parquet as pq
    import glob as glob_mod

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("DIAGNOSTIC: Feature Stability")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Load model
    lgbm_files = sorted(glob_mod.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))
    if not lgbm_files:
        print("[ERROR] No trained LGBM .pkl found.")
        return
    with open(lgbm_files[-1], "rb") as f:
        pipeline = pickle.load(f)

    # Load data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    all_safras = sorted(df["SAFRA"].unique())

    # 1. SHAP/Importance per SAFRA
    print("\n" + "-" * 70)
    print("1. FEATURE IMPORTANCE BY SAFRA")
    print("-" * 70)

    importance_by_safra = compute_shap_per_safra(pipeline, df, all_safras)

    # 2. Rank stability
    print("\n" + "-" * 70)
    print("2. RANK STABILITY ANALYSIS")
    print("-" * 70)

    stability = analyze_rank_stability(importance_by_safra)

    # 3. Drift analysis for watched features
    print("\n" + "-" * 70)
    print("3. DRIFT WATCH FEATURES")
    print("-" * 70)

    drift_results = analyze_drift_features(df)

    # Save
    os.makedirs(DIAGNOSTIC_DIR, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "importance_by_safra": importance_by_safra,
        "rank_stability": stability,
        "drift_watch": drift_results,
        "findings": [],
    }

    # Summarize findings
    for feat, drift in drift_results.items():
        for safra, info in drift.items():
            if info["status"] == "RED":
                report["findings"].append(
                    f"{feat} has RED drift (PSI={info['psi']:.4f}) at SAFRA {safra}"
                )

    if stability.get("volatile_features"):
        report["findings"].append(
            f"{len(stability['volatile_features'])} features show rank instability (>5 positions change)"
        )

    with open(os.path.join(DIAGNOSTIC_DIR, f"feature_stability_{run_id}.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[SAVE] Feature stability report saved to {DIAGNOSTIC_DIR}/")
    print(f"\n  Findings: {len(report['findings'])}")
    for finding in report["findings"]:
        print(f"    - {finding}")

    return report


if __name__ == "__main__":
    run_feature_stability()
