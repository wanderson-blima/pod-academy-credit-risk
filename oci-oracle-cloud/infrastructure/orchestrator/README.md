# Orchestrator — Docker Airflow on OCI E3.Flex

Airflow runs on the orchestrator VM (146.235.27.18) via Docker Compose with 3 containers: scheduler, webserver, postgres.

## Directory Layout (on orchestrator)

```
/home/opc/
├── orchestrator/
│   ├── dags/                    # Airflow DAGs (mounted into containers)
│   ├── docker-compose.yaml      # 3 services: scheduler, webserver, postgres
│   ├── airflow.env              # Airflow env vars (FERNET_KEY, executor, etc.)
│   └── setup_airflow.sh         # Initial setup script
├── ml-pipeline/
│   └── scripts/                 # Python scripts (uploaded via SCP)
│       ├── train_credit_risk.py
│       ├── feature_selection.py
│       ├── ensemble.py
│       ├── batch_scoring.py
│       ├── monitoring.py
│       └── data_quality.py
├── data/
│   └── gold/                    # Parquet files (600 files, 1.3 GB)
│       └── clientes_consolidado/
└── artifacts/                   # Output: models, metrics, plots, scoring
```

## DAGs

Two production DAGs, plus one deprecated unified DAG:

| DAG ID | File | Purpose |
|--------|------|---------|
| `credit_risk_data_pipeline` | `credit_risk_data_pipeline.py` | Bronze -> Silver -> Gold (data ingestion) |
| `credit_risk_ml_pipeline` | `credit_risk_ml_pipeline.py` | Feature Selection -> Training -> Ensemble -> Scoring -> Monitoring |
| `credit_risk_pipeline` | `credit_risk_pipeline.py` | [DEPRECATED] Unified DAG with 13 tasks |

Execution order: run data pipeline first, then ML pipeline.

### ML Pipeline Tasks (credit_risk_ml_pipeline)

```
verify_instance -> install_ml_packages -> check_resources -> check_gold_data
    -> run_data_quality -> run_feature_selection -> run_training
    -> run_ensemble -> run_scoring -> run_monitoring
    -> collect_artifacts -> resize_down_reminder
```

Total time: ~58 min on E3.Flex 4 OCPUs / 64 GB.

## Airflow Variables

Set these in Airflow UI (Admin > Variables) or via CLI **before** triggering DAGs:

| Variable | Required By | Description | Example |
|----------|-------------|-------------|---------|
| `COMPARTMENT_OCID` | Both DAGs | OCID do compartment OCI | `ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq` |
| `ORCHESTRATOR_INSTANCE_OCID` | ML Pipeline | OCID da instancia orchestrator (para resize) | `ocid1.instance.oc1.sa-saopaulo-1..XXXXX` |
| `UNIFIED_APP_OCID` | Data Pipeline | OCID do Data Flow Application (Spark) | `ocid1.dataflowapplication.oc1.sa-saopaulo-1..XXXXX` |

```bash
# Set all required variables
docker exec airflow-webserver airflow variables set COMPARTMENT_OCID \
  "ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"
docker exec airflow-webserver airflow variables set ORCHESTRATOR_INSTANCE_OCID \
  "<instance-ocid>"
docker exec airflow-webserver airflow variables set UNIFIED_APP_OCID \
  "<dataflow-app-ocid>"

# Verify
docker exec airflow-webserver airflow variables list
```

### OCI CLI inside container

The Airflow container needs OCI CLI installed and configured for Data Flow operations:

```bash
# OCI CLI is installed at /home/airflow/.local/bin/oci
# Authentication uses instance principal (no config file needed)
# The orchestrator VM has a dynamic group policy granting Data Flow + Object Storage access
```

## Docker Compose

Three containers defined in `docker-compose.yaml`:

| Container | Port | Role |
|-----------|------|------|
| airflow-webserver | 8080 | Web UI + CLI |
| airflow-scheduler | — | DAG scheduling and task execution |
| airflow-postgres | 5432 | Metadata database |

Start/stop:

```bash
cd /home/opc/orchestrator
docker compose up -d        # Start all 3 containers
docker compose down         # Stop all
docker compose ps           # Check status
docker compose logs -f --tail=50 airflow-scheduler  # Tail scheduler logs
```

## Instance Lifecycle (Resize)

The ML pipeline requires 4 OCPUs / 64 GB. For cost savings, resize down to 2 OCPUs / 16 GB when not running ML workloads.

**Before ML pipeline** -- resize up:

```bash
oci compute instance update \
  --instance-id <ORCHESTRATOR_INSTANCE_OCID> \
  --shape-config '{"ocpus": 4, "memoryInGBs": 64}' \
  --force
```

**After ML pipeline** -- resize down:

```bash
oci compute instance update \
  --instance-id <ORCHESTRATOR_INSTANCE_OCID> \
  --shape-config '{"ocpus": 2, "memoryInGBs": 16}' \
  --force
```

The DAG includes `resize_down_reminder` as the final task.

## Triggering DAGs

```bash
# Via SSH
ssh -i ~/.ssh/oci_pipeline opc@146.235.27.18

# Trigger data pipeline
docker exec airflow-webserver airflow dags trigger credit_risk_data_pipeline

# Trigger ML pipeline (after data pipeline completes)
docker exec airflow-webserver airflow dags trigger credit_risk_ml_pipeline

# Check run status
docker exec airflow-webserver airflow dags list-runs -d credit_risk_ml_pipeline --limit 3
```

Or use the Airflow Web UI at http://146.235.27.18:8080.

## Uploading Scripts

From local machine:

```bash
scp -i ~/.ssh/oci_pipeline scripts/*.py opc@146.235.27.18:/home/opc/ml-pipeline/scripts/
```

## Uploading DAGs

```bash
scp -i ~/.ssh/oci_pipeline infrastructure/dags/credit_risk_*.py \
  opc@146.235.27.18:/home/opc/orchestrator/dags/
```

DAGs are auto-detected by the scheduler (mounted volume). Allow ~30s for parsing.

## DAG Migration (Deprecated → Production)

The original `credit_risk_pipeline.py` (unified, 13 tasks) was split into two DAGs for better separation of concerns:

| Aspecto | Unified (DEPRECATED) | Data + ML (Production) |
|---------|----------------------|------------------------|
| **Arquivo** | `credit_risk_pipeline.py` | `credit_risk_data_pipeline.py` + `credit_risk_ml_pipeline.py` |
| **Tasks** | 13 (tudo junto) | 3 (Data Flow) + 12 (ML local) |
| **Execucao** | Sequencial completa | Independente — data primeiro, ML depois |
| **Resize** | Nao automatico | ML DAG verifica/resize automaticamente |
| **Retry** | Reinicia tudo | Pode re-executar apenas ML sem refazer data |

Para migrar: basta parar de usar o DAG deprecated e triggerar os dois novos DAGs na ordem correta.

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| DAG nao aparece no UI | Erro de sintaxe no Python | `docker exec airflow-scheduler python /opt/airflow/dags/credit_risk_ml_pipeline.py` |
| Task falha com "Instance too small" | Orchestrator com 2 OCPUs | `bash orchestrator-lifecycle.sh resize-up` antes de triggerar |
| OCI CLI "NotAuthorizedOrNotFound" | Instance principal sem policy | Verificar dynamic group e policy no Terraform |
| Task "run_training" OOM killed | 64 GB insuficiente | Verificar se gold data tem 600 parquets (nao duplicados) |
| Scheduler nao executa tasks | Scheduler parado/crashado | `docker compose restart airflow-scheduler` |
| Logs em branco | Buffer do Python | Scripts usam `PYTHONUNBUFFERED=1` (ja configurado nos DAGs) |
| Data Flow run FAILED | Bucket vazio ou app OCID errado | Verificar `UNIFIED_APP_OCID` e conteudo dos buckets |
