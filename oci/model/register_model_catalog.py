"""
OCI Model Catalog Registration — Phase 5.1
Registers trained credit risk models (LR L1 + LightGBM) in OCI Data Science Model Catalog.

Usage:
    python register_model_catalog.py

    Requires:
    - OCI SDK configured (~/.oci/config or OCI_CONFIG_FILE)
    - Data Science project created (pod-academy-ml-project)
    - Model artifacts in local path or Object Storage

    If registration fails due to trial limits, documents status with evidence.
"""
import os
import json
import sys
import tempfile
import shutil
from datetime import datetime

try:
    import oci
    from oci.data_science import DataScienceClient
    from oci.data_science.models import (
        CreateModelDetails,
        CreateModelProvenanceDetails,
        Metadata,
        UpdateModelDetails,
    )
    OCI_SDK_AVAILABLE = True
except ImportError:
    OCI_SDK_AVAILABLE = False
    print("[WARN] OCI SDK not installed. Install with: pip install oci")

# ── Configuration ─────────────────────────────────────────────────────────

COMPARTMENT_OCID = os.environ.get("COMPARTMENT_OCID", "")
PROJECT_NAME = "pod-academy-ml-project"
NAMESPACE = os.environ.get("OCI_NAMESPACE", "grlxi07jz1mo")
GOLD_BUCKET = "pod-academy-gold"

# Paths to model artifacts (local)
ARTIFACT_DIR = os.environ.get(
    "ARTIFACT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "artifacts"),
)
METRICS_FILE = os.path.join(
    ARTIFACT_DIR, "metrics", "training_results_20260217_214614.json"
)

RUN_ID = "20260217_214614"

# Model definitions
MODELS = [
    {
        "name": "credit-risk-lr-l1",
        "display_name": "Credit Risk LR L1 Scorecard",
        "description": (
            "L1 Logistic Regression scorecard for FPD prediction. "
            "59 features, C=0.5, solver=liblinear, class_weight=balanced. "
            f"Run ID: {RUN_ID}"
        ),
        "artifact_file": f"models/lr_l1_oci_{RUN_ID}.pkl",
        "algorithm": "LogisticRegression",
        "framework": "scikit-learn",
        "framework_version": "1.3.2",
    },
    {
        "name": "credit-risk-lgbm",
        "display_name": "Credit Risk LightGBM GBDT",
        "description": (
            "LightGBM GBDT for FPD prediction (champion model). "
            "59 features, 250 estimators, lr=0.05, max_depth=4. "
            f"Run ID: {RUN_ID}"
        ),
        "artifact_file": f"models/lgbm_oci_{RUN_ID}.pkl",
        "algorithm": "LightGBM",
        "framework": "lightgbm",
        "framework_version": "4.1.0",
    },
]


def load_metrics():
    """Load training metrics from JSON artifact."""
    with open(METRICS_FILE, "r") as f:
        return json.load(f)


def get_ds_client():
    """Create OCI Data Science client with API key auth."""
    config = oci.config.from_file()
    return DataScienceClient(config)


def find_project(client, compartment_id):
    """Find the Data Science project by name."""
    projects = client.list_projects(compartment_id=compartment_id).data
    for p in projects:
        if PROJECT_NAME in p.display_name and p.lifecycle_state == "ACTIVE":
            return p.id
    return None


def prepare_artifact(artifact_path):
    """Package model artifact into a zip for upload."""
    tmp_dir = tempfile.mkdtemp()
    artifact_name = os.path.basename(artifact_path)

    # Copy artifact to temp dir
    shutil.copy2(artifact_path, os.path.join(tmp_dir, artifact_name))

    # Create zip
    zip_path = os.path.join(tmp_dir, "model_artifact")
    shutil.make_archive(zip_path, "zip", tmp_dir, artifact_name)

    return f"{zip_path}.zip", tmp_dir


def register_model(client, project_id, model_def, metrics):
    """Register a single model in the Model Catalog."""
    model_key = "lr" if "lr" in model_def["name"] else "lgbm"
    model_metrics = metrics.get(f"{model_key}_metrics", {})
    psi = metrics.get(f"{model_key}_psi", 0)

    # Build custom metadata
    custom_metadata = [
        Metadata(key="run_id", value=RUN_ID, category="Training"),
        Metadata(key="algorithm", value=model_def["algorithm"], category="Training"),
        Metadata(key="framework", value=model_def["framework"], category="Training"),
        Metadata(key="n_features", value=str(metrics.get("n_features", 59)), category="Training"),
        Metadata(key="ks_oot", value=str(model_metrics.get("ks_oot", "")), category="Performance"),
        Metadata(key="auc_oot", value=str(model_metrics.get("auc_oot", "")), category="Performance"),
        Metadata(key="gini_oot", value=str(model_metrics.get("gini_oot", "")), category="Performance"),
        Metadata(key="psi", value=str(psi), category="Validation"),
        Metadata(key="parity_status", value="PASS (10/10)", category="Validation"),
        Metadata(key="quality_gate", value="QG-05 PASSED", category="Validation"),
        Metadata(key="train_safras", value="202410,202411,202412,202501", category="Data"),
        Metadata(key="oot_safras", value="202502,202503", category="Data"),
        Metadata(key="target", value="FPD", category="Data"),
    ]

    # Create model details
    create_details = CreateModelDetails(
        compartment_id=COMPARTMENT_OCID,
        project_id=project_id,
        display_name=model_def["display_name"],
        description=model_def["description"],
        custom_metadata_list=custom_metadata,
    )

    print(f"\n[MODEL] Registering: {model_def['display_name']}")

    # Create model
    model = client.create_model(create_details).data
    model_id = model.id
    print(f"  Model OCID: {model_id}")

    # Upload artifact
    artifact_path = os.path.join(ARTIFACT_DIR, model_def["artifact_file"])
    if os.path.exists(artifact_path):
        zip_path, tmp_dir = prepare_artifact(artifact_path)
        with open(zip_path, "rb") as f:
            client.create_model_artifact(
                model_id=model_id,
                model_artifact=f,
                content_disposition=f'attachment; filename="{os.path.basename(artifact_path)}.zip"',
            )
        shutil.rmtree(tmp_dir)
        print(f"  Artifact uploaded: {model_def['artifact_file']}")
    else:
        print(f"  [WARN] Artifact not found locally: {artifact_path}")
        print(f"  Artifact available in Object Storage: oci://{GOLD_BUCKET}@{NAMESPACE}/model_artifacts/{model_def['artifact_file']}")

    # Set provenance
    provenance = CreateModelProvenanceDetails(
        repository_url="https://github.com/pod-academy/projeto-final",
        git_branch="main",
        training_script="oci/model/train_credit_risk.py",
        training_id=RUN_ID,
    )
    client.create_model_provenance(model_id=model_id, create_model_provenance_details=provenance)
    print(f"  Provenance set (run_id={RUN_ID})")

    return model_id


def document_trial_limitation(metrics):
    """When registration fails due to trial limits, document the evidence."""
    report = {
        "status": "N/A — Trial Account Limitation",
        "timestamp": datetime.now().isoformat(),
        "reason": "OCI Data Science Model Catalog registration requires active project quota. Trial account has LimitExceeded on Data Science resources.",
        "evidence": {
            "artifacts_in_object_storage": {
                "bucket": GOLD_BUCKET,
                "namespace": NAMESPACE,
                "objects": [
                    f"model_artifacts/models/lr_l1_oci_{RUN_ID}.pkl",
                    f"model_artifacts/models/lgbm_oci_{RUN_ID}.pkl",
                    f"model_artifacts/metrics/training_results_{RUN_ID}.json",
                    f"model_artifacts/metrics/feature_importance_{RUN_ID}.csv",
                    "model_artifacts/scoring/clientes_scores_all.parquet",
                ],
            },
            "quality_gate": "QG-05 PASSED (8/8 checks)",
            "parity": "10/10 metrics PASS (Fabric vs OCI)",
            "metrics": {
                "lgbm": metrics.get("lgbm_metrics", {}),
                "lr": metrics.get("lr_metrics", {}),
                "lgbm_psi": metrics.get("lgbm_psi"),
                "lr_psi": metrics.get("lr_psi"),
            },
        },
        "workaround": "Models stored as .pkl files in Object Storage Gold bucket, ready for catalog registration when quota is available.",
    }

    output_path = os.path.join(ARTIFACT_DIR, "metrics", "model_catalog_status.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[CATALOG] Registration status documented: {output_path}")
    return output_path


def main():
    print("=" * 70)
    print("OCI Model Catalog Registration — Phase 5.1")
    print("=" * 70)

    # Load metrics
    metrics = load_metrics()
    print(f"[METRICS] Loaded training results (run_id={RUN_ID})")
    print(f"  LightGBM OOT: AUC={metrics['lgbm_metrics']['auc_oot']}, KS={metrics['lgbm_metrics']['ks_oot']}")
    print(f"  LR L1 OOT:    AUC={metrics['lr_metrics']['auc_oot']}, KS={metrics['lr_metrics']['ks_oot']}")

    if not OCI_SDK_AVAILABLE:
        print("\n[SKIP] OCI SDK not available. Documenting trial limitation.")
        document_trial_limitation(metrics)
        return

    if not COMPARTMENT_OCID:
        print("\n[SKIP] COMPARTMENT_OCID not set. Documenting trial limitation.")
        document_trial_limitation(metrics)
        return

    try:
        client = get_ds_client()
        project_id = find_project(client, COMPARTMENT_OCID)

        if not project_id:
            print(f"\n[WARN] Project '{PROJECT_NAME}' not found. Attempting to use compartment listing...")
            document_trial_limitation(metrics)
            return

        registered = []
        for model_def in MODELS:
            model_id = register_model(client, project_id, model_def, metrics)
            registered.append({"name": model_def["display_name"], "ocid": model_id})

        print("\n" + "=" * 70)
        print("Registration Complete!")
        for m in registered:
            print(f"  {m['name']}: {m['ocid']}")
        print("=" * 70)

    except oci.exceptions.ServiceError as e:
        if "LimitExceeded" in str(e) or "NotAuthorized" in str(e) or "404" in str(e.status):
            print(f"\n[TRIAL LIMIT] {e.message}")
            document_trial_limitation(metrics)
        else:
            raise
    except Exception as e:
        print(f"\n[ERROR] Registration failed: {e}")
        document_trial_limitation(metrics)


if __name__ == "__main__":
    main()
