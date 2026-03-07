"""
Local Training Runner — Downloads data from OCI, trains locally, uploads artifacts.
Workaround for OCI Data Science trial resource limits.

Usage:
    python run_local_training.py
"""
import os
import sys
import json
import time
import pickle
import subprocess

# ── Set local paths BEFORE importing train_credit_risk ────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DATA_DIR = os.path.join(SCRIPT_DIR, "local_data", "feature_store", "clientes_consolidado")
LOCAL_ARTIFACT_DIR = os.path.join(SCRIPT_DIR, "local_artifacts")

os.makedirs(LOCAL_ARTIFACT_DIR, exist_ok=True)
os.makedirs(os.path.join(LOCAL_ARTIFACT_DIR, "models"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_ARTIFACT_DIR, "metrics"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_ARTIFACT_DIR, "scoring"), exist_ok=True)

# Monkey-patch the train_credit_risk module paths
import train_credit_risk as tcr
tcr.LOCAL_DATA_PATH = LOCAL_DATA_DIR
tcr.ARTIFACT_DIR = LOCAL_ARTIFACT_DIR
tcr.GOLD_PATH = LOCAL_DATA_DIR  # fallback reads from local too

print("=" * 70)
print("LOCAL TRAINING RUNNER")
print(f"Data path: {LOCAL_DATA_DIR}")
print(f"Artifact path: {LOCAL_ARTIFACT_DIR}")
print("=" * 70)

# ── Verify data is downloaded ────────────────────────────────────────────
if not os.path.exists(LOCAL_DATA_DIR):
    print(f"[ERROR] Data directory not found: {LOCAL_DATA_DIR}")
    print("  Run: oci os object bulk-download --bucket-name pod-academy-gold \\")
    print("       --namespace grlxi07jz1mo --prefix 'feature_store/clientes_consolidado/' \\")
    print("       --download-dir local_data")
    sys.exit(1)

parquet_files = [f for f in os.listdir(LOCAL_DATA_DIR) if f.endswith(".parquet")]
# Also check SAFRA subdirectories (partitioned data)
safra_dirs = [d for d in os.listdir(LOCAL_DATA_DIR) if d.startswith("SAFRA=")]
total_pq = len(parquet_files)
for sd in safra_dirs:
    sd_path = os.path.join(LOCAL_DATA_DIR, sd)
    total_pq += len([f for f in os.listdir(sd_path) if f.endswith(".parquet")])

print(f"[DATA] Found {total_pq} parquet files in {len(safra_dirs)} SAFRA partitions")

if total_pq == 0:
    print("[ERROR] No parquet files found. Data download may still be in progress.")
    sys.exit(1)

# ── Run training ─────────────────────────────────────────────────────────
print("\n[TRAIN] Starting training pipeline...")
lr_pipeline, lgbm_pipeline, results = tcr.train_and_evaluate()

# ── Run evaluation ───────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("RUNNING EVALUATION SUITE...")
print("=" * 70)

try:
    import evaluate_model as em
    em.ARTIFACT_DIR = LOCAL_ARTIFACT_DIR
    em.LOCAL_DATA_PATH = LOCAL_DATA_DIR
    eval_report = em.run_evaluation(lr_pipeline, lgbm_pipeline, results["run_id"])
    print(f"[EVAL] Evaluation report saved")
except Exception as e:
    print(f"[WARN] Evaluation suite error (non-fatal): {e}")

# ── Run batch scoring ────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("RUNNING BATCH SCORING...")
print("=" * 70)

try:
    import batch_scoring as bs
    bs.ARTIFACT_DIR = LOCAL_ARTIFACT_DIR
    bs.LOCAL_DATA_PATH = LOCAL_DATA_DIR
    bs.SCORES_OUTPUT_PATH = os.path.join(LOCAL_ARTIFACT_DIR, "scoring", "clientes_scores")

    import pyarrow.parquet as pq
    import pandas as pd

    columns_to_load = tcr.SELECTED_FEATURES + [tcr.TARGET, "SAFRA", "NUM_CPF"]
    df = pd.read_parquet(LOCAL_DATA_DIR, columns=columns_to_load)
    print(f"[SCORE] Loaded {len(df):,} records for scoring")

    scores_df = bs.score_batch(lgbm_pipeline, df)

    # Save locally
    local_scores_path = os.path.join(LOCAL_ARTIFACT_DIR, "scoring")
    os.makedirs(local_scores_path, exist_ok=True)
    scores_df.to_parquet(os.path.join(local_scores_path, "clientes_scores_all.parquet"), index=False)
    print(f"[SCORE] Saved {len(scores_df):,} scores to {local_scores_path}")
except Exception as e:
    print(f"[WARN] Batch scoring error (non-fatal): {e}")

# ── Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("LOCAL TRAINING COMPLETE")
print("=" * 70)
print(f"Run ID:     {results['run_id']}")
print(f"QG-05:      {results['quality_gate_qg05']}")
print(f"LR  KS OOT: {results['lr_metrics']['ks_oot']:.4f} | AUC: {results['lr_metrics']['auc_oot']:.4f}")
print(f"LGBM KS OOT: {results['lgbm_metrics']['ks_oot']:.4f} | AUC: {results['lgbm_metrics']['auc_oot']:.4f}")
print(f"\nArtifacts saved to: {LOCAL_ARTIFACT_DIR}")
print(f"  Models:  {LOCAL_ARTIFACT_DIR}/models/")
print(f"  Metrics: {LOCAL_ARTIFACT_DIR}/metrics/")
print(f"  Scores:  {LOCAL_ARTIFACT_DIR}/scoring/")

# Upload instructions
print(f"\nTo upload artifacts to OCI Object Storage:")
print(f"  oci os object bulk-upload --bucket-name pod-academy-gold \\")
print(f"    --namespace grlxi07jz1mo --src-dir {LOCAL_ARTIFACT_DIR} \\")
print(f"    --prefix model_artifacts/ --overwrite")
