"""
Data Science Job Entry Point — Batch Scoring
Runs as an OCI Data Science Job (triggered by orchestrator after Gold pipeline).

Usage:
    Configured as job entry point in Terraform oci_datascience_job resource.
    Receives environment variables from job configuration.

Environment:
    COMPARTMENT_OCID: Compartment for the job
    OCI_NAMESPACE: Object Storage namespace
    GOLD_BUCKET: Gold bucket name
    MODEL_PATH: Path to model artifact in Object Storage
    SCORING_OUTPUT: Output path for scores
"""
import os
import sys
import json
import pickle
import uuid
import numpy as np
import pandas as pd
from datetime import datetime

# Threading
NCPUS = int(os.environ.get("JOB_OCPUS", os.cpu_count() or 4))
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

# Configuration
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = os.environ.get("GOLD_BUCKET", "pod-academy-gold")
MODEL_PATH = os.environ.get("MODEL_PATH", "/home/datascience/model/ensemble_model.pkl")
SCORING_OUTPUT = os.environ.get("SCORING_OUTPUT",
    f"oci://{GOLD_BUCKET}@{NAMESPACE}/clientes_scores/")

# 59 selected features (from config.py)
SELECTED_FEATURES = [
    "TARGET_SCORE_02", "TARGET_SCORE_01",
    "REC_SCORE_RISCO", "REC_TAXA_STATUS_A", "REC_QTD_LINHAS",
    "REC_DIAS_ENTRE_RECARGAS", "REC_QTD_INST_DIST_REG",
    "REC_DIAS_DESDE_ULTIMA_RECARGA", "REC_TAXA_CARTAO_ONLINE",
    "REC_QTD_STATUS_ZB2", "REC_QTD_CARTAO_ONLINE",
    "REC_COEF_VARIACAO_REAL", "var_26",
    "FAT_DIAS_MEDIO_CRIACAO_VENCIMENTO", "REC_VLR_CREDITO_STDDEV",
    "REC_TAXA_PLAT_PREPG", "REC_VLR_REAL_STDDEV",
    "REC_QTD_CARTAO_CHIPPRE", "REC_QTD_PLANOS", "REC_QTD_PLAT_AUTOC",
    "PAG_QTD_PAGAMENTOS_TOTAL", "FAT_QTD_FATURAS_PRIMEIRA", "var_73",
    "REC_QTD_STATUS_ZB1", "FAT_TAXA_PRIMEIRA_FAT", "FAT_DIAS_ATRASO_MIN",
    "PAG_TAXA_PAGAMENTOS_COM_JUROS", "FAT_DIAS_MAX_CRIACAO_VENCIMENTO",
    "REC_COEF_VARIACAO_CREDITO", "PAG_DIAS_ENTRE_FATURAS",
    "FAT_DIAS_DESDE_ATIVACAO_CONTA", "var_85", "REC_FREQ_RECARGA_DIARIA",
    "FAT_DIAS_DESDE_ULTIMA_FAT", "FAT_DIAS_DESDE_PRIMEIRA_FAT",
    "PAG_QTD_FATURAS_DISTINTAS", "var_82", "PAG_DIAS_DESDE_ULTIMA_FATURA",
    "REC_TAXA_PLAT_CONTROLE", "var_90", "PAG_TAXA_FORMA_PA",
    "PAG_QTD_PAGAMENTOS_COM_JUROS", "PAG_QTD_AREAS",
    "FAT_DIAS_ATRASO_MEDIO", "REC_QTD_RECARGAS_TOTAL", "var_28", "var_44",
    "PAG_VLR_PAGAMENTO_FATURA_STDDEV", "REC_QTD_TIPOS_RECARGA",
    "var_34", "FAT_QTD_FAT_PREPG", "PAG_FLAG_ALTO_RISCO", "var_67",
    "REC_QTD_PLATAFORMAS", "PAG_QTD_STATUS_R",
    "PAG_COEF_VARIACAO_PAGAMENTO", "FAT_QTD_FATURAS_ACA",
    "REC_QTD_INSTITUICOES", "FAT_QTD_SAFRAS_DISTINTAS",
]

TARGET = "FPD"


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


def load_model():
    """Load model from local path or Object Storage."""
    if os.path.exists(MODEL_PATH):
        print(f"[LOAD] Loading model from: {MODEL_PATH}")
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)

    # Try downloading from Object Storage
    import oci
    config = oci.config.from_file()
    os_client = oci.object_storage.ObjectStorageClient(config)

    model_obj_name = "model_artifacts/ensemble/ensemble_model.pkl"
    print(f"[LOAD] Downloading model from Object Storage: {model_obj_name}")

    response = os_client.get_object(NAMESPACE, GOLD_BUCKET, model_obj_name)
    model_data = response.data.content

    local_path = "/tmp/ensemble_model.pkl"
    with open(local_path, "wb") as f:
        f.write(model_data)

    with open(local_path, "rb") as f:
        return pickle.load(f)


def load_data():
    """Load Gold feature store data."""
    data_path = f"oci://{GOLD_BUCKET}@{NAMESPACE}/feature_store/clientes_final/"
    local_path = os.environ.get("DATA_PATH", "/home/datascience/data/clientes_final/")

    columns = SELECTED_FEATURES + [TARGET, "SAFRA", "NUM_CPF"]

    if os.path.exists(local_path):
        import pyarrow.parquet as pq
        table = pq.read_table(local_path, columns=columns)
        return table.to_pandas(self_destruct=True)

    # Read from Object Storage
    return pd.read_parquet(data_path, columns=columns)


def score_all(pipeline, df):
    """Score all customers."""
    execution_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[SCORE] Scoring {len(df):,} records...")
    X = df[SELECTED_FEATURES]
    probabilities = pipeline.predict_proba(X)[:, 1]
    scores = ((1 - probabilities) * 1000).astype(int).clip(0, 1000)

    result = pd.DataFrame({
        "NUM_CPF": df["NUM_CPF"].values,
        "SAFRA": df["SAFRA"].values,
        "SCORE": scores,
        "FAIXA_RISCO": [risk_band(s) for s in scores],
        "PROBABILIDADE_FPD": probabilities.round(6),
        "MODELO_VERSAO": "ensemble-v1-job",
        "DATA_SCORING": timestamp,
        "EXECUTION_ID": execution_id,
    })

    # Distribution
    print(f"\n[SCORE] Distribution:")
    for band in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        count = (result["FAIXA_RISCO"] == band).sum()
        pct = count / len(result) * 100
        print(f"  {band:10s}: {count:>8,} ({pct:.1f}%)")

    return result


def save_scores(scores_df):
    """Save scores to Object Storage."""
    print(f"\n[SAVE] Writing {len(scores_df):,} scores...")

    # Save locally first
    local_dir = "/home/datascience/output"
    os.makedirs(local_dir, exist_ok=True)
    local_file = f"{local_dir}/clientes_scores_all.parquet"
    scores_df.to_parquet(local_file, index=False)
    print(f"  Local: {local_file}")

    # Upload to Object Storage
    try:
        import oci
        config = oci.config.from_file()
        os_client = oci.object_storage.ObjectStorageClient(config)

        for safra in sorted(scores_df["SAFRA"].unique()):
            safra_df = scores_df[scores_df["SAFRA"] == safra]
            safra_file = f"/tmp/scores_safra_{safra}.parquet"
            safra_df.to_parquet(safra_file, index=False)

            obj_name = f"clientes_scores/SAFRA={safra}/scores.parquet"
            with open(safra_file, "rb") as f:
                os_client.put_object(NAMESPACE, GOLD_BUCKET, obj_name, f)
            print(f"  Uploaded: {obj_name} ({len(safra_df):,} records)")
    except Exception as e:
        print(f"  [WARN] Upload to Object Storage failed: {e}")
        print(f"  Scores available locally at: {local_file}")


def main():
    print("=" * 70)
    print("BATCH SCORING JOB — OCI Data Science")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"CPUs: {NCPUS}")
    print("=" * 70)

    # Load model
    pipeline = load_model()
    print(f"[MODEL] Loaded (type={type(pipeline).__name__})")

    # Load data
    df = load_data()
    print(f"[DATA] Loaded {len(df):,} records, {len(df['SAFRA'].unique())} SAFRAs")

    # Score
    scores_df = score_all(pipeline, df)

    # Validate schema
    expected_cols = {"NUM_CPF", "SAFRA", "SCORE", "FAIXA_RISCO",
                     "PROBABILIDADE_FPD", "MODELO_VERSAO", "DATA_SCORING", "EXECUTION_ID"}
    assert set(scores_df.columns) == expected_cols, f"Schema mismatch: {set(scores_df.columns)}"

    # Save
    save_scores(scores_df)

    print(f"\n[DONE] Batch scoring complete: {len(scores_df):,} records scored")


if __name__ == "__main__":
    main()
