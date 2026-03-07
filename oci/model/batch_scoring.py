"""
Batch Scoring — OCI Data Science
Scores all customers using trained LightGBM pipeline.
Output: clientes_scores table (8 columns) in Gold bucket.

Usage:
    Run in OCI Data Science notebook after training and evaluation.
    Loads the latest trained LGBM pipeline from ARTIFACT_DIR.
"""
import os
import json
import pickle
import uuid
import glob
import numpy as np
import pandas as pd
from datetime import datetime

# Threading
NCPUS = int(os.environ.get("NOTEBOOK_OCPUS", "10"))
os.environ["OMP_NUM_THREADS"] = str(NCPUS)
os.environ["OPENBLAS_NUM_THREADS"] = str(NCPUS)
os.environ["MKL_NUM_THREADS"] = "1"

# sklearn compat patch
import sklearn.utils.validation as _val
_original_check = _val.check_array
def _patched_check(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _original_check(*a, **kw)
_val.check_array = _patched_check

import warnings
warnings.filterwarnings("ignore")

from train_credit_risk import (
    SELECTED_FEATURES, TARGET, ARTIFACT_DIR,
    GOLD_PATH, LOCAL_DATA_PATH,
    NAMESPACE, GOLD_BUCKET,
)

# ═══════════════════════════════════════════════════════════════════════════
# SCORING
# ═══════════════════════════════════════════════════════════════════════════

SCORES_OUTPUT_PATH = f"oci://{GOLD_BUCKET}@{NAMESPACE}/clientes_scores/"
MODEL_VERSION = "lgbm-oci-v1"


def risk_band(score):
    """Classify score into risk band (0-1000 scale)."""
    if score < 300:
        return "CRITICO"
    elif score < 500:
        return "ALTO"
    elif score < 700:
        return "MEDIO"
    else:
        return "BAIXO"


def score_batch(pipeline, df):
    """Score all customers and generate clientes_scores output."""
    execution_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[SCORE] Scoring {len(df):,} records...")
    X = df[SELECTED_FEATURES]

    # Generate probabilities
    probabilities = pipeline.predict_proba(X)[:, 1]

    # Convert to 0-1000 score (higher = lower risk)
    scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)

    # Build output DataFrame — matches Gold.clientes_scores schema (8 columns)
    result = pd.DataFrame({
        "NUM_CPF": df["NUM_CPF"].values,
        "SAFRA": df["SAFRA"].values,
        "SCORE": scores,
        "FAIXA_RISCO": [risk_band(s) for s in scores],
        "PROBABILIDADE_FPD": probabilities.round(6),
        "MODELO_VERSAO": MODEL_VERSION,
        "DATA_SCORING": timestamp,
        "EXECUTION_ID": execution_id,
    })

    # Distribution summary
    print(f"\n[SCORE] Distribution:")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        count = (result["FAIXA_RISCO"] == band).sum()
        pct = count / len(result) * 100
        print(f"  {band:10s}: {count:>8,} ({pct:.1f}%)")

    print(f"\n[SCORE] Score stats: mean={scores.mean():.0f}, "
          f"median={int(np.median(scores))}, "
          f"min={scores.min()}, max={scores.max()}")

    return result


def save_scores(scores_df, output_path=None):
    """Write scores to Gold bucket as Parquet, partitioned by SAFRA."""
    if output_path is None:
        output_path = SCORES_OUTPUT_PATH

    print(f"\n[SAVE] Writing {len(scores_df):,} scores to {output_path}")

    # Write partitioned by SAFRA
    for safra in sorted(scores_df["SAFRA"].unique()):
        safra_df = scores_df[scores_df["SAFRA"] == safra]
        safra_path = f"{output_path}SAFRA={safra}/scores.parquet"
        safra_df.drop(columns=["SAFRA"]).to_parquet(safra_path, index=False)
        print(f"  SAFRA {safra}: {len(safra_df):,} records")

    # Also save local copy
    local_path = f"{ARTIFACT_DIR}/scoring"
    os.makedirs(local_path, exist_ok=True)
    scores_df.to_parquet(f"{local_path}/clientes_scores_all.parquet", index=False)
    print(f"[SAVE] Local copy: {local_path}/clientes_scores_all.parquet")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pyarrow.parquet as pq

    print("=" * 70)
    print("BATCH SCORING — OCI Data Science")
    print("=" * 70)

    # Load latest trained LightGBM pipeline
    lgbm_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))
    if not lgbm_files:
        print("[ERROR] No trained LGBM .pkl found. Run train_credit_risk.py first.")
        exit(1)

    print(f"[LOAD] Model: {lgbm_files[-1]}")
    with open(lgbm_files[-1], "rb") as f:
        lgbm_pipeline = pickle.load(f)

    # Load all data
    columns_to_load = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]
    if os.path.exists(LOCAL_DATA_PATH):
        table = pq.read_table(LOCAL_DATA_PATH, columns=columns_to_load)
        df = table.to_pandas(self_destruct=True)
    else:
        df = pd.read_parquet(GOLD_PATH, columns=columns_to_load)

    print(f"[DATA] Loaded {len(df):,} records, {len(df['SAFRA'].unique())} SAFRAs")

    # Score all records
    scores_df = score_batch(lgbm_pipeline, df)

    # Validate output schema (8 columns)
    expected_cols = {"NUM_CPF", "SAFRA", "SCORE", "FAIXA_RISCO",
                     "PROBABILIDADE_FPD", "MODELO_VERSAO", "DATA_SCORING", "EXECUTION_ID"}
    assert set(scores_df.columns) == expected_cols, f"Schema mismatch: {set(scores_df.columns)}"
    print(f"\n[VALIDATE] Output schema: {len(scores_df.columns)} columns — OK")

    # Save to Gold
    save_scores(scores_df)

    print(f"\n[DONE] Batch scoring complete: {len(scores_df):,} records scored")
