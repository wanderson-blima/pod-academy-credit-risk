"""
Validacao de Deploy — Confirma que scoring reproduz metricas da avaliacao.

Carrega o modelo do MLflow Registry, aplica sobre a SAFRA OOS (202501),
e compara KS/AUC/Gini com as metricas logadas no MLflow run original.
Tolerancia: +/- 0.5pp para KS/Gini, +/- 0.005 para AUC.

Story: Fase 4.4 — Deploy Validation

Uso:
    Executar apos scoring_batch.ipynb e antes de promote_to_production().
"""

import logging
import numpy as np
import pandas as pd
import mlflow
from mlflow.tracking import MlflowClient
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import (
    PATH_FEATURE_STORE, EXPERIMENT_NAME,
    SPARK_BROADCAST_THRESHOLD, SPARK_SHUFFLE_PARTITIONS, SPARK_AQE_ENABLED,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("validacao_deploy")

# =============================================================================
# PARAMETROS
# =============================================================================
MODEL_NAME = "credit-risk-fpd-lgbm_baseline"
MODEL_STAGE = "Staging"
VALIDATION_SAFRA = 202501  # OOS — SAFRA com FPD conhecido

# Tolerancias
TOL_KS = 0.5    # pp
TOL_GINI = 0.5  # pp
TOL_AUC = 0.005


def ks_stat(y_true, y_score):
    """Calcula KS statistic (0-100)."""
    if len(np.unique(y_true)) < 2:
        logger.warning("y_true tem apenas uma classe — KS indefinido")
        return np.nan
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    return ks_2samp(pos, neg).statistic * 100


def validate_deploy(spark):
    """Valida que o modelo em Staging reproduz metricas da avaliacao.

    Args:
        spark: SparkSession ativa.

    Returns:
        dict: Resultado da validacao com status PASS/FAIL.
    """
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(SPARK_BROADCAST_THRESHOLD))
    spark.conf.set("spark.sql.adaptive.enabled", str(SPARK_AQE_ENABLED).lower())
    spark.conf.set("spark.sql.shuffle.partitions", str(SPARK_SHUFFLE_PARTITIONS))

    logger.info("=== Validacao de Deploy ===")
    logger.info("Modelo: %s (%s)", MODEL_NAME, MODEL_STAGE)
    logger.info("SAFRA validacao: %d", VALIDATION_SAFRA)

    # -------------------------------------------------------------------------
    # 1. Carregar modelo
    # -------------------------------------------------------------------------
    client = MlflowClient()
    model_versions = client.get_latest_versions(MODEL_NAME, stages=[MODEL_STAGE])
    if not model_versions:
        raise RuntimeError(f"Nenhuma versao em {MODEL_STAGE} para '{MODEL_NAME}'")

    mv = model_versions[0]
    model_uri = f"models:/{MODEL_NAME}/{MODEL_STAGE}"
    model = mlflow.pyfunc.load_model(model_uri)
    logger.info("Modelo carregado: v%s (run_id=%s)", mv.version, mv.run_id)

    # -------------------------------------------------------------------------
    # 2. Recuperar feature names e metricas do run original
    # -------------------------------------------------------------------------
    import glob, json
    artifacts_path = client.download_artifacts(mv.run_id, "")
    metadata_files = glob.glob(f"{artifacts_path}/*metadata*.json")
    if not metadata_files:
        raise RuntimeError("Metadata JSON nao encontrado no MLflow run")

    with open(metadata_files[0]) as f:
        metadata = json.load(f)
    feature_names = metadata["feature_names"]

    # Metricas de referencia do run original
    run = client.get_run(mv.run_id)
    ref_metrics = run.data.metrics
    logger.info("Metricas de referencia do run: %s", {k: f"{v:.4f}" for k, v in ref_metrics.items()})

    # -------------------------------------------------------------------------
    # 3. Carregar dados OOS e predizer
    # -------------------------------------------------------------------------
    df = spark.read.format("delta").load(PATH_FEATURE_STORE) \
        .filter(f"SAFRA = {VALIDATION_SAFRA}")

    n_records = df.count()
    logger.info("Registros SAFRA %d: %d", VALIDATION_SAFRA, n_records)
    if n_records == 0:
        raise RuntimeError(f"Nenhum registro para SAFRA {VALIDATION_SAFRA}")

    df_pd = df.select(["FPD"] + feature_names).toPandas()
    y_true = df_pd["FPD"].values
    X = df_pd[feature_names]

    for col in X.columns:
        if X[col].dtype in ["float64", "float32", "int64", "int32"]:
            X[col] = X[col].fillna(0)
        else:
            X[col] = X[col].fillna("MISSING")

    scores = model.predict(X)
    if hasattr(model, '_model_impl'):
        inner = model._model_impl
        if hasattr(inner, 'predict_proba'):
            scores = inner.predict_proba(X)[:, 1]

    # -------------------------------------------------------------------------
    # 4. Calcular metricas
    # -------------------------------------------------------------------------
    ks = ks_stat(y_true, scores)
    auc = roc_auc_score(y_true, scores) if len(np.unique(y_true)) >= 2 else np.nan
    gini = (2 * auc - 1) * 100 if not np.isnan(auc) else np.nan

    logger.info("Metricas do scoring:")
    logger.info("  KS:   %.2f", ks)
    logger.info("  AUC:  %.4f", auc)
    logger.info("  Gini: %.2f", gini)

    # -------------------------------------------------------------------------
    # 5. Comparar com referencia
    # -------------------------------------------------------------------------
    results = {"ks": ks, "auc": auc, "gini": gini, "checks": []}

    # Tentar pegar metricas de referencia (nomes podem variar)
    ref_ks = ref_metrics.get("ks_oos", ref_metrics.get("ks_oot", None))
    ref_auc = ref_metrics.get("auc_oos", ref_metrics.get("auc_oot", None))
    ref_gini = ref_metrics.get("gini_oos", ref_metrics.get("gini_oot", None))

    if ref_ks is not None:
        # Normalizar para mesma escala (0-100)
        ref_ks_norm = ref_ks if ref_ks > 1 else ref_ks * 100
        delta_ks = abs(ks - ref_ks_norm)
        status = "PASS" if delta_ks <= TOL_KS else "FAIL"
        results["checks"].append({"metric": "KS", "ref": ref_ks_norm, "actual": ks, "delta": delta_ks, "status": status})
        logger.info("  KS delta: %.2f pp (%s)", delta_ks, status)

    if ref_auc is not None:
        delta_auc = abs(auc - ref_auc)
        status = "PASS" if delta_auc <= TOL_AUC else "FAIL"
        results["checks"].append({"metric": "AUC", "ref": ref_auc, "actual": auc, "delta": delta_auc, "status": status})
        logger.info("  AUC delta: %.4f (%s)", delta_auc, status)

    if ref_gini is not None:
        ref_gini_norm = ref_gini if ref_gini > 1 else ref_gini * 100
        delta_gini = abs(gini - ref_gini_norm)
        status = "PASS" if delta_gini <= TOL_GINI else "FAIL"
        results["checks"].append({"metric": "Gini", "ref": ref_gini_norm, "actual": gini, "delta": delta_gini, "status": status})
        logger.info("  Gini delta: %.2f pp (%s)", delta_gini, status)

    # -------------------------------------------------------------------------
    # 6. Veredicto
    # -------------------------------------------------------------------------
    if not results["checks"]:
        logger.warning("Nenhuma metrica de referencia encontrada no MLflow run — validacao manual necessaria")
        results["status"] = "MANUAL_REVIEW"
    elif all(c["status"] == "PASS" for c in results["checks"]):
        results["status"] = "PASS"
        logger.info("=== DEPLOY VALIDADO (PASS) ===")
    else:
        failed = [c["metric"] for c in results["checks"] if c["status"] == "FAIL"]
        results["status"] = "FAIL"
        logger.error("=== DEPLOY FALHOU — metricas divergentes: %s ===", failed)

    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# =============================================================================
result = validate_deploy(spark)
print(f"\nResultado: {result['status']}")
for c in result.get("checks", []):
    print(f"  {c['metric']}: ref={c['ref']:.3f}, actual={c['actual']:.3f}, delta={c['delta']:.4f} [{c['status']}]")
