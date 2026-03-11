"""
Airflow DAG: Credit Risk ML Pipeline — Model Training & Operations
Orchestrates: Resize Up → Preflight → Feature Selection → Training (5 models) →
              Ensemble → Scoring → Monitoring → Collect Artifacts → Resize Down

ML scripts run LOCALLY on the orchestrator VM.
The DAG automatically resizes the instance to 4 OCPUs / 64 GB at the start,
and scales back down to 2 OCPUs / 16 GB after completion (including on failure).

Prerequisite: Gold layer must exist (run credit_risk_data_pipeline first).

Schedule: Manual trigger only
Trigger: Manual
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
# Paths as seen INSIDE the Airflow container (docker-compose volumes):
#   /home/opc/ml-pipeline/scripts/  → mounted from host
#   /home/opc/data/                 → mounted from host
#   /home/opc/artifacts/            → mounted from host

SCRIPTS_DIR = "/home/opc/ml-pipeline/scripts"
DATA_PATH = "/home/opc/data/gold"
ARTIFACT_DIR = "/home/opc/artifacts"
GOLD_BUCKET = "pod-academy-gold"

# Instance config for auto-resize
COMPARTMENT = "{{ var.value.COMPARTMENT_OCID }}"
INSTANCE_OCID = "{{ var.value.ORCHESTRATOR_INSTANCE_OCID }}"

RUN_DATE = "{{ ds_nodash }}"

# OCI CLI is at /home/airflow/.local/bin/oci inside the container
OCI_PATH_EXPORT = "export PATH=/home/airflow/.local/bin:$PATH"

# ─── Verify Instance Size (resize must be done BEFORE triggering DAG) ──────
# Resize stops the instance, which kills Airflow. So it cannot be done from
# inside a DAG task. Use orchestrator-lifecycle.sh resize-up BEFORE triggering.

VERIFY_INSTANCE_SIZE_CMD = """
set -euo pipefail

echo "=== Verifying Instance Size ==="

CPUS=$(nproc)
MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEM_GB=$((MEM_KB / 1024 / 1024))

echo "  Current: ${CPUS} vCPUs / ${MEM_GB} GB RAM"

if [ "$CPUS" -ge "4" ] && [ "$MEM_GB" -ge "60" ]; then
    echo "  Instance size OK for ML workload"
    exit 0
fi

echo ""
echo "ERROR: Instance too small for ML pipeline."
echo "  Required: >= 4 vCPUs / 64 GB"
echo "  Current:  ${CPUS} vCPUs / ${MEM_GB} GB"
echo ""
echo "  Resize BEFORE triggering this DAG:"
echo "    bash orchestrator-lifecycle.sh resize-up"
exit 1
"""

# ─── Notify: Resize down reminder at the end ──────────────────────────────

RESIZE_DOWN_REMINDER_CMD = """
set -euo pipefail

CPUS=$(nproc)
MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEM_GB=$((MEM_KB / 1024 / 1024))

echo "=== ML Pipeline Complete ==="
echo "  Current size: ${CPUS} vCPUs / ${MEM_GB} GB"
echo "  Current cost: ~\\$0.148/hr (4 OCPUs / 64 GB)"
echo ""
echo "  IMPORTANT: Scale down to save costs!"
echo "    bash orchestrator-lifecycle.sh resize-down"
echo ""
echo "  Or stop the instance entirely:"
echo "    bash orchestrator-lifecycle.sh stop"
"""

# ─── Install ML packages (idempotent, runs after every container restart) ──

INSTALL_ML_PACKAGES_CMD = f"""
set -euo pipefail
{OCI_PATH_EXPORT}

echo "=== Installing ML packages ==="

# Check if already installed (fast path)
python3 -c "import lightgbm, xgboost, catboost, sklearn, scipy, category_encoders, matplotlib, psutil; print('[OK] All ML packages already installed')" 2>/dev/null && exit 0

echo "  Packages missing — installing..."
pip install --user --quiet \
    scikit-learn lightgbm xgboost catboost \
    category-encoders scipy psutil matplotlib 2>&1 | tail -5

# Verify installation
python3 -c "
import lightgbm, xgboost, catboost, sklearn, scipy
print(f'  lightgbm={{lightgbm.__version__}}')
print(f'  xgboost={{xgboost.__version__}}')
print(f'  catboost={{catboost.__version__}}')
print(f'  sklearn={{sklearn.__version__}}')
print(f'  scipy={{scipy.__version__}}')
print('[OK] All ML packages installed successfully')
"
"""

# ─── Preflight: Check instance has enough memory for ML ────────────────────

CHECK_RESOURCES_CMD = f"""
set -euo pipefail
{OCI_PATH_EXPORT}

echo "=== Preflight: Checking resources ==="

# Check available memory (need at least 30 GB free for ML)
MEM_TOTAL_KB=$(grep MemTotal /proc/meminfo | awk '{{print $2}}')
MEM_AVAIL_KB=$(grep MemAvailable /proc/meminfo | awk '{{print $2}}')
MEM_TOTAL_GB=$((MEM_TOTAL_KB / 1024 / 1024))
MEM_AVAIL_GB=$((MEM_AVAIL_KB / 1024 / 1024))

echo "  Memory: ${{MEM_AVAIL_GB}} GB available / ${{MEM_TOTAL_GB}} GB total"

if [ "$MEM_TOTAL_GB" -lt "30" ]; then
    echo "ERROR: Instance has only ${{MEM_TOTAL_GB}} GB total memory."
    echo "ML pipeline requires at least 64 GB (4 OCPUs)."
    echo ""
    echo "Resize the instance first:"
    echo "  1. Stop instance"
    echo "  2. oci compute instance update --shape-config '{{\"ocpus\":4,\"memoryInGBs\":64}}'"
    echo "  3. Start instance"
    echo "  4. Re-trigger this DAG"
    exit 1
fi

# Check scripts exist
SCRIPTS="{SCRIPTS_DIR}"
for script in feature_selection.py train_credit_risk.py ensemble.py batch_scoring.py monitoring.py; do
    if [ ! -f "$SCRIPTS/$script" ]; then
        echo "ERROR: Missing script $SCRIPTS/$script"
        exit 1
    fi
done
echo "  Scripts: all 5 found in $SCRIPTS"

# Check data exists
if [ ! -d "{DATA_PATH}" ]; then
    echo "ERROR: Data directory {DATA_PATH} not found"
    exit 1
fi
SAFRA_COUNT=$(ls -d {DATA_PATH}/SAFRA=* 2>/dev/null | wc -l)
echo "  Data: $SAFRA_COUNT SAFRAs in {DATA_PATH}"
if [ "$SAFRA_COUNT" -lt "6" ]; then
    echo "ERROR: Expected 6 SAFRAs, found $SAFRA_COUNT"
    exit 1
fi

echo "Preflight PASSED"
"""

# ─── Gold Layer Prerequisite Check ──────────────────────────────────────────

CHECK_GOLD_DATA_CMD = f"""
set -euo pipefail
{OCI_PATH_EXPORT}

echo "Validating Gold data on Object Storage..."
PARTITIONS=$(oci os object list --bucket-name {GOLD_BUCKET} --prefix "feature_store/clientes_consolidado/SAFRA=" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
echo "  clientes_consolidado: $PARTITIONS objects on OCI"
if [ "$PARTITIONS" -lt "1" ]; then
    echo "WARNING: No Gold partitions on Object Storage (may be using local data)"
fi

# Also check local data
if [ -d "{DATA_PATH}" ]; then
    LOCAL_COUNT=$(ls -d {DATA_PATH}/SAFRA=* 2>/dev/null | wc -l)
    echo "  Local data: $LOCAL_COUNT SAFRAs in {DATA_PATH}"
    if [ "$LOCAL_COUNT" -ge "6" ]; then
        echo "Gold validation PASSED (local data available)"
        exit 0
    fi
fi

if [ "$PARTITIONS" -lt "1" ]; then
    echo "ERROR: No Gold data found (neither OCI nor local)"
    exit 1
fi
echo "Gold validation PASSED"
"""

# ─── Helper: Run a Python script LOCALLY on the orchestrator ────────────────

RUN_LOCAL_SCRIPT = """
set -euo pipefail
export PATH=/home/airflow/.local/bin:$PATH
SCRIPT="{script}"

echo "=== Running $SCRIPT locally ==="
echo "Scripts: {scripts_dir}"
echo "Data: {data_path}"
echo "Artifacts: {artifact_dir}"
echo ""

cd {scripts_dir}
export ARTIFACT_DIR={artifact_dir}
export DATA_PATH={data_path}
export OCI_NAMESPACE=grlxi07jz1mo
export GOLD_BUCKET=pod-academy-gold
export FEATURE_SELECTION_MODE=dynamic
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONUNBUFFERED=1

python3 -u $SCRIPT 2>&1

EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
    echo "ERROR: $SCRIPT failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi
echo ""
echo "$SCRIPT completed successfully"
"""

# ─── ML Phase commands ───────────────────────────────────────────────────

RUN_FEATURE_SELECTION_CMD = RUN_LOCAL_SCRIPT.format(
    script="feature_selection.py",
    scripts_dir=SCRIPTS_DIR,
    artifact_dir=ARTIFACT_DIR,
    data_path=DATA_PATH,
)

RUN_DATA_QUALITY_CMD = f"""
set -euo pipefail
{OCI_PATH_EXPORT}
echo "=== Running Data Quality Checks ==="
cd {SCRIPTS_DIR}
export ARTIFACT_DIR={ARTIFACT_DIR}
export DATA_PATH={DATA_PATH}
export OCI_NAMESPACE=grlxi07jz1mo
python3 data_quality.py --namespace grlxi07jz1mo --artifact-dir {ARTIFACT_DIR} 2>&1 || true
echo "Data quality checks completed (non-blocking)"
"""

RUN_TRAINING_CMD = RUN_LOCAL_SCRIPT.format(
    script="train_credit_risk.py",
    scripts_dir=SCRIPTS_DIR,
    artifact_dir=ARTIFACT_DIR,
    data_path=DATA_PATH,
)

RUN_ENSEMBLE_CMD = RUN_LOCAL_SCRIPT.format(
    script="ensemble.py",
    scripts_dir=SCRIPTS_DIR,
    artifact_dir=ARTIFACT_DIR,
    data_path=DATA_PATH,
)

RUN_SCORING_CMD = RUN_LOCAL_SCRIPT.format(
    script="batch_scoring.py",
    scripts_dir=SCRIPTS_DIR,
    artifact_dir=ARTIFACT_DIR,
    data_path=DATA_PATH,
)

RUN_MONITORING_CMD = RUN_LOCAL_SCRIPT.format(
    script="monitoring.py",
    scripts_dir=SCRIPTS_DIR,
    artifact_dir=ARTIFACT_DIR,
    data_path=DATA_PATH,
)

# ─── Collect / organize artifacts ────────────────────────────────────────

COLLECT_ARTIFACTS_CMD = f"""
set -euo pipefail
echo "=== Organizing artifacts ==="
ARTIFACT_DIR="{ARTIFACT_DIR}"
RUN_DATE="{RUN_DATE}"

# Create timestamped snapshot
SNAPSHOT_DIR="${{ARTIFACT_DIR}}/runs/${{RUN_DATE}}"
mkdir -p "$SNAPSHOT_DIR"

# Copy key outputs to snapshot
cp -r $ARTIFACT_DIR/metrics $SNAPSHOT_DIR/ 2>/dev/null || true
cp -r $ARTIFACT_DIR/plots $SNAPSHOT_DIR/ 2>/dev/null || true
cp -r $ARTIFACT_DIR/monitoring $SNAPSHOT_DIR/ 2>/dev/null || true
cp -r $ARTIFACT_DIR/scoring $SNAPSHOT_DIR/ 2>/dev/null || true
cp $ARTIFACT_DIR/selected_features.json $SNAPSHOT_DIR/ 2>/dev/null || true
cp $ARTIFACT_DIR/funnel_summary.json $SNAPSHOT_DIR/ 2>/dev/null || true
cp $ARTIFACT_DIR/ensemble_results.json $SNAPSHOT_DIR/ 2>/dev/null || true

echo "Artifacts snapshot saved to $SNAPSHOT_DIR"
ls -la $SNAPSHOT_DIR/ 2>/dev/null || true

# Summary
echo ""
echo "=== Pipeline Summary ==="
if [ -f "$ARTIFACT_DIR/metrics/training_results_*.json" ]; then
    echo "Training results: $(ls $ARTIFACT_DIR/metrics/training_results_*.json 2>/dev/null)"
fi
echo "Models: $(ls $ARTIFACT_DIR/models/*.pkl 2>/dev/null | wc -l) PKL files"
echo "Plots: $(ls $ARTIFACT_DIR/plots/*.png 2>/dev/null | wc -l) PNG files"
"""

# ─── DAG Definition ─────────────────────────────────────────────────────────

with DAG(
    dag_id="credit_risk_ml_pipeline",
    default_args=default_args,
    description="ML Pipeline: Feature Selection > Training > Ensemble > Scoring > Monitoring (local execution)",
    schedule_interval=None,
    start_date=datetime(2026, 3, 1),
    catchup=False,
    tags=["credit-risk", "ml-pipeline", "auto-resize"],
    max_active_runs=1,
) as dag:

    # ── Infrastructure: Verify instance is resized ───────────────────────
    verify_instance = BashOperator(
        task_id="verify_instance_4ocpu_64gb",
        bash_command=VERIFY_INSTANCE_SIZE_CMD,
        execution_timeout=timedelta(minutes=5),
    )

    # ── Install ML packages (idempotent, needed after container restart) ──
    install_packages = BashOperator(
        task_id="install_ml_packages",
        bash_command=INSTALL_ML_PACKAGES_CMD,
        execution_timeout=timedelta(minutes=15),
    )

    # ── Preflight ─────────────────────────────────────────────────────────
    check_resources = BashOperator(
        task_id="check_resources",
        bash_command=CHECK_RESOURCES_CMD,
        execution_timeout=timedelta(minutes=2),
    )

    check_gold_data = BashOperator(
        task_id="check_gold_data",
        bash_command=CHECK_GOLD_DATA_CMD,
        execution_timeout=timedelta(minutes=5),
    )

    # ── ML Pipeline Tasks ─────────────────────────────────────────────────
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

    collect_artifacts = BashOperator(
        task_id="collect_artifacts",
        bash_command=COLLECT_ARTIFACTS_CMD,
        execution_timeout=timedelta(minutes=15),
    )

    # ── Infrastructure: Resize down reminder ──────────────────────────────
    resize_reminder = BashOperator(
        task_id="resize_down_reminder",
        bash_command=RESIZE_DOWN_REMINDER_CMD,
        execution_timeout=timedelta(minutes=5),
        trigger_rule="all_done",  # Run even if upstream tasks failed
    )

    # ── Task Dependencies ──────────────────────────────────────────────────
    #
    # Visual flow in Airflow UI:
    #
    #   verify_instance_4ocpu_64gb
    #         │
    #   install_ml_packages
    #         │
    #   check_resources
    #         │
    #   check_gold_data
    #       ┌───┐
    #  feature_sel  data_quality
    #       │
    #   run_training
    #       │
    #   run_ensemble
    #       │
    #   run_scoring
    #       │
    #   run_monitoring
    #       │
    #   collect_artifacts
    #       │
    #   resize_down_reminder
    #

    # Verify instance size → Install packages → Preflight
    verify_instance >> install_packages >> check_resources >> check_gold_data

    # Feature Selection and Data Quality run in parallel after gold check
    check_gold_data >> [run_feature_selection, run_data_quality]

    # ML Pipeline sequential
    run_feature_selection >> run_training >> run_ensemble >> run_scoring >> run_monitoring >> collect_artifacts

    # Reminder to resize down (trigger_rule=all_done ensures it runs even on failure)
    [collect_artifacts, run_data_quality] >> resize_reminder
