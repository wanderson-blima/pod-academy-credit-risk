"""
Monitoramento de Drift — PSI de Score e Features + Performance Check.

Compara distribuicoes de scores e features entre baseline (treino) e SAFRA
atual, gerando alertas quando thresholds sao violados.

Fase 5: Monitoring Setup (5.1 Baseline + 5.2 Thresholds + 5.3 Script)

Uso:
    Executar mensalmente apos scoring_batch.ipynb para cada nova SAFRA.
    Ajustar MONITOR_SAFRA antes de executar.
"""

import glob
import logging
import json
from datetime import datetime

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
logger = logging.getLogger("monitoramento_drift")

# =============================================================================
# PARAMETROS
# =============================================================================
MODEL_NAME = "credit-risk-fpd-lgbm_baseline"
MODEL_STAGE = "Production"

BASELINE_SAFRAS = [202410, 202411, 202412]  # SAFRAs de treino
MONITOR_SAFRA = 202503                       # SAFRA a monitorar

TOP_N_FEATURES = 20  # Top features para drift check

# =============================================================================
# THRESHOLDS (5.2)
# =============================================================================
THRESHOLDS = {
    "psi_score_green": 0.10,
    "psi_score_yellow": 0.25,
    "psi_feature_green": 0.10,
    "psi_feature_yellow": 0.20,
    "ks_drift_max_pp": 5.0,
    "gini_drift_max_pp": 5.0,
    "auc_drift_max": 0.03,
}


# =============================================================================
# FUNCOES UTILITARIAS
# =============================================================================

def calculate_psi(expected, actual, n_bins=10):
    """Population Stability Index entre duas distribuicoes.

    Args:
        expected: Array baseline (treino).
        actual: Array atual (monitoramento).
        n_bins: Numero de bins para discretizacao.

    Returns:
        float: PSI value. < 0.10 = estavel, 0.10-0.25 = atencao, > 0.25 = instavel.
               Returns NaN if bins collapse below 3 (e.g., zero-inflated features).
    """
    if len(expected) == 0 or len(actual) == 0:
        return np.nan

    breakpoints = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    # Remover breakpoints duplicados (pode ocorrer em features zero-inflated)
    breakpoints = np.unique(breakpoints)

    # C5: Se bins colapsaram demais, PSI nao e confiavel — retornar NaN
    if len(breakpoints) < 3:
        logger.warning(
            "PSI: breakpoints colapsaram para %d valores unicos (minimo 3 necessarios). "
            "Feature provavelmente zero-inflated ou constante. Retornando NaN.",
            len(breakpoints),
        )
        return np.nan

    expected_percents = np.histogram(expected, breakpoints)[0] / len(expected)
    actual_percents = np.histogram(actual, breakpoints)[0] / len(actual)

    # Clip para evitar divisao por zero e log(0).
    # Usa 0.0001 (H2: 0.001 era agressivo demais — inflava bins com poucos samples em 100x).
    expected_percents = np.clip(expected_percents, 0.0001, None)
    actual_percents = np.clip(actual_percents, 0.0001, None)

    psi = np.sum((actual_percents - expected_percents) *
                 np.log(actual_percents / expected_percents))
    return float(psi)


def classify_psi(psi, green_threshold, yellow_threshold):
    """Classifica PSI em GREEN/YELLOW/RED."""
    if np.isnan(psi):
        return "UNKNOWN"
    if psi <= green_threshold:
        return "GREEN"
    if psi <= yellow_threshold:
        return "YELLOW"
    return "RED"


def ks_stat(y_true, y_score):
    """KS statistic (0-100)."""
    if len(np.unique(y_true)) < 2:
        return np.nan
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    return ks_2samp(pos, neg).statistic * 100


# =============================================================================
# MONITORAMENTO PRINCIPAL
# =============================================================================

def run_monitoring(spark):
    """Executa monitoramento completo de drift.

    Args:
        spark: SparkSession ativa.

    Returns:
        dict: Relatorio de monitoramento com alertas.
    """
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(SPARK_BROADCAST_THRESHOLD))
    spark.conf.set("spark.sql.adaptive.enabled", str(SPARK_AQE_ENABLED).lower())
    spark.conf.set("spark.sql.shuffle.partitions", str(SPARK_SHUFFLE_PARTITIONS))

    logger.info("=== Monitoramento de Drift ===")
    logger.info("Baseline: %s | Monitor: %d", BASELINE_SAFRAS, MONITOR_SAFRA)

    # H4: Validar que SAFRA de monitoramento nao esta nas SAFRAs de baseline
    if MONITOR_SAFRA in BASELINE_SAFRAS:
        raise ValueError(
            f"MONITOR_SAFRA ({MONITOR_SAFRA}) esta contida em BASELINE_SAFRAS "
            f"({BASELINE_SAFRAS}). O monitoramento deve comparar SAFRAs distintas — "
            f"incluir a mesma SAFRA em ambos invalida a deteccao de drift."
        )

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
    logger.info("Modelo: %s v%s", mv.name, mv.version)

    # Feature names do metadata
    artifacts_path = client.download_artifacts(mv.run_id, "")
    metadata_files = glob.glob(f"{artifacts_path}/*metadata*.json")
    if not metadata_files:
        raise RuntimeError("Metadata nao encontrado — execute export_model.py primeiro")
    with open(metadata_files[0]) as f:
        metadata = json.load(f)
    feature_names = metadata["feature_names"]

    # -------------------------------------------------------------------------
    # 2. Carregar dados baseline e atual
    # -------------------------------------------------------------------------
    baseline_list = ", ".join(str(s) for s in BASELINE_SAFRAS)
    df_baseline = spark.read.format("delta").load(PATH_FEATURE_STORE) \
        .filter(f"SAFRA IN ({baseline_list})")
    df_current = spark.read.format("delta").load(PATH_FEATURE_STORE) \
        .filter(f"SAFRA = {MONITOR_SAFRA}")

    n_baseline = df_baseline.count()
    n_current = df_current.count()
    logger.info("Baseline: %d registros | Atual: %d registros", n_baseline, n_current)

    if n_current == 0:
        raise RuntimeError(f"Nenhum registro para SAFRA {MONITOR_SAFRA}")

    # Converter para pandas
    cols_needed = feature_names + ["FPD"]
    cols_available = [c for c in cols_needed if c in df_baseline.columns]

    # M1: Alertar sobre features do metadata que nao existem no DataFrame
    cols_missing = [c for c in cols_needed if c not in df_baseline.columns]
    if cols_missing:
        logger.warning(
            "M1: %d colunas do metadata nao encontradas no DataFrame e serao ignoradas: %s",
            len(cols_missing), cols_missing[:10],  # limitar a 10 para nao poluir log
        )

    # H5: Validar que ao menos as features do modelo estao presentes
    feature_missing = [f for f in feature_names if f not in df_baseline.columns]
    if feature_missing:
        raise ValueError(
            f"H5: {len(feature_missing)} features do metadata nao encontradas no "
            f"DataFrame. Primeiras 10: {feature_missing[:10]}. "
            f"Verifique se o feature_store esta atualizado e se o metadata corresponde."
        )

    pdf_baseline = df_baseline.select(cols_available).toPandas()
    pdf_current = df_current.select(cols_available).toPandas()

    # M2: fillna(0) — estrategia conservadora para features numericas do modelo.
    # Justificativa: features de books (REC_, PAG_, FAT_) sao agregacoes numericas
    # onde ausencia indica inexistencia de atividade no periodo (ex: nenhuma recarga),
    # portanto 0 e semanticamente correto. Para features categoricas (ja encodadas
    # como numericas no feature_store), 0 representa a categoria de referencia.
    X_baseline = pdf_baseline[feature_names].fillna(0)
    X_current = pdf_current[feature_names].fillna(0)

    # -------------------------------------------------------------------------
    # 3. Score PSI (5.1 — baseline de scores)
    # -------------------------------------------------------------------------
    logger.info("Calculando scores...")

    def _predict_proba(model, X):
        """Extrai probabilidades P(classe=1) do modelo.

        Raises:
            ValueError: Se o modelo nao possui predict_proba — scores de classe
                        {0,1} invalidariam o PSI de score.
        """
        if hasattr(model, '_model_impl'):
            inner = model._model_impl
            if hasattr(inner, 'predict_proba'):
                scores = inner.predict_proba(X)[:, 1]
                return np.asarray(scores, dtype=float)
        # H1: Nao retornar model.predict() (class labels 0/1) — isso tornaria o PSI inutil
        raise ValueError(
            "Modelo nao possui predict_proba acessivel via _model_impl. "
            "PSI requer probabilidades continuas, nao labels de classe {0,1}. "
            "Verifique se o modelo foi exportado corretamente com MLflow."
        )

    scores_baseline = _predict_proba(model, X_baseline)
    scores_current = _predict_proba(model, X_current)

    score_psi = calculate_psi(scores_baseline, scores_current)
    score_status = classify_psi(score_psi, THRESHOLDS["psi_score_green"], THRESHOLDS["psi_score_yellow"])

    logger.info("Score PSI: %.4f [%s]", score_psi, score_status)

    # -------------------------------------------------------------------------
    # 4. Feature drift (top N features por importancia)
    # -------------------------------------------------------------------------
    logger.info("Calculando feature drift (top %d)...", TOP_N_FEATURES)

    # Determinar top features via modelo (se LGBM) ou todas
    top_features = feature_names[:TOP_N_FEATURES]
    if hasattr(model, '_model_impl'):
        inner = model._model_impl
        if hasattr(inner, 'named_steps'):
            final_step = inner.steps[-1][1]
            if hasattr(final_step, 'feature_importances_'):
                importances = final_step.feature_importances_
                # Mapear para nomes (pode ter transformacao no pipeline)
                if len(importances) == len(feature_names):
                    idx = np.argsort(importances)[::-1][:TOP_N_FEATURES]
                    top_features = [feature_names[i] for i in idx]
                else:
                    # C6: Log warning explicito sobre mismatch ao inves de falhar silenciosamente
                    logger.warning(
                        "Feature importance length mismatch: modelo tem %d importances, "
                        "mas metadata lista %d features. Usando primeiras %d features "
                        "do metadata como fallback. Possivel causa: transformacao no "
                        "pipeline (ex: one-hot encoding) alterou o numero de features.",
                        len(importances), len(feature_names), TOP_N_FEATURES,
                    )

    feature_drift = {}
    for feat in top_features:
        baseline_vals = X_baseline[feat].dropna().values.astype(float)
        current_vals = X_current[feat].dropna().values.astype(float)

        if len(baseline_vals) > 0 and len(current_vals) > 0:
            psi = calculate_psi(baseline_vals, current_vals)
            status = classify_psi(psi, THRESHOLDS["psi_feature_green"], THRESHOLDS["psi_feature_yellow"])
            feature_drift[feat] = {"psi": round(psi, 4), "status": status}

    n_red = sum(1 for d in feature_drift.values() if d["status"] == "RED")
    n_yellow = sum(1 for d in feature_drift.values() if d["status"] == "YELLOW")
    n_green = sum(1 for d in feature_drift.values() if d["status"] == "GREEN")

    logger.info("Feature drift: %d GREEN, %d YELLOW, %d RED", n_green, n_yellow, n_red)

    # -------------------------------------------------------------------------
    # 5. Performance check (se FPD disponivel)
    # -------------------------------------------------------------------------
    perf_metrics = {}
    perf_drift = {}

    if "FPD" in pdf_current.columns:
        y_current = pdf_current["FPD"].values
        mask = ~np.isnan(y_current.astype(float))

        # M3: Validar que FPD contem apenas valores binarios {0, 1}
        if mask.sum() > 0:
            fpd_unique = set(np.unique(y_current[mask].astype(float)))
            unexpected_vals = fpd_unique - {0.0, 1.0}
            if unexpected_vals:
                logger.warning(
                    "M3: FPD contem valores nao-binarios: %s. "
                    "Esperado apenas {0, 1}. Metricas de performance podem ser invalidas.",
                    unexpected_vals,
                )

        if mask.sum() > 100 and len(np.unique(y_current[mask])) >= 2:
            logger.info("FPD disponivel — calculando metricas de performance...")

            current_ks = ks_stat(y_current[mask], scores_current[mask])
            current_auc = roc_auc_score(y_current[mask], scores_current[mask])
            current_gini = (2 * current_auc - 1) * 100

            perf_metrics = {
                "ks": round(current_ks, 2),
                "auc": round(current_auc, 4),
                "gini": round(current_gini, 2),
            }

            # Calcular metricas baseline para comparacao
            y_baseline = pdf_baseline["FPD"].values
            mask_bl = ~np.isnan(y_baseline.astype(float))
            if mask_bl.sum() > 100 and len(np.unique(y_baseline[mask_bl])) >= 2:
                baseline_ks = ks_stat(y_baseline[mask_bl], scores_baseline[mask_bl])
                baseline_auc = roc_auc_score(y_baseline[mask_bl], scores_baseline[mask_bl])
                baseline_gini = (2 * baseline_auc - 1) * 100

                # C4: Convencao credit risk — drift = current - baseline.
                # Positivo = melhoria, Negativo = degradacao (requer retreino).
                ks_drift = current_ks - baseline_ks
                auc_drift = current_auc - baseline_auc
                gini_drift = current_gini - baseline_gini

                perf_drift = {
                    "ks_drift_pp": round(ks_drift, 2),
                    "auc_drift": round(auc_drift, 4),
                    "gini_drift_pp": round(gini_drift, 2),
                    "ks_status": "RED" if abs(ks_drift) > THRESHOLDS["ks_drift_max_pp"] else "GREEN",
                    "auc_status": "RED" if abs(auc_drift) > THRESHOLDS["auc_drift_max"] else "GREEN",
                    "gini_status": "RED" if abs(gini_drift) > THRESHOLDS["gini_drift_max_pp"] else "GREEN",
                }

                logger.info(
                    "KS drift: %+.1f pp [%s] (negativo = degradacao)",
                    ks_drift, perf_drift["ks_status"],
                )
                logger.info(
                    "AUC drift: %+.4f [%s] (negativo = degradacao)",
                    auc_drift, perf_drift["auc_status"],
                )
                logger.info(
                    "Gini drift: %+.1f pp [%s] (negativo = degradacao)",
                    gini_drift, perf_drift["gini_status"],
                )
        else:
            logger.info("FPD insuficiente ou sem variancia — skip performance check")
    else:
        logger.info("FPD nao disponivel nesta SAFRA — skip performance check")

    # -------------------------------------------------------------------------
    # 6. Gerar recomendacao
    # -------------------------------------------------------------------------
    alerts = []
    if score_status == "RED":
        alerts.append("Score PSI > 0.25 — modelo instavel, recalibracao necessaria")
    elif score_status == "YELLOW":
        alerts.append("Score PSI > 0.10 — investigar, monitorar proxima SAFRA")

    if n_red > 0:
        red_feats = [f for f, d in feature_drift.items() if d["status"] == "RED"]
        alerts.append(f"{n_red} features com drift RED: {red_feats[:5]}")

    if perf_drift.get("ks_status") == "RED":
        # C4: drift = current - baseline; negativo indica degradacao
        direction = "degradacao" if perf_drift["ks_drift_pp"] < 0 else "variacao"
        alerts.append(
            f"KS drift {perf_drift['ks_drift_pp']:+.1f}pp (|drift| > "
            f"{THRESHOLDS['ks_drift_max_pp']}pp) — {direction}, considerar retreino"
        )

    if not alerts:
        recommendation = "ESTAVEL — nenhuma acao necessaria"
        overall_status = "GREEN"
    elif any("recalibracao" in a or "retreino" in a for a in alerts):
        recommendation = "RETREINO RECOMENDADO — drift significativo detectado"
        overall_status = "RED"
    else:
        recommendation = "ATENCAO — monitorar proxima SAFRA antes de agir"
        overall_status = "YELLOW"

    # -------------------------------------------------------------------------
    # 7. Montar relatorio
    # -------------------------------------------------------------------------
    report = {
        "timestamp": datetime.now().isoformat(),
        "model_name": MODEL_NAME,
        "model_version": mv.version,
        "baseline_safras": BASELINE_SAFRAS,
        "monitor_safra": MONITOR_SAFRA,
        "overall_status": overall_status,
        "recommendation": recommendation,
        "score_psi": round(score_psi, 4),
        "score_status": score_status,
        "feature_drift_summary": {
            "total_monitored": len(feature_drift),
            "green": n_green,
            "yellow": n_yellow,
            "red": n_red,
        },
        "feature_drift_detail": feature_drift,
        "performance_metrics": perf_metrics,
        "performance_drift": perf_drift,
        "thresholds": THRESHOLDS,
        "alerts": alerts,
        "records": {"baseline": n_baseline, "current": n_current},
    }

    # -------------------------------------------------------------------------
    # 8. Logar no MLflow
    # -------------------------------------------------------------------------
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run(run_name=f"monitoring_safra_{MONITOR_SAFRA}"):
        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("model_version", mv.version)
        mlflow.log_param("monitor_safra", MONITOR_SAFRA)
        mlflow.log_param("baseline_safras", str(BASELINE_SAFRAS))
        mlflow.log_param("overall_status", overall_status)

        mlflow.log_metric("score_psi", score_psi)
        mlflow.log_metric("features_red", n_red)
        mlflow.log_metric("features_yellow", n_yellow)
        mlflow.log_metric("n_baseline", n_baseline)
        mlflow.log_metric("n_current", n_current)

        if perf_metrics:
            for k, v in perf_metrics.items():
                mlflow.log_metric(f"current_{k}", v)
        if perf_drift:
            mlflow.log_metric("ks_drift_pp", perf_drift["ks_drift_pp"])
            mlflow.log_metric("auc_drift", perf_drift["auc_drift"])
            mlflow.log_metric("gini_drift_pp", perf_drift["gini_drift_pp"])

        # Salvar relatorio JSON
        # M4: Artefatos temporarios em /tmp — sao copiados para MLflow artifact store
        # via log_artifact() e podem ser removidos apos a execucao. No Fabric,
        # /tmp e efemero e limpo automaticamente ao final da sessao Spark.
        report_path = f"/tmp/monitoring_safra_{MONITOR_SAFRA}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        mlflow.log_artifact(report_path)

        # Salvar drift CSV
        if feature_drift:
            drift_df = pd.DataFrame(feature_drift).T
            drift_df.index.name = "feature"
            drift_path = f"/tmp/feature_drift_safra_{MONITOR_SAFRA}.csv"
            drift_df.to_csv(drift_path)
            mlflow.log_artifact(drift_path)

        run_id = mlflow.active_run().info.run_id

    logger.info("MLflow monitoring run: %s", run_id)

    # -------------------------------------------------------------------------
    # 9. Imprimir resumo
    # -------------------------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"  MONITORAMENTO — SAFRA {MONITOR_SAFRA}")
    print(f"{'='*60}")
    print(f"  Status geral:  {overall_status}")
    print(f"  Score PSI:     {score_psi:.4f} [{score_status}]")
    print(f"  Features:      {n_green} GREEN / {n_yellow} YELLOW / {n_red} RED")
    if perf_metrics:
        print(f"  KS atual:      {perf_metrics['ks']:.1f}")
        print(f"  AUC atual:     {perf_metrics['auc']:.4f}")
    if perf_drift:
        # M5: Mostrar drift com sinal e direcao explicita
        ks_d = perf_drift['ks_drift_pp']
        auc_d = perf_drift['auc_drift']
        gini_d = perf_drift['gini_drift_pp']
        print(f"  KS drift:      {ks_d:+.1f}pp [{perf_drift['ks_status']}]")
        print(f"  AUC drift:     {auc_d:+.4f} [{perf_drift['auc_status']}]")
        print(f"  Gini drift:    {gini_d:+.1f}pp [{perf_drift['gini_status']}]")
        # Resumo de direcao
        if ks_d < 0 or auc_d < 0 or gini_d < 0:
            degraded = []
            if ks_d < 0:
                degraded.append("KS")
            if auc_d < 0:
                degraded.append("AUC")
            if gini_d < 0:
                degraded.append("Gini")
            print(f"  Direcao:       DEGRADACAO em {', '.join(degraded)} (current < baseline)")
        else:
            print(f"  Direcao:       ESTAVEL/MELHORIA (current >= baseline)")
    print(f"  Recomendacao:  {recommendation}")
    if alerts:
        print(f"\n  Alertas:")
        for a in alerts:
            print(f"    - {a}")
    print(f"{'='*60}")

    return report


# =============================================================================
# EXECUCAO PRINCIPAL
# Guard: so executa automaticamente se 'spark' estiver no escopo global
# (padrao Fabric notebooks). Previne execucao acidental em import.
# =============================================================================
if "spark" in dir() and spark is not None:
    report = run_monitoring(spark)
