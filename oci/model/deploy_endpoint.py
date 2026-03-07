"""
Model Registration & Deployment — OCI Data Science
Registers trained models in OCI Model Catalog and deploys REST endpoint.

Usage:
    Run in OCI Data Science notebook after training + evaluation pass QG-05.
    Requires: oracle-ads, oci SDK, Resource Principal auth.
"""
import os
import json
import pickle
import glob
import numpy as np
import pandas as pd
from datetime import datetime

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

import ads
from ads.model.generic_model import GenericModel
from ads.common.model_metadata import UseCaseType

from train_credit_risk import (
    SELECTED_FEATURES, ARTIFACT_DIR, FABRIC_BASELINE,
)

# Auth
ads.set_auth("resource_principal")

# ═══════════════════════════════════════════════════════════════════════════
# MODEL CATALOG REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════

def register_model(pipeline, model_name, metrics, conda_env="generalml_p38_cpu_v1"):
    """Register a trained sklearn pipeline in OCI Model Catalog."""
    artifact_dir = f"{ARTIFACT_DIR}/catalog/{model_name}"
    os.makedirs(artifact_dir, exist_ok=True)

    # Save pipeline as artifact
    with open(f"{artifact_dir}/model.pkl", "wb") as f:
        pickle.dump(pipeline, f)

    # Save feature list
    with open(f"{artifact_dir}/selected_features.json", "w") as f:
        json.dump(SELECTED_FEATURES, f)

    # Create score.py for inference
    score_py = '''"""
score.py — Model inference for OCI Model Deployment.
"""
import json
import os
import pickle
import pandas as pd
import numpy as np

# sklearn compat patch
import sklearn.utils.validation as _val
_orig = _val.check_array
def _patch(*a, **kw):
    kw.pop("force_all_finite", None)
    kw.pop("ensure_all_finite", None)
    return _orig(*a, **kw)
_val.check_array = _patch

model_dir = os.path.dirname(os.path.realpath(__file__))
model = None

def load_model():
    global model
    with open(os.path.join(model_dir, "model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(model_dir, "selected_features.json"), "r") as f:
        features = json.load(f)
    return model

def predict(data, model=load_model()):
    if isinstance(data, dict):
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data
    else:
        df = pd.DataFrame(data)

    with open(os.path.join(model_dir, "selected_features.json"), "r") as f:
        features = json.load(f)

    proba = model.predict_proba(df[features])[:, 1]
    scores = ((1 - proba) * 1000).astype(int).clip(0, 1000)

    return {
        "prediction": scores.tolist(),
        "probability": proba.round(6).tolist(),
    }
'''
    with open(f"{artifact_dir}/score.py", "w") as f:
        f.write(score_py)

    # Register using GenericModel
    generic_model = GenericModel(
        estimator=pipeline,
        artifact_dir=artifact_dir,
    )

    generic_model.prepare(
        inference_conda_env=conda_env,
        use_case_type=UseCaseType.BINARY_CLASSIFICATION,
        force_overwrite=True,
    )

    # Add custom metadata
    for key, value in metrics.items():
        generic_model.metadata_custom.add(
            key=key,
            value=str(round(value, 5) if isinstance(value, float) else value),
            category="Training Profile",
        )
    generic_model.metadata_custom.add(
        key="n_features", value="59", category="Training Profile",
    )
    generic_model.metadata_custom.add(
        key="train_safras", value="202410-202501", category="Training Profile",
    )
    generic_model.metadata_custom.add(
        key="platform", value="OCI Data Science", category="Training Profile",
    )

    # Save to catalog
    model_id = generic_model.save(
        display_name=model_name,
        description=f"Credit Risk FPD model ({model_name}). 59 features, temporal split.",
    )

    print(f"[CATALOG] Registered: {model_name} → {model_id}")
    return model_id


def deploy_endpoint(model_id, display_name="credit-risk-fpd-endpoint",
                    shape="VM.Standard.E4.Flex", ocpus=1, memory_gb=16):
    """Deploy model as REST endpoint from Model Catalog."""
    from ads.model.deployment import ModelDeployment, ModelDeploymentContainerRuntime

    deployment = ModelDeployment(
        display_name=display_name,
        model_id=model_id,
        instance_shape=shape,
        instance_count=1,
        shape_config_details={"ocpus": ocpus, "memory_in_gbs": memory_gb},
        bandwidth_mbps=10,
    )
    deployment.deploy(wait_for_completion=True)

    print(f"[DEPLOY] Endpoint: {deployment.url}")
    print(f"[DEPLOY] OCID: {deployment.model_deployment_id}")

    return deployment


def validate_endpoint(deployment, X_sample, y_sample, pipeline):
    """Test endpoint with 10 known samples and compare to local inference."""
    print("\n[VALIDATE] Testing endpoint with 10 known samples...")

    local_proba = pipeline.predict_proba(X_sample)[:, 1]
    endpoint_result = deployment.predict(X_sample)

    all_match = True
    for i in range(min(10, len(X_sample))):
        local_p = local_proba[i]
        endpoint_p = endpoint_result["probability"][i]
        diff = abs(local_p - endpoint_p)
        match = diff < 0.001
        status = "OK" if match else "MISMATCH"
        if not match:
            all_match = False
        print(f"  Sample {i+1}: local={local_p:.4f} endpoint={endpoint_p:.4f} diff={diff:.6f} [{status}]")

    print(f"\n[VALIDATE] Endpoint validation: {'PASSED' if all_match else 'FAILED'}")
    return all_match


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("MODEL REGISTRATION & DEPLOYMENT — OCI Data Science")
    print("=" * 70)

    # Load latest training results
    result_files = sorted(glob.glob(f"{ARTIFACT_DIR}/metrics/training_results_*.json"))
    if not result_files:
        print("[ERROR] No training results found. Run train_credit_risk.py first.")
        exit(1)

    with open(result_files[-1], "r") as f:
        training_results = json.load(f)

    if training_results.get("quality_gate_qg05") != "PASSED":
        print("[ERROR] Quality Gate QG-05 not passed. Fix model issues before deploying.")
        exit(1)

    # Load trained pipelines
    lr_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/lr_l1_oci_*.pkl"))
    lgbm_files = sorted(glob.glob(f"{ARTIFACT_DIR}/models/lgbm_oci_*.pkl"))

    with open(lr_files[-1], "rb") as f:
        lr_pipeline = pickle.load(f)
    with open(lgbm_files[-1], "rb") as f:
        lgbm_pipeline = pickle.load(f)

    # Register both models
    print("\n--- Registering LR L1 Scorecard ---")
    lr_metrics = training_results.get("lr_metrics", {})
    lr_model_id = register_model(
        lr_pipeline,
        model_name="credit-risk-fpd-lr-scorecard-v1",
        metrics={k: v for k, v in lr_metrics.items() if isinstance(v, (int, float))},
    )

    print("\n--- Registering LightGBM GBDT ---")
    lgbm_metrics = training_results.get("lgbm_metrics", {})
    lgbm_model_id = register_model(
        lgbm_pipeline,
        model_name="credit-risk-fpd-lgbm-v1",
        metrics={k: v for k, v in lgbm_metrics.items() if isinstance(v, (int, float))},
    )

    print("\n" + "=" * 70)
    print("REGISTRATION COMPLETE")
    print(f"  LR Scorecard: {lr_model_id}")
    print(f"  LightGBM:     {lgbm_model_id}")
    print("=" * 70)

    print("\nTo deploy REST endpoint, run:")
    print(f'  deployment = deploy_endpoint("{lgbm_model_id}")')
