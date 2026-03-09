"""
Airflow DAG: Credit Risk Pipeline — Medallion Data Lakehouse
Orchestrates: Bronze → Silver → Gold → Training → Scoring
Uses a single unified Data Flow application with maximum capacity.
Each phase runs as a separate Data Flow run for validation between phases.

Schedule: Weekly on Monday at 02:00 (America/Sao_Paulo)
Trigger: Manual or scheduled
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
    "retries": 2,
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

RUN_TRAINING_CMD = """
set -euo pipefail
echo "Training step — to be executed in OCI Data Science Notebook"
echo "This task is a placeholder for manual or job-triggered training"
"""

RUN_SCORING_CMD = """
set -euo pipefail
echo "Scoring step — to be executed after training completes"
echo "This task is a placeholder for batch scoring execution"
"""

# ─── DAG Definition ─────────────────────────────────────────────────────────

with DAG(
    dag_id="credit_risk_pipeline",
    default_args=default_args,
    description="Medallion pipeline: Bronze → Silver → Gold → Training → Scoring",
    schedule_interval="0 2 * * 1",  # Weekly Monday 02:00
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

    run_training = BashOperator(
        task_id="run_training",
        bash_command=RUN_TRAINING_CMD,
    )

    run_scoring = BashOperator(
        task_id="run_scoring",
        bash_command=RUN_SCORING_CMD,
    )

    # Task dependencies: Bronze → validate → Silver → validate → Gold → validate → Training → Scoring
    run_bronze >> validate_bronze >> run_silver >> validate_silver >> run_gold >> validate_gold >> run_training >> run_scoring
