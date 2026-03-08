# Operations Runbook — OCI Data Platform

**Last Updated**: 2026-03-07
**Platform**: Oracle Cloud Infrastructure (sa-saopaulo-1)
**Trial Credit**: US$ 500 | **Budget Alert**: R$ 500/month | **Accumulated Spend**: R$ 171.71

---

## Prerequisites

All operations require:
- OCI CLI installed and configured (`~/.oci/config`)
- Environment variables set:
  ```bash
  export COMPARTMENT_OCID="ocid1.compartment.oc1..xxx"
  export TENANCY_OCID="ocid1.tenancy.oc1..xxx"
  export ADW_OCID="ocid1.autonomousdatabase.oc1..xxx"
  export NOTEBOOK_OCID="ocid1.datasciencenotebooksession.oc1..xxx"
  export PREFIX="pod-academy"
  ```
- Scripts located in: `oci/infrastructure/ops/`

---

## Daily Operations

### Start Infrastructure
Starts ADW and Data Science notebook for active development/scoring.

```bash
bash oci/infrastructure/ops/start-infra.sh
```

Resources started: ADW (AVAILABLE), Notebook (ACTIVE).
Data Flow and Object Storage are always available (on-demand).

### Stop Infrastructure
Stops compute resources to minimize costs. **Run at end of each work session.**

```bash
bash oci/infrastructure/ops/stop-infra.sh
```

Resources stopped: ADW (STOPPED), Notebook (INACTIVE), Model Deployments (deactivated).
Estimated savings: eliminates compute charges while storage costs remain.

### Health Check
Verifies all infrastructure components are operational.

```bash
bash oci/infrastructure/ops/health-check.sh
```

Checks: 6 buckets, Data Science project, Data Flow apps, VCN, ADW status, budget, model artifacts.

---

## Pipeline Execution

### Full Pipeline (Bronze -> Silver -> Gold)

```bash
# 1. Ingest to Bronze (Object Storage)
oci data-flow run submit \
  --application-id $BRONZE_APP_OCID \
  --display-name "bronze-ingest-$(date +%Y%m%d)"

# 2. Transform to Silver
oci data-flow run submit \
  --application-id $SILVER_APP_OCID \
  --display-name "silver-transform-$(date +%Y%m%d)"

# 3. Engineer Gold features
oci data-flow run submit \
  --application-id $GOLD_APP_OCID \
  --display-name "gold-engineer-$(date +%Y%m%d)"
```

### Monitor Pipeline Run
```bash
oci data-flow run get --run-id $RUN_OCID \
  --query 'data.{"State":"lifecycle-state","Duration":"run-duration-in-milliseconds"}' \
  --output table
```

Expected durations: Bronze ~45 min, Silver ~90 min, Gold ~287 min (trial cluster).

---

## Batch Scoring

### Run Batch Scoring
```bash
# From OCI Data Science notebook or locally:
python oci/model/batch_scoring.py
```

Output: `pod-academy-gold/clientes_scores/clientes_scores_all.parquet`
Records: ~230K per scoring run

### Verify Scoring Output
```bash
oci os object list --bucket-name pod-academy-gold \
  --prefix clientes_scores/ \
  --query 'data[*].{Name:name,Size:size,Modified:"time-modified"}' \
  --output table
```

---

## Model Monitoring

### Run Model Monitor
```bash
python oci/model/monitor_model.py \
  --scores-path oci/artifacts/scoring/ \
  --output-dir oci/artifacts/monitoring/
```

Output: `monitoring_report_YYYYMMDD.json` with PSI and feature drift analysis.

To also publish metrics to OCI Monitoring and update the live dashboard:
```bash
python oci/model/monitor_model.py \
  --scores-path oci/artifacts/scoring/ \
  --output-dir oci/artifacts/monitoring/ \
  --publish-metrics
```

### Live Dashboard

**URL**: https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/

Dashboard dinamico servido via ORDS REST do ADW. 3 paginas:
- **Executive Overview**: KPIs (KS, AUC, Gini, PSI) + charts de tendencia
- **Model Performance**: Comparacao LightGBM vs LR L1 + Feature drift
- **Operations & Costs**: Pipeline history + cost breakdown

Os dados atualizam automaticamente ao inserir novos registros nas tabelas do schema MLMONITOR.

**APEX Builder** (para customizacao):
- URL: `https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/apex`
- Workspace: `MLMONITOR` | User: `DASHADMIN` | Pass: `CreditRisk2026#ML`

**Nota**: O ADW precisa estar AVAILABLE para o dashboard funcionar. Para ligar: `oci db autonomous-database start --autonomous-database-id $ADW_OCID`

### PSI Thresholds
| PSI Range | Status | Action |
|-----------|--------|--------|
| < 0.10 | OK | Continue monitoring |
| 0.10 - 0.25 | WARNING | Investigate feature drift, increase monitoring frequency |
| > 0.25 | RETRAIN | Retrain model with recent data |

### Current Baseline
- LR PSI: 0.000749 (OK)
- LGBM PSI: 0.001205 (OK)

---

## Incident Response

### Pipeline Failure

1. Check Data Flow run logs:
   ```bash
   oci data-flow run get-log --run-id $RUN_OCID --name spark_driver_stderr
   ```
2. Common causes:
   - **OutOfMemory**: Increase executor memory or reduce partition size
   - **FileNotFound**: Verify source files in Object Storage
   - **PermissionDenied**: Check dynamic group policies
3. Retry the failed stage only (pipeline is idempotent).

### Model Drift Detected

1. Run `monitor_model.py` to confirm PSI values.
2. Check which features drifted in the monitoring report.
3. If PSI > 0.25:
   - Pull latest Gold data
   - Retrain using `train_credit_risk.py`
   - Compare new metrics against baseline
   - Update model artifacts in Object Storage
4. Document in monitoring history.

### Budget Alert Triggered

1. Run cost report:
   ```bash
   bash oci/infrastructure/ops/cost-report.sh
   ```
2. If spend > 80% of budget:
   - Stop ADW: `bash oci/infrastructure/ops/stop-infra.sh`
   - Review Data Flow run frequency
   - Check for orphaned resources
3. If spend > 95%:
   - Emergency stop all compute
   - Review with team before any new runs

---

## Backup & Recovery

### Backup Critical Data
```bash
bash oci/infrastructure/ops/backup-data.sh
```

Downloads Gold feature store and model artifacts to `./backup/`.

### Recovery Procedure
1. Verify Terraform state: `cd oci/infrastructure/terraform && terraform plan`
2. If state is corrupted: `terraform import` for critical resources
3. Re-upload data from backup if needed
4. Re-run pipeline from last successful stage

---

## Emergency Teardown

**WARNING**: Destroys all OCI infrastructure. Data will be lost.

1. **Backup first**: `bash oci/infrastructure/ops/backup-data.sh`
2. **Notify team** of planned teardown
3. **Execute destroy**:
   ```bash
   bash oci/infrastructure/ops/destroy-infra.sh
   ```
4. **Verify cleanup**: Confirm $0 compute charges in OCI Console
5. **Archive Terraform state** for audit trail

---

## Key Contacts

| Role | Contact |
|------|---------|
| OCI Platform Lead | wandersonlima20@gmail.com |
| Budget Alerts | wandersonlima20@gmail.com |

---

## Resource Reference

| Resource | Type | Cost Model |
|----------|------|------------|
| 6 Object Storage Buckets | Always-on | Per GB stored + requests |
| ADW (2 ECPU) | Start/Stop | Per ECPU-hour when AVAILABLE |
| Data Flow (3 apps) | On-demand | Per OCPU-hour during runs |
| Data Science Project | Always-on | Free (project metadata only) |
| Notebook Session | Start/Stop | Per OCPU-hour when ACTIVE |
| VCN + Gateways | Always-on | Free (standard networking) |
| KMS Vault + Key | Always-on | Per key version/month |
