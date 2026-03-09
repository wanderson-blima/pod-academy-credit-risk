# Step-by-Step Guide — OCI Credit Risk Platform

**Last Updated**: 2026-03-08
**Platform**: Oracle Cloud Infrastructure (sa-saopaulo-1)
**Trial Credit**: US$ 500

---

## Prerequisites

### OCI CLI
```bash
# Install OCI CLI
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"

# Configure
oci setup config
# Provide: tenancy OCID, user OCID, region (sa-saopaulo-1), API key path
```

### Environment Variables
```bash
export COMPARTMENT_OCID="ocid1.compartment.oc1..xxx"
export TENANCY_OCID="ocid1.tenancy.oc1..xxx"
export OCI_NAMESPACE="grlxi07jz1mo"
export PREFIX="pod-academy"
```

### Terraform
```bash
# Install Terraform >= 1.3.0
# Download from: https://developer.hashicorp.com/terraform/downloads
terraform --version
```

---

## 1. Infrastructure Deployment

### Option A: Terraform (Recommended)

```bash
cd oci/infrastructure/terraform

# Initialize
terraform init

# Review plan
terraform plan -var-file="terraform.tfvars.dev"

# Apply
terraform apply -var-file="terraform.tfvars.dev"
```

**Resources created** (~50+):
- VCN + 3 subnets + gateways + NSGs
- 6 Object Storage buckets (landing, bronze, silver, gold, logs, scripts)
- ADW (2 ECPU)
- Data Flow pool + 4 applications (bronze, silver, gold, unified)
- Data Science project + notebook
- ARM orchestrator instance (Always Free)
- Data Catalog
- KMS Vault + key
- Monitoring (topic, alarms)
- Budget alerts
- IAM dynamic groups + policies

### Option B: OCI Console (Manual)

1. **Networking**: VCN Wizard > Create VCN with Internet Connectivity
   - VCN CIDR: 10.0.0.0/16
   - Public subnet: 10.0.0.0/24
   - Private subnets: 10.0.1.0/24 (data), 10.0.2.0/24 (compute)

2. **Storage**: Object Storage > Create Bucket (repeat for 6 buckets)
   - pod-academy-landing, bronze, silver, gold, logs, scripts

3. **Database**: Autonomous Database > Create > Data Warehouse > 2 ECPU

4. **Data Flow**: Data Flow > Applications > Create Application (repeat for each)

5. **Data Science**: Data Science > Create Project > Create Notebook Session

6. **Orchestrator**: Compute > Create Instance > VM.Standard.A1.Flex (4 OCPU, 24 GB)

---

## 2. Upload Data to Landing

```bash
# Upload raw data files to landing bucket
for table in dados_cadastrais telco score_bureau_movel recarga pagamento faturamento; do
    oci os object bulk-upload \
        --bucket-name pod-academy-landing \
        --src-dir ./data/${table}/ \
        --prefix ${table}/ \
        --overwrite
done

# Upload dimension CSVs
oci os object bulk-upload --bucket-name pod-academy-landing \
    --src-dir ./data/recarga_dim/ --prefix recarga_dim/ --overwrite

oci os object bulk-upload --bucket-name pod-academy-landing \
    --src-dir ./data/faturamento_dim/ --prefix faturamento_dim/ --overwrite
```

### Verify Upload
```bash
oci os object list --bucket-name pod-academy-landing \
    --query 'data[*].{Name:name,Size:size}' --output table
```

---

## 3. Upload Pipeline Scripts

```bash
# Upload all pipeline scripts to scripts bucket
for script in ingest_bronze.py transform_silver.py engineer_gold.py unified_pipeline.py; do
    oci os object put \
        --bucket-name pod-academy-scripts \
        --file oci/pipeline/${script} \
        --name ${script} --force
done

# Create dependency archive for unified pipeline
cd oci/pipeline
zip -j /tmp/pipeline_deps.zip ingest_bronze.py transform_silver.py engineer_gold.py
oci os object put --bucket-name pod-academy-scripts \
    --file /tmp/pipeline_deps.zip --name pipeline_deps.zip --force
cd -
```

---

## 4. Pipeline Execution

### Option A: Unified Pipeline (Recommended)

```bash
# Submit unified pipeline (Bronze -> Silver -> Gold in one job)
oci data-flow run submit \
    --application-id $UNIFIED_APP_OCID \
    --display-name "unified-pipeline-$(date +%Y%m%d)" \
    --arguments '["--start-phase", "bronze"]'
```

### Option B: Individual Stages

```bash
# 1. Bronze ingestion
oci data-flow run submit \
    --application-id $BRONZE_APP_OCID \
    --display-name "bronze-$(date +%Y%m%d)"

# 2. Silver transformation (after Bronze completes)
oci data-flow run submit \
    --application-id $SILVER_APP_OCID \
    --display-name "silver-$(date +%Y%m%d)"

# 3. Gold feature engineering (after Silver completes)
oci data-flow run submit \
    --application-id $GOLD_APP_OCID \
    --display-name "gold-$(date +%Y%m%d)"
```

### Option C: Orchestrated (Automatic)

```bash
# SSH to orchestrator
ssh -i key.pem opc@<orchestrator_ip>

# Run pipeline
/home/opc/orchestrator/run_pipeline.sh

# Or schedule weekly
/home/opc/orchestrator/schedule_pipeline.sh weekly
```

### Monitor Pipeline
```bash
oci data-flow run get --run-id $RUN_OCID \
    --query 'data.{"State":"lifecycle-state","Duration":"run-duration-in-milliseconds"}' \
    --output table

# View logs
oci data-flow run get-log --run-id $RUN_OCID --name spark_driver_stderr
```

---

## 5. Model Training & Scoring

### Train Models
```bash
# From Data Science notebook or locally:
python oci/model/train_credit_risk.py
# Trains LR L1 + LightGBM, validates QG-05
```

### Batch Scoring
```bash
# Score all 3.9M customers
python oci/model/batch_scoring.py
# Output: pod-academy-gold/clientes_scores/
```

### Register in Model Catalog
```bash
python oci/model/register_model_catalog.py
# Registers LR L1, LightGBM, Ensemble with metadata
```

### Deploy REST Endpoint (Optional)
```bash
# From Data Science notebook:
python oci/model/deploy_endpoint.py
# Creates REST endpoint for real-time scoring
```

---

## 6. ADW External Tables

```bash
# Connect to ADW
sql ADMIN/<password>@<connection_string>

# Run setup scripts in order
@oci/infrastructure/adw/01_setup_credentials.sql
@oci/infrastructure/adw/02_create_external_tables.sql
@oci/infrastructure/adw/03_create_views.sql
@oci/infrastructure/adw/04_validate.sql
```

**Console Alternative**: Database Actions > SQL Worksheet > paste and run each script.

---

## 7. Data Catalog Harvesting

```bash
# After Terraform creates the catalog:
bash oci/infrastructure/ops/harvest-catalog.sh
```

Then configure in Console: Data Catalog > Catalog > Data Assets > Configure connections > Run harvesting jobs.

---

## 8. Monitoring & Alerts

### APEX Dashboard
URL: `https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/`

### Run Model Monitor
```bash
python oci/model/monitor_model.py --scores-path oci/artifacts/scoring/ --publish-metrics
```

### OCI Alarms
Configured via Terraform:
- Pipeline failure alerts
- PSI drift detection (threshold: 0.25)
- KS degradation (threshold: 0.20)
- Budget alerts (50%, 80%, 100%)

---

## 9. Cost Management

### Start Resources
```bash
bash oci/infrastructure/ops/start-infra.sh
```

### Stop Resources (end of session)
```bash
bash oci/infrastructure/ops/stop-infra.sh
```

### Cost Report
```bash
bash oci/infrastructure/ops/cost-report.sh
```

### Estimated Monthly Cost
| Component | Cost |
|-----------|------|
| ARM Orchestrator (4 OCPU, 24 GB) | $0 (Always Free) |
| ADW (2 ECPU) | $0 (Always Free) |
| Object Storage (~20 GB) | ~$0.50 |
| Data Flow (4 runs/month, 14 OCPUs, 30 min) | ~$8-12 |
| Data Science notebook (20h/month) | ~$15-25 |
| Data Catalog | $0 (Free tier) |
| KMS Vault | ~$5 |
| **Total** | **~$30-45/month** |

---

## 10. Emergency Procedures

### Pipeline Failure Recovery
```bash
# Resume from last successful phase
/home/opc/orchestrator/run_pipeline.sh --start-phase silver
```

### Full Teardown
```bash
bash oci/infrastructure/ops/backup-data.sh  # Backup first!
cd oci/infrastructure/terraform
terraform destroy -var-file="terraform.tfvars.dev"
```

---

## Architecture Overview

```
Landing (CSV/Parquet) -> Bronze (Delta) -> Silver (Delta) -> Gold (Delta)
     |                                                          |
     OCI Data Flow (Unified Pipeline)                          |
                                                               v
                                                    ADW External Tables
                                                    APEX Dashboard
                                                               |
                                                    Data Science Job
                                                    (Batch Scoring)
                                                               |
                                                    Model Catalog
                                                    REST Endpoint

Orchestrator (ARM A1 Always-Free) -> Cron -> Data Flow -> Data Science
                                          -> ONS Alerts
                                          -> Health Checks

Data Catalog -> Harvest Bronze/Silver/Gold -> Lineage tracking
```
