"""
[DEPRECATED] Airflow DAG: Credit Risk Pipeline — Unified (Legacy)

DEPRECATED: Use the 2 split DAGs instead:
  - credit_risk_data_pipeline.py  (Bronze → Silver → Gold)
  - credit_risk_ml_pipeline.py    (Feature Selection → Training → ... → Monitoring)

This unified DAG is kept for reference/rollback only.
It is auto-paused upon creation.

Original description:
Orchestrates: Bronze → Silver → Gold → Feature Selection → Data Quality →
              Training (5 models) → Ensemble → Scoring → Monitoring
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# ─── Default args ───────────────────────────────────────────────────────────

default_args = {
    "owner": "pod-academy",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=6),
}

# ─── Configuration ──────────────────────────────────────────────────────────

COMPARTMENT = "{{ var.value.COMPARTMENT_OCID }}"
UNIFIED_APP = "{{ var.value.UNIFIED_APP_OCID }}"

BRONZE_BUCKET = "pod-academy-bronze"
SILVER_BUCKET = "pod-academy-silver"
GOLD_BUCKET = "pod-academy-gold"

RUN_DATE = "{{ ds_nodash }}"

# ─── Helper: Submit Data Flow run and poll until completion ─────────────────

SUBMIT_AND_POLL = """
set -euo pipefail
PHASE="{phase}"
APP_ID="{app_id}"
DISPLAY_NAME="e2e-${{PHASE}}-{run_date}"
ARGS='{args}'

echo "=== Submitting $PHASE Data Flow run ==="
echo "App: $APP_ID"
echo "Args: $ARGS"

RUN_ID=$(oci data-flow run create \
    --application-id $APP_ID \
    --compartment-id {compartment} \
    --display-name "$DISPLAY_NAME" \
    --arguments "$ARGS" \
    --query 'data.id' --raw-output)

echo "$PHASE Run ID: $RUN_ID"

# Poll until terminal state (check every 60s)
while true; do
    STATE=$(oci data-flow run get --run-id $RUN_ID --query 'data."lifecycle-state"' --raw-output)
    DURATION=$(oci data-flow run get --run-id $RUN_ID --query 'data."run-duration-in-milliseconds"' --raw-output 2>/dev/null || echo "0")
    DURATION_MIN=$((DURATION / 60000))
    echo "  [${{DURATION_MIN}}min] State: $STATE"
    if [ "$STATE" = "SUCCEEDED" ] || [ "$STATE" = "FAILED" ] || [ "$STATE" = "CANCELED" ]; then
        break
    fi
    sleep 60
done

if [ "$STATE" != "SUCCEEDED" ]; then
    echo "ERROR: $PHASE run $STATE (Run ID: $RUN_ID)"
    exit 1
fi
echo "$PHASE run SUCCEEDED in ${{DURATION_MIN}} minutes"
"""

# ─── Phase commands ─────────────────────────────────────────────────────────

RUN_BRONZE_CMD = SUBMIT_AND_POLL.format(
    phase="bronze",
    app_id=UNIFIED_APP,
    run_date=RUN_DATE,
    args='["--start-phase","bronze","--end-phase","bronze","--fresh"]',
    compartment=COMPARTMENT,
)

VALIDATE_BRONZE_CMD = """
set -euo pipefail
echo "Validating Bronze output (19 tables)..."
MAIN_TABLES="dados_cadastrais telco score_bureau_movel recarga pagamento faturamento dim_calendario"
DIM_TABLES="dim_canal_aquisicao_credito dim_forma_pagamento dim_instituicao dim_plano_preco dim_plataforma dim_promocao_credito dim_status_plataforma dim_tecnologia dim_tipo_credito dim_tipo_insercao dim_tipo_recarga dim_tipo_faturamento"
FOUND=0
TOTAL=0
for table in $MAIN_TABLES $DIM_TABLES; do
    TOTAL=$((TOTAL + 1))
    COUNT=$(oci os object list --bucket-name {bronze} --prefix "$table/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    if [ "$COUNT" -gt "0" ]; then
        FOUND=$((FOUND + 1))
        echo "  OK: $table ($COUNT objects)"
    else
        echo "  MISSING: $table"
    fi
done
echo "Found $FOUND / $TOTAL Bronze tables"
if [ "$FOUND" -lt "19" ]; then
    echo "WARNING: Some Bronze tables missing ($FOUND/19)"
fi
""".format(bronze=BRONZE_BUCKET)

RUN_SILVER_CMD = SUBMIT_AND_POLL.format(
    phase="silver",
    app_id=UNIFIED_APP,
    run_date=RUN_DATE,
    args='["--start-phase","silver","--end-phase","silver"]',
    compartment=COMPARTMENT,
)

VALIDATE_SILVER_CMD = """
set -euo pipefail
echo "Validating Silver output (19 tables)..."
MAIN_TABLES="dados_cadastrais telco score_bureau_movel recarga pagamento faturamento dim_calendario"
DIM_TABLES="dim_canal_aquisicao_credito dim_forma_pagamento dim_instituicao dim_plano_preco dim_plataforma dim_promocao_credito dim_status_plataforma dim_tecnologia dim_tipo_credito dim_tipo_insercao dim_tipo_recarga dim_tipo_faturamento"
FOUND=0
for table in $MAIN_TABLES $DIM_TABLES; do
    COUNT=$(oci os object list --bucket-name {silver} --prefix "rawdata/$table/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    if [ "$COUNT" -gt "0" ]; then
        FOUND=$((FOUND + 1))
        echo "  OK: $table ($COUNT objects)"
    else
        echo "  MISSING: $table"
    fi
done
echo "Found $FOUND / 19 Silver tables"
if [ "$FOUND" -lt "7" ]; then
    echo "ERROR: Missing main Silver tables"
    exit 1
fi
""".format(silver=SILVER_BUCKET)

RUN_GOLD_CMD = SUBMIT_AND_POLL.format(
    phase="gold",
    app_id=UNIFIED_APP,
    run_date=RUN_DATE,
    args='["--start-phase","gold","--end-phase","gold"]',
    compartment=COMPARTMENT,
)

VALIDATE_GOLD_CMD = """
set -euo pipefail
echo "Validating Gold output..."
PARTITIONS=$(oci os object list --bucket-name {gold} --prefix "feature_store/clientes_consolidado/SAFRA=" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
echo "  clientes_consolidado: $PARTITIONS objects"
if [ "$PARTITIONS" -lt "1" ]; then
    echo "ERROR: No Gold partitions found"
    exit 1
fi

BOOKS="book_recarga_cmv book_pagamento book_faturamento"
for book in $BOOKS; do
    COUNT=$(oci os object list --bucket-name {gold} --prefix "$book/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    echo "  $book: $COUNT objects"
done
echo "Gold validation passed"
""".format(gold=GOLD_BUCKET)

# ─── ML Pipeline Configuration ────────────────────────────────────────────
# ML scripts run LOCALLY on the orchestrator VM.
# Prerequisites: VM resized to 4+ OCPUs / 64+ GB RAM before triggering.
# Scripts must be uploaded to SCRIPTS_DIR before running.

NAMESPACE = "grlxi07jz1mo"
ARTIFACT_DIR = "/home/opc/ml-pipeline/artifacts"
DATA_PATH = "/home/opc/ml-pipeline/data/feature_store/clientes_consolidado"
SCRIPTS_DIR = "/home/opc/ml-pipeline/scripts"

ML_ENV = (
    f"export PYTHONUNBUFFERED=1 && "
    f"export ARTIFACT_DIR={ARTIFACT_DIR} && "
    f"export DATA_PATH={DATA_PATH} && "
    f"export LOCAL_DATA_PATH={DATA_PATH} && "
    f"export OCI_NAMESPACE={NAMESPACE} && "
    f"export GOLD_BUCKET={GOLD_BUCKET} && "
    f"export FEATURE_SELECTION_MODE=dynamic"
)

# ─── Setup: Install packages + download data ─────────────────────────────

SETUP_ML_ENV_CMD = f"""
set -euo pipefail
echo "=== Setting up ML environment ==="

# Install ML packages
pip install -q lightgbm xgboost catboost category-encoders psutil pyarrow scikit-learn matplotlib 2>&1 | tail -5
echo "[SETUP] ML packages installed"

# Create directories
mkdir -p {ARTIFACT_DIR}/models {ARTIFACT_DIR}/metrics {ARTIFACT_DIR}/plots {ARTIFACT_DIR}/scoring {ARTIFACT_DIR}/monitoring
mkdir -p {DATA_PATH}

# Check memory
python -c "import psutil; m=psutil.virtual_memory(); print(f'[SYS] RAM: {{m.total/1024**3:.1f}} GB total, {{m.available/1024**3:.1f}} GB available')"
echo "[SETUP] Environment ready"
"""

DOWNLOAD_DATA_CMD = f"""
set -euo pipefail
echo "=== Downloading Gold data from Object Storage ==="

# Check if data already exists
EXISTING=$(find {DATA_PATH} -name "*.parquet" 2>/dev/null | wc -l)
if [ "$EXISTING" -gt "500" ]; then
    echo "[DATA] Data already present ($EXISTING parquet files). Skipping download."
    exit 0
fi

# Bulk download from gold bucket (may return non-zero for skipped dirs)
oci os object bulk-download \
    --bucket-name {GOLD_BUCKET} \
    --namespace {NAMESPACE} \
    --prefix "feature_store/clientes_consolidado/" \
    --download-dir /home/opc/ml-pipeline/data/ \
    --auth instance_principal \
    --overwrite 2>&1 | tail -5 || true

DOWNLOADED=$(find {DATA_PATH} -name "*.parquet" 2>/dev/null | wc -l)
echo "[DATA] Found $DOWNLOADED parquet files on disk"

if [ "$DOWNLOADED" -lt "100" ]; then
    echo "ERROR: Expected 600+ parquets, got $DOWNLOADED"
    exit 1
fi
echo "[DATA] Download complete ($DOWNLOADED parquets)"
"""

# Helper: Run a Python script locally on the orchestrator
RUN_LOCAL_SCRIPT = """
set -euo pipefail
SCRIPT="{script}"
echo "=== Running $SCRIPT locally on orchestrator ==="
echo "Artifacts: """ + ARTIFACT_DIR + """
echo "Data: """ + DATA_PATH + """

""" + ML_ENV + """ && cd """ + SCRIPTS_DIR + """ && python -u $SCRIPT 2>&1

EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
    echo "ERROR: $SCRIPT failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi
echo "$SCRIPT completed successfully"
"""

# ─── ML Phase commands ───────────────────────────────────────────────────

RUN_FEATURE_SELECTION_CMD = RUN_LOCAL_SCRIPT.format(script="feature_selection.py")

RUN_DATA_QUALITY_CMD = f"""
set -euo pipefail
echo "=== Running Data Quality Checks ==="
{ML_ENV} && cd {SCRIPTS_DIR} && python -u data_quality.py 2>&1 || true
echo "Data quality checks completed (non-blocking)"
"""

RUN_TRAINING_CMD = RUN_LOCAL_SCRIPT.format(script="train_credit_risk.py")
RUN_ENSEMBLE_CMD = RUN_LOCAL_SCRIPT.format(script="ensemble.py")
RUN_SCORING_CMD = RUN_LOCAL_SCRIPT.format(script="batch_scoring.py")
RUN_MONITORING_CMD = RUN_LOCAL_SCRIPT.format(script="monitoring.py")

# ─── Upload artifacts to Object Storage ───────────────────────────────────

UPLOAD_ARTIFACTS_CMD = f"""
set -euo pipefail
echo "=== Uploading artifacts to Object Storage ==="

oci os object bulk-upload \
    --bucket-name {GOLD_BUCKET} \
    --namespace {NAMESPACE} \
    --prefix "ml_artifacts/{{{{ ds_nodash }}}}/" \
    --src-dir {ARTIFACT_DIR} \
    --auth instance_principal \
    --overwrite 2>&1 | tail -10

echo "[UPLOAD] Artifacts uploaded to ml_artifacts/{{{{ ds_nodash }}}}/"

# Summary
echo ""
echo "=== Pipeline Summary ==="
if [ -f {ARTIFACT_DIR}/metrics/training_results_*.json ]; then
    python -c "
import json, glob
files = glob.glob('{ARTIFACT_DIR}/metrics/training_results_*.json')
if files:
    with open(files[-1]) as f:
        r = json.load(f)
    print(f'QG-05: {{r.get(\"quality_gate_qg05\", \"?\")}}')
    for m, v in r.get('model_metrics', {{}}).items():
        print(f'  {{m}}: KS_OOT={{v[\"ks_oot\"]:.4f}}, AUC={{v[\"auc_oot\"]:.4f}}')
"
fi
echo "Done!"
"""

# ─── DAG Definition ─────────────────────────────────────────────────────────

with DAG(
    dag_id="credit_risk_pipeline",
    default_args=default_args,
    description="Medallion pipeline: Bronze → Silver → Gold → Feature Selection → Training (5 models) → Ensemble → Scoring → Monitoring",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["credit-risk", "medallion", "pod-academy"],
    max_active_runs=1,
) as dag:

    run_bronze = BashOperator(
        task_id="run_bronze",
        bash_command=RUN_BRONZE_CMD,
        execution_timeout=timedelta(hours=2),
    )

    validate_bronze = BashOperator(
        task_id="validate_bronze",
        bash_command=VALIDATE_BRONZE_CMD,
    )

    run_silver = BashOperator(
        task_id="run_silver",
        bash_command=RUN_SILVER_CMD,
        execution_timeout=timedelta(hours=3),
    )

    validate_silver = BashOperator(
        task_id="validate_silver",
        bash_command=VALIDATE_SILVER_CMD,
    )

    run_gold = BashOperator(
        task_id="run_gold",
        bash_command=RUN_GOLD_CMD,
        execution_timeout=timedelta(hours=3),
    )

    validate_gold = BashOperator(
        task_id="validate_gold",
        bash_command=VALIDATE_GOLD_CMD,
    )

    # ── ML Pipeline Tasks (run locally on orchestrator) ─────────────────────

    setup_ml_env = BashOperator(
        task_id="setup_ml_env",
        bash_command=SETUP_ML_ENV_CMD,
        execution_timeout=timedelta(minutes=15),
    )

    download_data = BashOperator(
        task_id="download_data",
        bash_command=DOWNLOAD_DATA_CMD,
        execution_timeout=timedelta(minutes=30),
    )

    run_feature_selection = BashOperator(
        task_id="run_feature_selection",
        bash_command=RUN_FEATURE_SELECTION_CMD,
        execution_timeout=timedelta(hours=2),
    )

    run_data_quality = BashOperator(
        task_id="run_data_quality",
        bash_command=RUN_DATA_QUALITY_CMD,
        execution_timeout=timedelta(minutes=30),
    )

    run_training = BashOperator(
        task_id="run_training",
        bash_command=RUN_TRAINING_CMD,
        execution_timeout=timedelta(hours=4),
    )

    run_ensemble = BashOperator(
        task_id="run_ensemble",
        bash_command=RUN_ENSEMBLE_CMD,
        execution_timeout=timedelta(hours=1),
    )

    run_scoring = BashOperator(
        task_id="run_scoring",
        bash_command=RUN_SCORING_CMD,
        execution_timeout=timedelta(hours=2),
    )

    run_monitoring = BashOperator(
        task_id="run_monitoring",
        bash_command=RUN_MONITORING_CMD,
        execution_timeout=timedelta(hours=1),
    )

    upload_artifacts = BashOperator(
        task_id="upload_artifacts",
        bash_command=UPLOAD_ARTIFACTS_CMD,
        execution_timeout=timedelta(minutes=15),
    )

    # ── Task Dependencies ──────────────────────────────────────────────────
    # Data Pipeline: Bronze → Silver → Gold (Spark on Data Flow)
    run_bronze >> validate_bronze >> run_silver >> validate_silver >> run_gold >> validate_gold

    # ML Pipeline Setup: install packages + download data (after Gold ready)
    validate_gold >> setup_ml_env >> download_data

    # ML Pipeline: Feature Selection → Training → Ensemble → Scoring → Monitoring
    download_data >> run_feature_selection >> run_training >> run_ensemble >> run_scoring >> run_monitoring >> upload_artifacts

    # Data Quality runs in parallel with feature selection (non-blocking)
    download_data >> run_data_quality
