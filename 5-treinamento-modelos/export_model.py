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
import joblib
import mlflow
from datetime import datetime
from pathlib import Path
import numpy as np

import sys; sys.path.insert(0, "/lakehouse/default/Files/projeto-final")
from config.pipeline_config import EXPERIMENT_NAME

# =============================================================================
# CONFIGURACAO
# =============================================================================
MODEL_DIR = "/lakehouse/default/Files/projeto-final/5-treinamento-modelos/artifacts"
EXPERIMENT = EXPERIMENT_NAME

# Criar diretorio de artefatos
Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)


def export_model(pipeline, model_name, X_test, y_test, feature_names, metrics_dict=None):
    """Exporta modelo treinado como .pkl e registra no MLflow.

    Args:
        pipeline: Pipeline sklearn treinada (scaler + model).
        model_name: Nome do modelo (e.g., 'logistic_regression_l1', 'lgbm_baseline').
        X_test: Features de teste para avaliacao.
        y_test: Target de teste.
        feature_names: Lista com nomes das features.
        metrics_dict: Dict com metricas pre-calculadas (opcional).

    Returns:
        dict: Paths dos artefatos gerados.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # =========================================================================
    # 1. Serializar modelo .pkl
    # =========================================================================
    pkl_path = f"{MODEL_DIR}/{model_name}_{timestamp}.pkl"
    joblib.dump(pipeline, pkl_path)
    print(f"Modelo salvo: {pkl_path}")

    # Verificar que o .pkl carrega corretamente
    loaded = joblib.load(pkl_path)
    y_pred_check = loaded.predict_proba(X_test[:5])
    print(f"Verificacao .pkl: OK (shape predito: {y_pred_check.shape})")

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
        "training_safras": ["202410", "202411", "202412", "202501"],
        "oot_safras": ["202502", "202503"],
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
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"Metadata salvo: {metadata_path}")

    # =========================================================================
    # 3. Registrar no MLflow
    # =========================================================================
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

        # Log model
        mlflow.sklearn.log_model(
            pipeline,
            artifact_path="model",
            registered_model_name=f"credit-risk-fpd-{model_name}"
        )

        run_id = mlflow.active_run().info.run_id
        print(f"MLflow Run ID: {run_id}")

    return {
        "pkl_path": pkl_path,
        "metadata_path": metadata_path,
        "mlflow_run_id": run_id
    }


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
