# Final Documentation Package — OCI Data Platform

**Project**: Hackathon PoD Academy — Credit Risk FPD (Claro + Oracle)
**Date**: 2026-03-07
**Status**: COMPLETE

---

## Master Document Index

### Architecture & Design

| Document | Path | Description |
|----------|------|-------------|
| OCI Architecture Guide | [`oci/docs/oci-architecture-guide.md`](oci-architecture-guide.md) | Complete guide: 6 Mermaid diagrams, tutorial, troubleshooting |
| OCI Architecture Overview | [`oci/README.md`](../../oci/README.md) | OCI platform architecture and setup |
| Data Architecture (Fabric) | [`fabric/docs/architecture/data-architecture.md`](../../fabric/docs/architecture/data-architecture.md) | Medallion pipeline design |
| PRD — OCI Pipeline Parity | [`oci/docs/prd-oci-pipeline-parity.md`](prd-oci-pipeline-parity.md) | Requirements for Fabric-to-OCI migration |
| Terraform IaC | [`oci/infrastructure/terraform/`](../infrastructure/terraform/) | 7 modules: network, storage, database, dataflow, datascience, cost, monitoring |

### Quality Gates & Validation

| Document | Path | Result |
|----------|------|--------|
| QG-OCI-001 (Infrastructure) | [`squads/oci-data-platform/checklists/infra-quality-gate.md`](../../squads/oci-data-platform/checklists/infra-quality-gate.md) | 38/43 PASS (5 N/A trial) |
| QG-OCI-002 (Data Pipeline) | [`squads/oci-data-platform/checklists/data-quality-gate.md`](../../squads/oci-data-platform/checklists/data-quality-gate.md) | 26/26 PASS |
| QG-OCI-003 (Model) | [`squads/oci-data-platform/checklists/model-quality-gate.md`](../../squads/oci-data-platform/checklists/model-quality-gate.md) | 25/36 PASS (11 N/A trial) |
| QG-OCI-004 (Security) | [`squads/oci-data-platform/checklists/security-checklist.md`](../../squads/oci-data-platform/checklists/security-checklist.md) | 25/29 PASS (4 N/A trial) |
| QG-OCI-005 (Operations) | [`squads/oci-data-platform/checklists/qg-oci-005-operations.md`](../../squads/oci-data-platform/checklists/qg-oci-005-operations.md) | 10/10 PASS |
| E2E Validation Report | [`oci/docs/oci-e2e-validation-report.md`](oci-e2e-validation-report.md) | PASSED |
| Quality Dashboard | [`oci/docs/QUALITY-DASHBOARD-v2.md`](QUALITY-DASHBOARD-v2.md) | All gates green |

### Operations & Monitoring

| Document | Path | Description |
|----------|------|-------------|
| Operations Runbook | [`oci/docs/operations-runbook.md`](operations-runbook.md) | Daily ops, pipeline, scoring, incident response |
| Cost Dashboard | [`oci/docs/cost-dashboard.md`](cost-dashboard.md) | R$ 171.71 acumulado / US$ 500 trial credit |
| Model Monitoring Dashboard | [`oci/docs/model-monitoring-dashboard.md`](model-monitoring-dashboard.md) | ML dashboard: ORDS/APEX live dashboard + OCI custom metrics + alerts |
| Live Dashboard (ORDS) | [Dashboard URL](https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/dashboard/) | 3 pages, Chart.js, dark theme, real-time data from ADW |
| Dashboard Setup Scripts | [`oci/infrastructure/apex/`](../infrastructure/apex/) | SQL schemas, tables, seed data, HTML dashboard, upload utility |
| OCI Custom Metrics | [`oci/model/oci_metrics.py`](../model/oci_metrics.py) | OCI Monitoring API integration (namespace: credit_risk_model) |
| Model Monitoring Code | [`oci/model/monitor_model.py`](../model/monitor_model.py) | PSI + feature drift analysis + `--publish-metrics` flag |
| Health Check | [`oci/infrastructure/ops/health-check.sh`](../infrastructure/ops/health-check.sh) | Infrastructure status verification |
| Decommissioning Checklist | [`oci/docs/decommissioning-checklist.md`](decommissioning-checklist.md) | Safe teardown procedure |

### Model & ML

| Document | Path | Description |
|----------|------|-------------|
| Training Code | [`oci/model/train_credit_risk.py`](../model/train_credit_risk.py) | Dual model training (LR L1 + LightGBM) |
| Evaluation Suite | [`oci/model/evaluate_model.py`](../model/evaluate_model.py) | Decile tables, swap analysis, PSI |
| Batch Scoring | [`oci/model/batch_scoring.py`](../model/batch_scoring.py) | Score all customers (230K records) |
| Model Catalog Registration | [`oci/model/register_model_catalog.py`](../model/register_model_catalog.py) | OCI Model Catalog integration |
| Training Results | [`oci/artifacts/metrics/training_results_20260217_214614.json`](../artifacts/metrics/training_results_20260217_214614.json) | Ground truth metrics |
| Scoring Deliverable | [`oci/deliverable/`](../deliverable/) | Docker-ready scoring package |

### Pipeline Code

| Document | Path | Description |
|----------|------|-------------|
| Bronze Ingestion | [`oci/pipeline/ingest_bronze.py`](../pipeline/ingest_bronze.py) | Raw data ingestion to Object Storage |
| Silver Transformation | [`oci/pipeline/transform_silver.py`](../pipeline/transform_silver.py) | Type casting + deduplication |
| Gold Feature Engineering | [`oci/pipeline/engineer_gold.py`](../pipeline/engineer_gold.py) | Feature store consolidation |

### Handover

| Document | Path | Description |
|----------|------|-------------|
| Transition Sign-off | [`oci/docs/transition-signoff.md`](transition-signoff.md) | Phase status, deliverables, known limitations |
| Post-Implementation Review | [`oci/docs/post-implementation-review.md`](post-implementation-review.md) | Lessons learned, what worked/didn't |
| Presentation Script | [`docs/presentation/ROTEIRO_APRESENTACAO_10MIN.md`](../../docs/presentation/ROTEIRO_APRESENTACAO_10MIN.md) | 10-minute hackathon presentation |

### Fabric Pipeline (Original)

| Document | Path | Description |
|----------|------|-------------|
| Fabric README | [`fabric/README.md`](../../fabric/README.md) | Original Fabric pipeline |
| Feature Engineering Docs | [`fabric/docs/feature-engineering/`](../../fabric/docs/feature-engineering/) | Feature books documentation |
| Model Results | [`fabric/docs/modeling/model-results.md`](../../fabric/docs/modeling/model-results.md) | Fabric model performance |
| Model Visualizations | [`fabric/docs/images/`](../../fabric/docs/images/) | Performance panels, SHAP plots |

---

## Key Metrics at a Glance

| Metric | Value |
|--------|-------|
| Data Records | 3.9M (NUM_CPF x SAFRA) |
| Features | 402 total, 59 selected |
| LightGBM KS (OOT) | 33.97% |
| AUC (OOT) | 0.7303 |
| Fabric-OCI Parity | 10/10 PASS |
| PSI | 0.0012 (stable) |
| Total OCI Cost | R$ 171.71 (BRL) / US$ 500 trial credit |
| Terraform Resources | 43 managed |
| Quality Gate Score | 124/144 PASS (100% applicable) |

---

*Package assembled: 2026-03-07*
*Validated by: OCI Platform Squad (Atlas, Neuron, Gage)*
