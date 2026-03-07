"""
Model Evaluation Suite — OCI Data Science
Phase 5: Decile table, swap analysis, PSI, Fabric parity comparison.

Runs AFTER train_credit_risk.py. Loads trained pipelines and generates
full evaluation report for Quality Gate QG-05.

Usage:
    Run in OCI Data Science notebook after training completes.
    Expects trained pipeline .pkl files in ARTIFACT_DIR/models/
"""
import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import ks_2samp

# ── Threading (match training config) ──────────────────────────────────────
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

# ── sklearn compatibility patch ────────────────────────────────────────────
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

import warnings
warnings.filterwarnings("ignore")

# Import shared config from training script
from train_credit_risk import (
    SELECTED_FEATURES, CAT_FEATURES, NUM_FEATURES, TARGET,
    TRAIN_SAFRAS, OOS_SAFRA, OOT_SAFRAS,
    FABRIC_BASELINE, ARTIFACT_DIR,
    GOLD_PATH, LOCAL_DATA_PATH,
    compute_ks, compute_gini, compute_psi,
)

# ═══════════════════════════════════════════════════════════════════════════
# DECILE TABLE
# ═══════════════════════════════════════════════════════════════════════════

def generate_decile_table(y_true, y_prob, label=""):
    """Generate decile table with rank ordering validation."""
    df_eval = pd.DataFrame({"target": y_true.values, "prob": y_prob})
    df_eval["decile"] = pd.qcut(df_eval["prob"], q=10, labels=False, duplicates="drop") + 1

    table = df_eval.groupby("decile").agg(
        count=("target", "count"),
        events=("target", "sum"),
        avg_prob=("prob", "mean"),
        min_prob=("prob", "min"),
        max_prob=("prob", "max"),
    ).reset_index()

    table["non_events"] = table["count"] - table["events"]
    table["event_rate"] = table["events"] / table["count"]
    table["cum_events"] = table["events"].cumsum()
    table["cum_non_events"] = table["non_events"].cumsum()
    table["cum_event_pct"] = table["cum_events"] / table["events"].sum()
    table["cum_non_event_pct"] = table["cum_non_events"] / table["non_events"].sum()
    table["ks"] = abs(table["cum_event_pct"] - table["cum_non_event_pct"])
    table["lift"] = table["event_rate"] / (table["events"].sum() / table["count"].sum())

    is_monotonic = table["event_rate"].is_monotonic_increasing
    ks_max = table["ks"].max()

    print(f"\n  Decile Table ({label}) — Monotonic: {is_monotonic} | KS max: {ks_max:.4f}")
    print(table[["decile", "count", "events", "event_rate", "cum_event_pct", "ks", "lift"]]
          .to_string(index=False, float_format="%.4f"))

    return table, is_monotonic

# ═══════════════════════════════════════════════════════════════════════════
# SWAP ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════

def swap_analysis(pipeline, df_1, df_2, safra_1_label, safra_2_label, bins=10):
    """Analyze rank stability between two SAFRA periods."""
    scores_1 = pipeline.predict_proba(df_1[SELECTED_FEATURES])[:, 1]
    scores_2 = pipeline.predict_proba(df_2[SELECTED_FEATURES])[:, 1]

    deciles_1 = pd.qcut(scores_1, q=bins, labels=False, duplicates="drop") + 1
    deciles_2 = pd.qcut(scores_2, q=bins, labels=False, duplicates="drop") + 1

    swap_matrix = pd.crosstab(
        pd.Series(deciles_1, name=f"Decile_{safra_1_label}"),
        pd.Series(deciles_2, name=f"Decile_{safra_2_label}"),
        normalize="index",
    )

    diagonal = np.diag(swap_matrix.values) if swap_matrix.shape[0] == swap_matrix.shape[1] else []
    stability = np.mean(diagonal) if len(diagonal) > 0 else 0.0

    print(f"\n  Swap Analysis: {safra_1_label} vs {safra_2_label}")
    print(f"  Rank stability (diagonal avg): {stability:.2%}")
    print(f"  Swap rate: {1 - stability:.2%}")

    return swap_matrix, stability

# ═══════════════════════════════════════════════════════════════════════════
# FEATURE PSI
# ═══════════════════════════════════════════════════════════════════════════

def feature_psi_analysis(X_train, X_oot, pipeline, top_n=20):
    """Compute PSI for top features by importance."""
    lgbm_model = pipeline.named_steps["model"]
    transformed_names = [f"num__{f}" for f in NUM_FEATURES] + [f"cat__{f}" for f in CAT_FEATURES]

    importance = pd.Series(lgbm_model.feature_importances_, index=transformed_names)
    top_features_transformed = importance.nlargest(top_n).index.tolist()

    # Map transformed names back to original
    prep = pipeline.named_steps["prep"]
    X_train_t = prep.transform(X_train)
    X_oot_t = prep.transform(X_oot)

    if hasattr(X_train_t, "toarray"):
        X_train_t = X_train_t.toarray()
    if hasattr(X_oot_t, "toarray"):
        X_oot_t = X_oot_t.toarray()

    psi_results = {}
    for i, feat_name in enumerate(transformed_names):
        if feat_name in top_features_transformed:
            psi_val = compute_psi(X_train_t[:, i], X_oot_t[:, i])
            psi_results[feat_name] = psi_val

    psi_df = pd.DataFrame({
        "feature": psi_results.keys(),
        "psi": psi_results.values(),
    }).sort_values("psi", ascending=False)

    drifted = psi_df[psi_df["psi"] > 0.25]

    print(f"\n  Feature PSI (top {top_n}):")
    print(psi_df.to_string(index=False, float_format="%.6f"))

    if len(drifted) > 0:
        print(f"\n  WARNING: {len(drifted)} features with PSI > 0.25:")
        print(drifted.to_string(index=False))

    return psi_df

# ═══════════════════════════════════════════════════════════════════════════
# FULL EVALUATION REPORT
# ═══════════════════════════════════════════════════════════════════════════

def run_evaluation(lr_pipeline, lgbm_pipeline, run_id=None):
    """Full evaluation suite: decile, swap, PSI, parity, quality gate."""
    import pyarrow.parquet as pq

    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("MODEL EVALUATION SUITE")
    print(f"Run ID: {run_id}")
    print("=" * 70)

    # Load data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    df_train = df[df["SAFRA"].isin(TRAIN_SAFRAS) & df[TARGET].notna()]
    df_oos = df[df["SAFRA"].isin(OOS_SAFRA) & df[TARGET].notna()]
    df_oot = df[df["SAFRA"].isin(OOT_SAFRAS) & df[TARGET].notna()]

    X_train = df_train[SELECTED_FEATURES]
    y_train = df_train[TARGET].astype(int)
    X_oos = df_oos[SELECTED_FEATURES]
    y_oos = df_oos[TARGET].astype(int)
    X_oot = df_oot[SELECTED_FEATURES]
    y_oot = df_oot[TARGET].astype(int)

    report = {"run_id": run_id, "timestamp": datetime.now().isoformat()}

    # ── 1. Decile Tables ───────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("1. DECILE TABLES")
    print("-" * 70)

    for model_name, pipeline in [("LR L1", lr_pipeline), ("LightGBM", lgbm_pipeline)]:
        print(f"\n  === {model_name} ===")
        y_prob_oos = pipeline.predict_proba(X_oos)[:, 1]
        y_prob_oot = pipeline.predict_proba(X_oot)[:, 1]

        decile_oos, mono_oos = generate_decile_table(y_oos, y_prob_oos, f"{model_name} OOS")
        decile_oot, mono_oot = generate_decile_table(y_oot, y_prob_oot, f"{model_name} OOT")

        report[f"{model_name.lower().replace(' ', '_')}_decile_oos_monotonic"] = mono_oos
        report[f"{model_name.lower().replace(' ', '_')}_decile_oot_monotonic"] = mono_oot

        # Save CSVs
        decile_oos.to_csv(f"{ARTIFACT_DIR}/metrics/decile_{model_name.lower().replace(' ', '_')}_oos_{run_id}.csv", index=False)
        decile_oot.to_csv(f"{ARTIFACT_DIR}/metrics/decile_{model_name.lower().replace(' ', '_')}_oot_{run_id}.csv", index=False)

    # ── 2. Swap Analysis ──────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("2. SWAP ANALYSIS (Rank Stability)")
    print("-" * 70)

    for model_name, pipeline in [("LR L1", lr_pipeline), ("LightGBM", lgbm_pipeline)]:
        print(f"\n  === {model_name} ===")
        swap_mat, stability = swap_analysis(pipeline, df_oos, df_oot, "OOS_202501", "OOT_202502-03")
        report[f"{model_name.lower().replace(' ', '_')}_swap_stability"] = round(stability, 4)

        swap_mat.to_csv(f"{ARTIFACT_DIR}/metrics/swap_{model_name.lower().replace(' ', '_')}_{run_id}.csv")

    # ── 3. Feature PSI ────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("3. FEATURE PSI (Data Drift Detection)")
    print("-" * 70)

    psi_df = feature_psi_analysis(X_train, X_oot, lgbm_pipeline, top_n=20)
    psi_df.to_csv(f"{ARTIFACT_DIR}/metrics/feature_psi_{run_id}.csv", index=False)
    report["features_with_psi_gt_025"] = int((psi_df["psi"] > 0.25).sum())

    # ── 4. Score Distribution ─────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("4. SCORE DISTRIBUTION")
    print("-" * 70)

    for model_name, pipeline in [("LR L1", lr_pipeline), ("LightGBM", lgbm_pipeline)]:
        scores_oot = ((1 - pipeline.predict_proba(X_oot)[:, 1]) * 1000).astype(int).clip(0, 1000)

        def risk_band(s):
            if s < 300: return "CRITICO"
            elif s < 500: return "ALTO"
            elif s < 700: return "MEDIO"
            else: return "BAIXO"

        bands = pd.Series([risk_band(s) for s in scores_oot])
        dist = bands.value_counts().to_dict()
        print(f"\n  {model_name} OOT score distribution:")
        for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
            count = dist.get(band, 0)
            pct = count / len(scores_oot) * 100
            print(f"    {band:10s}: {count:>8,} ({pct:.1f}%)")

    # ── 5. Summary Report ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    with open(f"{ARTIFACT_DIR}/metrics/evaluation_report_{run_id}.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n[SAVE] Evaluation report: {ARTIFACT_DIR}/metrics/evaluation_report_{run_id}.json")

    return report


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Load latest trained models and run evaluation
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import glob

    # Find latest model artifacts
    lr_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/lr_l1_oci_*.pkl"))
    lgbm_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))

    if not lr_files or not lgbm_files:
        print("[ERROR] No trained model .pkl files found. Run train_credit_risk.py first.")
        exit(1)

    print(f"[LOAD] LR:   {lr_files[-1]}")
    print(f"[LOAD] LGBM: {lgbm_files[-1]}")

    with open(lr_files[-1], "rb") as f:
        lr_pipeline = pickle.load(f)
    with open(lgbm_files[-1], "rb") as f:
        lgbm_pipeline = pickle.load(f)

    run_evaluation(lr_pipeline, lgbm_pipeline)
