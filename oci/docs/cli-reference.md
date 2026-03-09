# OCI CLI Quick Reference — Credit Risk Platform

## Data Flow

### Submit Pipeline Run
```bash
# Unified pipeline
oci data-flow run submit \
    --application-id $UNIFIED_APP_OCID \
    --display-name "pipeline-$(date +%Y%m%d)" \
    --arguments '["--start-phase", "bronze"]'

# Individual stage
oci data-flow run submit \
    --application-id $APP_OCID \
    --display-name "stage-name-$(date +%Y%m%d)"
```

### Monitor Run
```bash
# Get run status
oci data-flow run get --run-id $RUN_OCID \
    --query 'data.{"State":"lifecycle-state","Duration":"run-duration-in-milliseconds"}' \
    --output table

# List recent runs
oci data-flow run list \
    --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{"Name":"display-name","State":"lifecycle-state","Created":"time-created"}' \
    --output table --limit 10

# Get driver logs
oci data-flow run get-log --run-id $RUN_OCID --name spark_driver_stderr

# Get stdout
oci data-flow run get-log --run-id $RUN_OCID --name spark_driver_stdout
```

### Manage Applications
```bash
# List applications
oci data-flow application list \
    --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{"Name":"display-name","ID":id}' --output table

# Get application details
oci data-flow application get --application-id $APP_OCID
```

---

## Data Science

### Jobs
```bash
# Create job run (batch scoring)
oci data-science job-run create \
    --job-id $JOB_OCID \
    --compartment-id $COMPARTMENT_OCID \
    --display-name "scoring-$(date +%Y%m%d)"

# List job runs
oci data-science job-run list \
    --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{"Name":"display-name","State":"lifecycle-state"}' \
    --output table

# Get job run status
oci data-science job-run get --job-run-id $JOB_RUN_OCID
```

### Models
```bash
# List models
oci data-science model list \
    --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{"Name":"display-name","State":"lifecycle-state","Created":"time-created"}' \
    --output table

# Create model
oci data-science model create \
    --compartment-id $COMPARTMENT_OCID \
    --project-id $PROJECT_OCID \
    --display-name "credit-risk-ensemble-v20260308"

# Get model details
oci data-science model get --model-id $MODEL_OCID
```

### Notebook Session
```bash
# Start notebook
oci data-science notebook-session activate --notebook-session-id $NOTEBOOK_OCID

# Stop notebook
oci data-science notebook-session deactivate --notebook-session-id $NOTEBOOK_OCID

# Get status
oci data-science notebook-session get --notebook-session-id $NOTEBOOK_OCID \
    --query 'data.{"State":"lifecycle-state","URL":"notebook-session-url"}' --output table
```

---

## Object Storage

### Upload / Download
```bash
# Upload single file
oci os object put --bucket-name $BUCKET --file ./file.parquet --name path/file.parquet --force

# Bulk upload directory
oci os object bulk-upload --bucket-name $BUCKET --src-dir ./data/ --prefix data/ --overwrite

# Download file
oci os object get --bucket-name $BUCKET --name path/file.parquet --file ./local_file.parquet

# Bulk download
oci os object bulk-download --bucket-name $BUCKET --prefix feature_store/ --download-dir ./data/
```

### List / Manage
```bash
# List objects
oci os object list --bucket-name $BUCKET \
    --prefix feature_store/ \
    --query 'data[*].{Name:name,Size:size,Modified:"time-modified"}' --output table

# Delete object
oci os object delete --bucket-name $BUCKET --name path/file.parquet --force

# List buckets
oci os bucket list --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{Name:name,Created:"time-created"}' --output table
```

---

## Monitoring

### Alarms
```bash
# List alarms
oci monitoring alarm list \
    --compartment-id $COMPARTMENT_OCID \
    --query 'data[*].{"Name":"display-name","State":"lifecycle-state","Severity":severity}' \
    --output table

# Get alarm status
oci monitoring alarm-status list-alarms-status \
    --compartment-id $COMPARTMENT_OCID

# Get metric data (last 1 hour)
oci monitoring metric-data summarize-metrics-data \
    --compartment-id $COMPARTMENT_OCID \
    --namespace custom_metrics \
    --query-text "model_psi[1h].mean()"
```

### Notifications
```bash
# Publish to ONS topic
oci ons message publish \
    --topic-id $ONS_TOPIC_OCID \
    --title "Alert Title" \
    --body "Alert message body"
```

---

## Database (ADW)

```bash
# Start ADW
oci db autonomous-database start --autonomous-database-id $ADW_OCID

# Stop ADW
oci db autonomous-database stop --autonomous-database-id $ADW_OCID

# Get status
oci db autonomous-database get --autonomous-database-id $ADW_OCID \
    --query 'data.{"State":"lifecycle-state","DB":"db-name"}' --output table
```

---

## Data Catalog

```bash
# List catalogs
oci data-catalog catalog list --compartment-id $COMPARTMENT_OCID

# Create harvest job
oci data-catalog job create \
    --catalog-id $CATALOG_OCID \
    --job-type HARVEST \
    --display-name "harvest-gold-$(date +%Y%m%d)"

# List data assets
oci data-catalog data-asset list --catalog-id $CATALOG_OCID
```

---

## Compute (Orchestrator)

```bash
# Get instance status
oci compute instance get --instance-id $INSTANCE_OCID \
    --query 'data.{"State":"lifecycle-state","Shape":shape}' --output table

# SSH to orchestrator (via bastion)
ssh -i key.pem opc@<private_ip>

# Reboot
oci compute instance action --instance-id $INSTANCE_OCID --action SOFTRESET
```

---

## Cost Management

```bash
# Get budget
oci budgets budget list --compartment-id $TENANCY_OCID \
    --query 'data[*].{"Name":"display-name","Amount":amount,"Actual":"actual-spend"}' \
    --output table

# Usage report
oci account usage-report list --compartment-id $TENANCY_OCID
```
