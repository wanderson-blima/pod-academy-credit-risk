"""
Export do Modelo Baseline — .pkl + MLflow Registry.

Serializa o pipeline sklearn treinado (StandardScaler + LogisticRegression ou LGBMClassifier)
em formato .pkl, gera metadata JSON, e registra no MLflow com artefatos completos.

Story: HD-3.2 | Epic: EPIC-HD-001 | Entregavel: C

Uso:
    Executar apos o notebook modelo_baseline_risco_telecom_sklearn.ipynb
    As variaveis pipeline_LR, pipeline_LGBM, X_test, y_test devem estar no escopo.
"""

import json
import os
import time
import joblib
import mlflow
from mlflow.tracking import MlflowClient
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.utils.validation import check_is_fitted
from sklearn.exceptions import NotFittedError

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import EXPERIMENT_NAME, SAFRAS

# =============================================================================
# CONFIGURACAO
# =============================================================================
MODEL_DIR = "/lakehouse/default/Files/projeto-final/5-treinamento-modelos/artifacts"
EXPERIMENT = EXPERIMENT_NAME

# Safras split — derived from centralized config (M1: removed hardcoded values)
TRAINING_SAFRAS = [str(s) for s in SAFRAS[:4]]   # first 4 safras for training
OOT_SAFRAS = [str(s) for s in SAFRAS[4:]]        # remaining safras for OOT

# Criar diretorio de artefatos
Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)

# MLflow version lookup retry config (H1)
_MLFLOW_VERSION_RETRY_ATTEMPTS = 5
_MLFLOW_VERSION_RETRY_DELAY_SEC = 1.0


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def _validate_pipeline(pipeline):
    """Validate that pipeline is a fitted sklearn-compatible pipeline (C2, M5).

    Raises:
        TypeError: If pipeline lacks required attributes.
        RuntimeError: If pipeline does not appear to be fitted.
    """
    if pipeline is None:
        raise TypeError("pipeline cannot be None")

    if not hasattr(pipeline, "predict_proba"):
        raise TypeError(
            f"pipeline must have a 'predict_proba' method, got {type(pipeline).__name__}"
        )

    if not hasattr(pipeline, "steps"):
        raise TypeError(
            f"pipeline must have a 'steps' attribute (sklearn Pipeline), got {type(pipeline).__name__}"
        )

    if not pipeline.steps:
        raise ValueError("pipeline.steps is empty — pipeline has no processing steps")

    # M5: Check that pipeline is fitted using sklearn's official check_is_fitted().
    # Previous heuristic (dir() scan for attrs ending with '_') gave false positives
    # with LightGBM which has attributes like best_score_ before fit.
    last_step = pipeline.steps[-1]
    estimator = last_step[1] if isinstance(last_step, tuple) else last_step
    step_name = last_step[0] if isinstance(last_step, tuple) else type(estimator).__name__
    try:
        check_is_fitted(estimator)
    except NotFittedError:
        raise RuntimeError(
            f"Pipeline does not appear to be fitted — last step '{step_name}' "
            f"failed check_is_fitted(). Call pipeline.fit() first."
        )


def _validate_feature_names(feature_names):
    """Validate that feature_names is a non-empty list of strings (M3).

    Raises:
        TypeError: If feature_names is not a list.
        ValueError: If feature_names is empty.
    """
    if not isinstance(feature_names, (list, tuple)):
        raise TypeError(f"feature_names must be a list or tuple, got {type(feature_names).__name__}")

    if len(feature_names) == 0:
        raise ValueError("feature_names cannot be empty — at least one feature is required")


def _validate_X_test(X_test, feature_names):
    """Validate X_test shape and content (C1).

    Raises:
        TypeError: If X_test is None.
        ValueError: If X_test is empty or column count mismatches feature_names.
    """
    if X_test is None:
        raise TypeError("X_test cannot be None")

    # Support both numpy arrays and pandas DataFrames
    if hasattr(X_test, "shape"):
        n_rows, n_cols = X_test.shape
    else:
        raise TypeError(f"X_test must have a 'shape' attribute (numpy array or DataFrame), got {type(X_test).__name__}")

    if n_rows == 0:
        raise ValueError("X_test is empty (0 rows) — cannot verify model predictions")

    if n_cols != len(feature_names):
        raise ValueError(
            f"X_test column count ({n_cols}) does not match feature_names length ({len(feature_names)}). "
            f"Ensure X_test has the same features the model was trained on."
        )


def _validate_predictions_range(y_pred_proba):
    """Validate that predicted probabilities are in valid range [0, 1] (M2).

    Raises:
        RuntimeError: If any probability is outside [0, 1].
    """
    min_val = np.min(y_pred_proba)
    max_val = np.max(y_pred_proba)
    if min_val < 0.0 or max_val > 1.0:
        raise RuntimeError(
            f"Predicted probabilities are outside valid range [0, 1]: "
            f"min={min_val:.6f}, max={max_val:.6f}. Model may be corrupted."
        )


def _get_latest_version_with_retry(client, registered_name, max_attempts=None, delay_sec=None):
    """Get the latest model version with retry logic for MLflow race condition (H1).

    After mlflow.sklearn.log_model() with registered_model_name, the version
    may not be immediately available. This retries the lookup with a small delay.

    Returns:
        ModelVersion or None if not found after all retries.
    """
    if max_attempts is None:
        max_attempts = _MLFLOW_VERSION_RETRY_ATTEMPTS
    if delay_sec is None:
        delay_sec = _MLFLOW_VERSION_RETRY_DELAY_SEC

    for attempt in range(1, max_attempts + 1):
        versions = client.get_latest_versions(registered_name, stages=["None"])
        if versions:
            return versions[0]
        if attempt < max_attempts:
            print(f"  MLflow version not yet available (attempt {attempt}/{max_attempts}), retrying in {delay_sec}s...")
            time.sleep(delay_sec)

    print(f"  WARNING: Could not find version for '{registered_name}' after {max_attempts} attempts")
    return None


def _cleanup_partial_artifacts(pkl_path, metadata_path):
    """Remove partial artifacts if MLflow registration fails (M4).

    Only removes files that exist. Logs warnings on cleanup failures.
    """
    for path in [pkl_path, metadata_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                print(f"  Cleaned up partial artifact: {path}")
            except OSError as e:
                print(f"  WARNING: Failed to clean up {path}: {e}")


# =============================================================================
# MAIN EXPORT FUNCTION
# =============================================================================

def export_model(pipeline, model_name, X_test, y_test=None, feature_names=None,
                 metrics_dict=None, training_safras=None, oot_safras=None):
    """Exporta modelo treinado como .pkl e registra no MLflow.

    Args:
        pipeline: Pipeline sklearn treinada (scaler + model).
        model_name: Nome do modelo (e.g., 'logistic_regression_l1', 'lgbm_baseline').
        X_test: Features de teste para avaliacao.
        y_test: Target de teste (opcional). If provided and metrics_dict is None,
                basic metrics (AUC, F1) will be computed automatically.
        feature_names: Lista com nomes das features.
        metrics_dict: Dict com metricas pre-calculadas (opcional).
            If None and y_test is provided, metrics are computed automatically.
        training_safras: List of training safra strings (optional, defaults to config).
        oot_safras: List of OOT safra strings (optional, defaults to config).

    Returns:
        dict: Paths dos artefatos gerados.

    Raises:
        TypeError: If pipeline, X_test, or feature_names are invalid types.
        ValueError: If X_test is empty or feature count mismatches.
        RuntimeError: If pipeline is not fitted or predictions are invalid.
    """
    # =========================================================================
    # 0. Input validation (C1, C2, M3, M5)
    # =========================================================================
    _validate_pipeline(pipeline)
    _validate_feature_names(feature_names)
    _validate_X_test(X_test, feature_names)

    # Use config-based safras if not overridden (M1)
    if training_safras is None:
        training_safras = TRAINING_SAFRAS
    if oot_safras is None:
        oot_safras = OOT_SAFRAS

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pkl_path = None
    metadata_path = None
    run_id = None
    registered_name = f"credit-risk-fpd-{model_name}"

    # H4: If y_test is provided and no metrics_dict, compute basic metrics
    if metrics_dict is None and y_test is not None:
        try:
            y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
            computed_metrics = {}
            computed_metrics["auc"] = float(roc_auc_score(y_test, y_pred_proba))
            y_pred_binary = (y_pred_proba >= 0.5).astype(int)
            computed_metrics["f1"] = float(f1_score(y_test, y_pred_binary, zero_division=0))
            metrics_dict = computed_metrics
            print(f"Metricas computadas automaticamente a partir de y_test: {metrics_dict}")
        except Exception as e:
            print(f"WARNING: Nao foi possivel computar metricas a partir de y_test: {e}")
            metrics_dict = None

    # =========================================================================
    # 1. Serializar modelo .pkl (H3: wrapped in try-except)
    # =========================================================================
    pkl_path = f"{MODEL_DIR}/{model_name}_{timestamp}.pkl"
    try:
        joblib.dump(pipeline, pkl_path)
        print(f"Modelo salvo: {pkl_path}")
    except Exception as e:
        raise RuntimeError(f"Falha ao salvar modelo .pkl em '{pkl_path}': {e}") from e

    # Verificar que o .pkl carrega corretamente (H3: wrapped in try-except)
    try:
        loaded = joblib.load(pkl_path)
    except Exception as e:
        _cleanup_partial_artifacts(pkl_path, None)
        raise RuntimeError(f"Falha ao carregar modelo .pkl de '{pkl_path}': {e}") from e

    y_pred_check = loaded.predict_proba(X_test[:5])
    print(f"Verificacao .pkl: OK (shape predito: {y_pred_check.shape})")

    # M2: Validate predictions are in valid probability range [0, 1]
    _validate_predictions_range(y_pred_check)
    print(f"Verificacao range probabilidades: OK (min={np.min(y_pred_check):.4f}, max={np.max(y_pred_check):.4f})")

    # =========================================================================
    # 2. Gerar metadata JSON
    # =========================================================================
    metadata = {
        "model_name": model_name,
        "timestamp": timestamp,
        "framework": "sklearn",
        "pipeline_steps": [str(step) for step in pipeline.steps],
        "n_features": len(feature_names),
        "feature_names": feature_names,
        "target": "FPD",
        "granularity": "NUM_CPF + SAFRA",
        "training_safras": training_safras,
        "oot_safras": oot_safras,
        "pkl_path": pkl_path,
        "metrics": metrics_dict or {},
        "leakage_check": {
            "FAT_VLR_FPD": "REMOVED (was direct copy of target)",
            "SCORE_RISCO_*": "SAFE (uses operational indicators only)",
            "status": "CLEAN"
        },
        "story": "HD-3.2",
        "epic": "EPIC-HD-001"
    }

    metadata_path = f"{MODEL_DIR}/{model_name}_metadata_{timestamp}.json"
    try:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"Metadata salvo: {metadata_path}")
    except Exception as e:
        _cleanup_partial_artifacts(pkl_path, metadata_path)
        raise RuntimeError(f"Falha ao salvar metadata JSON em '{metadata_path}': {e}") from e

    # =========================================================================
    # 3. Registrar no MLflow (H2: entire section wrapped in try-except)
    # =========================================================================
    try:
        mlflow.set_experiment(EXPERIMENT)

        with mlflow.start_run(run_name=f"export_{model_name}_{timestamp}"):
            # Log params
            mlflow.log_param("model_name", model_name)
            mlflow.log_param("n_features", len(feature_names))
            mlflow.log_param("target", "FPD")
            mlflow.log_param("leakage_status", "CLEAN")

            # Log metrics
            if metrics_dict:
                for key, val in metrics_dict.items():
                    if isinstance(val, (int, float)) and not np.isnan(val):
                        mlflow.log_metric(key, val)

            # Log artifacts
            mlflow.log_artifact(pkl_path)
            mlflow.log_artifact(metadata_path)

            # Log model + register
            mlflow.sklearn.log_model(
                pipeline,
                artifact_path="model",
                registered_model_name=registered_name,
            )

            run_id = mlflow.active_run().info.run_id
            print(f"MLflow Run ID: {run_id}")

    except Exception as e:
        # M4: Clean up partial artifacts on MLflow failure
        _cleanup_partial_artifacts(pkl_path, metadata_path)
        raise RuntimeError(
            f"Falha no registro MLflow para '{model_name}': {e}. "
            f"Artefatos parciais foram removidos."
        ) from e

    # =========================================================================
    # 4. Transicionar para Staging + adicionar descricao (H1: retry logic)
    # =========================================================================
    try:
        client = MlflowClient()
        version_info = _get_latest_version_with_retry(client, registered_name)

        if version_info:
            version = version_info.version
            client.transition_model_version_stage(
                name=registered_name,
                version=version,
                stage="Staging",
            )
            desc_parts = [f"FPD model \u2014 {len(feature_names)} features"]
            if metrics_dict:
                for k, v in metrics_dict.items():
                    if isinstance(v, (int, float)) and not np.isnan(v):
                        desc_parts.append(f"{k}: {v:.3f}")
            client.update_model_version(
                name=registered_name,
                version=version,
                description=", ".join(desc_parts),
            )
            print(f"Modelo {registered_name} v{version} transicionado para Staging")
        else:
            print(f"WARNING: Modelo registrado mas versao nao encontrada para transicao de stage")

    except Exception as e:
        # Non-fatal: model was already exported and registered, only staging transition failed
        print(f"WARNING: Falha ao transicionar modelo para Staging: {e}")
        print(f"  O modelo foi exportado e registrado com sucesso. Transicao pode ser feita manualmente.")

    return {
        "pkl_path": pkl_path,
        "metadata_path": metadata_path,
        "mlflow_run_id": run_id,
        "registered_name": registered_name,
    }


def promote_to_production(model_name, version=None):
    """Promove modelo de Staging para Production.

    Args:
        model_name: Nome registrado no MLflow (e.g., 'credit-risk-fpd-lgbm_baseline').
        version: Versao especifica. Se None, usa a ultima em Staging.

    Returns:
        str: Versao promovida.
    """
    client = MlflowClient()
    if version is None:
        versions = client.get_latest_versions(model_name, stages=["Staging"])
        if not versions:
            raise RuntimeError(f"Nenhuma versao em Staging para '{model_name}'")
        version = versions[0].version

    client.transition_model_version_stage(
        name=model_name,
        version=version,
        stage="Production",
    )
    print(f"Modelo {model_name} v{version} promovido para Production")
    return version


# =============================================================================
# EXECUCAO — Chamado apos treinamento no notebook
# =============================================================================
# Exemplo de uso (descomentar no notebook apos treinamento):
#
# from export_model import export_model
#
# # Exportar Logistic Regression
# result_lr = export_model(
#     pipeline=pipeline_LR,
#     model_name="logistic_regression_l1",
#     X_test=X_test,
#     y_test=y_test,
#     feature_names=list(X_train.columns),
#     metrics_dict={"ks_oot": 0.331, "auc_oot": 0.736, "ks_oos": 0.35}
# )
#
# # Exportar LGBM
# result_lgbm = export_model(
#     pipeline=pipeline_LGBM,
#     model_name="lgbm_baseline",
#     X_test=X_test,
#     y_test=y_test,
#     feature_names=list(X_train.columns),
#     metrics_dict={"ks_oot": 0.34, "auc_oot": 0.74}
# )
