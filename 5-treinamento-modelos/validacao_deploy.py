"""
Validacao de Deploy — Confirma que scoring reproduz metricas da avaliacao.

Carrega o modelo do MLflow Registry, aplica sobre a SAFRA OOS (202501),
e compara KS/AUC/Gini com as metricas logadas no MLflow run original.
Tolerancia: +/- 0.5pp para KS/Gini, +/- 0.005 para AUC.

Story: Fase 4.4 — Deploy Validation

Uso:
    Executar apos scoring_batch.ipynb e antes de promote_to_production().
"""

import glob      # M1: moved from function body to top-level
import json      # M1: moved from function body to top-level
import logging
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype  # M2: proper numeric type detection
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
    # M1: glob and json imports moved to top-level
    artifacts_path = client.download_artifacts(mv.run_id, "")
    metadata_files = glob.glob(f"{artifacts_path}/*metadata*.json")
    if not metadata_files:
        raise RuntimeError("Metadata JSON nao encontrado no MLflow run")

    # M4: Log which metadata file was loaded
    logger.info("Metadata carregado de: %s", metadata_files[0])
    with open(metadata_files[0]) as f:
        metadata = json.load(f)
    feature_names = metadata.get("feature_names", [])

    # H3: Validate that feature_names is a non-empty list
    if not isinstance(feature_names, list) or len(feature_names) == 0:
        raise RuntimeError(
            "feature_names ausente ou vazio no metadata JSON — "
            "impossivel selecionar colunas para scoring"
        )

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

    # H5: Validate all feature_names exist in DataFrame columns before .select()
    df_columns = set(df.columns)
    missing_cols = [col for col in feature_names if col not in df_columns]
    if missing_cols:
        raise RuntimeError(
            f"{len(missing_cols)} feature(s) ausente(s) no DataFrame: "
            f"{missing_cols[:10]}{'...' if len(missing_cols) > 10 else ''}"
        )

    df_pd = df.select(["FPD"] + feature_names).toPandas()

    # H2: Validate FPD is binary {0,1} and not all null
    y_true = df_pd["FPD"].values
    if pd.isna(y_true).all():
        raise RuntimeError("FPD e inteiramente nulo — impossivel validar modelo")
    fpd_unique = set(pd.Series(y_true).dropna().unique())
    if not fpd_unique.issubset({0, 1, 0.0, 1.0}):
        raise RuntimeError(
            f"FPD contem valores nao-binarios: {fpd_unique - {0, 1, 0.0, 1.0}} — "
            "esperado apenas {{0, 1}}"
        )

    X = df_pd[feature_names]

    # M3: fillna strategy — numeric columns filled with 0 (neutral value for tree-based
    # models and does not shift distributions significantly); categorical/string columns
    # filled with "MISSING" (explicit sentinel category that the model was trained with).
    for col in X.columns:
        # M2: Use pandas.api.types.is_numeric_dtype() instead of raw dtype comparison
        if is_numeric_dtype(X[col]):
            X[col] = X[col].fillna(0)
        else:
            X[col] = X[col].fillna("MISSING")

    # H1+M5: Try predict_proba first (continuous probabilities), fallback to predict
    scores = None
    if hasattr(model, '_model_impl'):
        inner = model._model_impl
        if hasattr(inner, 'predict_proba'):
            try:
                scores = inner.predict_proba(X)[:, 1]
            except Exception as e:
                raise RuntimeError(
                    f"predict_proba() falhou ({type(e).__name__}): {e}"
                ) from e
        else:
            logger.warning(
                "_model_impl encontrado mas sem predict_proba — "
                "fallback para predict() (scores podem ser classes, nao probabilidades)"
            )
    else:
        logger.warning(
            "_model_impl nao encontrado no modelo pyfunc — "
            "fallback para predict() (scores podem ser classes, nao probabilidades)"
        )

    # Fallback: model.predict() se predict_proba nao disponivel
    if scores is None:
        try:
            scores = model.predict(X)
        except Exception as e:
            raise RuntimeError(
                f"model.predict() falhou ({type(e).__name__}): {e} — "
                "verifique compatibilidade de features e tipos de dados"
            ) from e

    # -------------------------------------------------------------------------
    # 4. Calcular metricas
    # -------------------------------------------------------------------------
    ks = ks_stat(y_true, scores)
    auc = roc_auc_score(y_true, scores) if len(np.unique(y_true)) >= 2 else np.nan
    gini = (2 * auc - 1) * 100 if not np.isnan(auc) else np.nan

    logger.info("Metricas do scoring:")
    logger.info("  KS:   %.2f", ks if not np.isnan(ks) else float("nan"))
    logger.info("  AUC:  %.4f", auc if not np.isnan(auc) else float("nan"))
    logger.info("  Gini: %.2f", gini if not np.isnan(gini) else float("nan"))

    # -------------------------------------------------------------------------
    # 5. Comparar com referencia
    # -------------------------------------------------------------------------
    results = {"ks": ks, "auc": auc, "gini": gini, "checks": []}

    # C1: If any computed metric is NaN, add explicit FAIL check entry
    if np.isnan(ks):
        results["checks"].append({
            "metric": "KS", "ref": None, "actual": float("nan"),
            "delta": float("nan"), "status": "FAIL",
            "reason": "KS computado e NaN (possivelmente y_true tem apenas uma classe)"
        })
        logger.error("KS e NaN — FAIL automatico")
    if np.isnan(auc):
        results["checks"].append({
            "metric": "AUC", "ref": None, "actual": float("nan"),
            "delta": float("nan"), "status": "FAIL",
            "reason": "AUC computado e NaN (possivelmente y_true tem apenas uma classe)"
        })
        logger.error("AUC e NaN — FAIL automatico")
    if np.isnan(gini):
        results["checks"].append({
            "metric": "Gini", "ref": None, "actual": float("nan"),
            "delta": float("nan"), "status": "FAIL",
            "reason": "Gini computado e NaN (derivado de AUC NaN)"
        })
        logger.error("Gini e NaN — FAIL automatico")

    # Tentar pegar metricas de referencia (nomes podem variar)
    ref_ks = ref_metrics.get("ks_oos", ref_metrics.get("ks_oot", None))
    ref_auc = ref_metrics.get("auc_oos", ref_metrics.get("auc_oot", None))
    ref_gini = ref_metrics.get("gini_oos", ref_metrics.get("gini_oot", None))

    # C3/H4: Scale detection — use > 2.0 as heuristic threshold.
    # KS and Gini values between 1 and 2 are valid in the 0-100 scale
    # (e.g., KS=1.5 means 1.5%), so > 1 incorrectly triggers normalization.
    # Values > 2.0 in 0-1 scale are impossible, so > 2.0 safely distinguishes scales.
    SCALE_THRESHOLD = 2.0

    if ref_ks is not None and not np.isnan(ks):
        # Normalizar para mesma escala (0-100)
        ref_ks_norm = ref_ks if ref_ks > SCALE_THRESHOLD else ref_ks * 100
        delta_ks = abs(ks - ref_ks_norm)
        status = "PASS" if delta_ks <= TOL_KS else "FAIL"
        results["checks"].append({"metric": "KS", "ref": ref_ks_norm, "actual": ks, "delta": delta_ks, "status": status})
        logger.info("  KS delta: %.2f pp (%s)", delta_ks, status)

    if ref_auc is not None and not np.isnan(auc):
        delta_auc = abs(auc - ref_auc)
        status = "PASS" if delta_auc <= TOL_AUC else "FAIL"
        results["checks"].append({"metric": "AUC", "ref": ref_auc, "actual": auc, "delta": delta_auc, "status": status})
        logger.info("  AUC delta: %.4f (%s)", delta_auc, status)

    if ref_gini is not None and not np.isnan(gini):
        ref_gini_norm = ref_gini if ref_gini > SCALE_THRESHOLD else ref_gini * 100
        delta_gini = abs(gini - ref_gini_norm)
        status = "PASS" if delta_gini <= TOL_GINI else "FAIL"
        results["checks"].append({"metric": "Gini", "ref": ref_gini_norm, "actual": gini, "delta": delta_gini, "status": status})
        logger.info("  Gini delta: %.2f pp (%s)", delta_gini, status)

    # C2: Required metrics must be present — FAIL (not MANUAL_REVIEW) if missing.
    # KS and AUC are required for deploy validation; Gini is derived and optional.
    REQUIRED_METRICS = {"KS", "AUC"}
    metrics_with_checks = {c["metric"] for c in results["checks"]}
    missing_required = REQUIRED_METRICS - metrics_with_checks
    if missing_required:
        for m in sorted(missing_required):
            results["checks"].append({
                "metric": m, "ref": None, "actual": None,
                "delta": None, "status": "FAIL",
                "reason": f"Metrica de referencia '{m}' nao encontrada no MLflow run "
                          f"(chaves tentadas: {m.lower()}_oos, {m.lower()}_oot)"
            })
            logger.error(
                "Metrica de referencia '%s' ausente no MLflow run — FAIL", m
            )

    # -------------------------------------------------------------------------
    # 6. Veredicto
    # -------------------------------------------------------------------------
    if all(c["status"] == "PASS" for c in results["checks"]):
        results["status"] = "PASS"
        logger.info("=== DEPLOY VALIDADO (PASS) ===")
    else:
        failed = [c["metric"] for c in results["checks"] if c["status"] == "FAIL"]
        reasons = [c.get("reason", "") for c in results["checks"] if c["status"] == "FAIL" and c.get("reason")]
        results["status"] = "FAIL"
        logger.error("=== DEPLOY FALHOU — metricas divergentes: %s ===", failed)
        if reasons:
            for reason in reasons:
                logger.error("  Detalhe: %s", reason)

    return results


# =============================================================================
# EXECUCAO PRINCIPAL
# Guard: so executa automaticamente se 'spark' estiver no escopo global
# (padrao Fabric notebooks). Previne execucao acidental em import.
# =============================================================================
if "spark" in dir() and spark is not None:
    result = validate_deploy(spark)
    print(f"\nResultado: {result['status']}")
    for c in result.get("checks", []):
        ref_str = f"{c['ref']:.3f}" if c['ref'] is not None else "N/A"
        actual_str = f"{c['actual']:.3f}" if c['actual'] is not None and not np.isnan(c['actual']) else "NaN"
        delta_str = f"{c['delta']:.4f}" if c['delta'] is not None and not np.isnan(c['delta']) else "N/A"
        reason_str = f" ({c['reason']})" if c.get('reason') else ""
        print(f"  {c['metric']}: ref={ref_str}, actual={actual_str}, delta={delta_str} [{c['status']}]{reason_str}")
