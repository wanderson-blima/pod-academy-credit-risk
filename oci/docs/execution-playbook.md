# Execution Playbook — PRD Story-by-Story

> Maps each PRD story to its execution script and evidence output.
> Execute stories in order. Each produces evidence in `oci/tests/evidence/story-{id}/`.

## Prerequisites

```bash
export COMPARTMENT_OCID="ocid1.compartment.oc1....."
export NAMESPACE="grlxi07jz1mo"
```

---

## Quick Reference

| Story | Script | Evidence |
|-------|--------|----------|
| 1.1 ARM A1 | `terraform apply -target=module.orchestrator` | instance OCID |
| 1.2 Airflow | `setup_airflow.sh` | docker ps output |
| 1.3 DAG | Copy DAG + `airflow dags list` | DAG screenshot |
| 2.1 Buckets | `ops/validate_buckets.sh` | `bucket_inventory.json` |
| 2.2 Bronze | `ops/validate_bronze.sh` | `bronze_tables.json` |
| 3.1 Upload | `ops/upload_scripts.sh` | `app_ocids.json` |
| 3.2 Silver | `ops/run_silver.sh` | `silver_run.json` |
| 3.3 Gold | `ops/run_gold.sh` | `gold_run.json` |
| 4.1 Notebook | `ops/validate_notebook.sh` | `notebook_status.json` |
| 4.2 Train | `python train_credit_risk.py` (in notebook) | `training_results.json` |
| 4.3 Catalog | `python register_model_catalog.py` + `ops/validate_model_catalog.sh` | `model_ocids.json` |
| 4.4 Scoring | `python batch_scoring.py` + `ops/validate_scores.sh` | `score_distribution.json` |
| 4.5 Deploy | `python deploy_endpoint.py` + `ops/validate_deployment.sh` | `endpoint_url.json` |
| 5.1 ADW | Execute SQL scripts in Database Actions | `sql_results.json` |
| 5.2 APEX | Execute APEX SQL + `seed_dashboard.py` | screenshots |
| 5.3 Catalog | `ops/harvest-catalog.sh` + `ops/validate_catalog.sh` | `catalog_harvest.json` |

## Status Check

```bash
for id in 1.1 1.2 1.3 2.1 2.2 3.1 3.2 3.3 4.1 4.2 4.3 4.4 4.5 5.1 5.2 5.3; do
    FILES=$(find oci/tests/evidence/story-$id -type f ! -name '.gitkeep' 2>/dev/null | wc -l)
    [ "$FILES" -gt "0" ] && echo "[x] Story $id ($FILES files)" || echo "[ ] Story $id"
done
```
