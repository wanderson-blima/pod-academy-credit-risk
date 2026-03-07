# OCI Data Platform Knowledge Base

## Service Reference

### OCI Data Flow (Managed Spark)
- Fully managed Apache Spark 3.5.0
- Languages: Python (PySpark), Scala, Java
- Modes: Batch, Streaming, Interactive
- Pricing: Per OCPU-hour while jobs run (zero idle cost)
- Pools: Pre-allocated compute, idle timeout, min=0 for scale-to-zero
- Max session duration: 7 days (10,080 minutes)
- URI pattern: `oci://{bucket}@{namespace}/{path}`

### OCI Object Storage
| Tier | Access | Min Retention | Retrieval |
|------|--------|---------------|-----------|
| Standard | Immediate | None | Free |
| Infrequent Access | Immediate | 31 days | Per-GB fee |
| Archive | Restore (hours) | 90 days | Per-GB fee + restore time |

- Auto-tiering: moves to Infrequent after 31 days inactive (objects >1 MiB)
- Lifecycle rules: up to 1,000 per bucket
- Versioning: available per bucket

### Autonomous Data Warehouse (ADW)
- Serverless: auto-scale up to 3x, stop/start, per-second billing
- Minimum: 2 ECPUs (or 1 ECPU with Free Tier)
- Stopped: zero CPU cost, storage-only billing
- External tables: query Object Storage via DBMS_CLOUD
- In-database ML: Oracle Machine Learning (OML)

### OCI Data Science
- Notebook Sessions: JupyterLab (CPU/GPU), billed per hour while active
- Jobs: batch execution without persistent compute
- Pipelines: multi-step ML orchestration
- Model Catalog: versioned registry with artifacts
- Model Deployment: real-time REST endpoints
- ADS SDK: Python interface to all services
- Conda environments: managed library environments

### OCI Data Catalog
- Metadata management for discovery and governance
- Harvests from ADW and Object Storage
- Business glossary and asset inventory
- Common metastore for Data Flow Spark

### OCI Vault
- Secrets management with AES-256 encryption
- Integration: ADW, Object Storage, Data Flow
- Types: DEFAULT (shared) or VIRTUAL_PRIVATE
- Resources: Vault → Key → Secret

## Terraform Resource Quick Reference

| Service | Resource Type |
|---------|--------------|
| VCN | `oci_core_vcn` |
| Subnet | `oci_core_subnet` |
| Internet GW | `oci_core_internet_gateway` |
| NAT GW | `oci_core_nat_gateway` |
| Service GW | `oci_core_service_gateway` |
| Route Table | `oci_core_route_table` |
| Security List | `oci_core_security_list` |
| Bucket | `oci_objectstorage_bucket` |
| ADW | `oci_database_autonomous_database` |
| Data Flow App | `oci_dataflow_application` |
| Data Flow Pool | `oci_dataflow_pool` |
| DS Project | `oci_datascience_project` |
| DS Notebook | `oci_datascience_notebook_session` |
| DS Model | `oci_datascience_model` |
| DS Deploy | `oci_datascience_model_deployment` |
| Data Catalog | `oci_datacatalog_catalog` |
| Vault | `oci_kms_vault` |
| Key | `oci_kms_key` |
| Secret | `oci_vault_secret` |
| Budget | `oci_budget_budget` |
| Alert Rule | `oci_budget_alert_rule` |
| Compartment | `oci_identity_compartment` |
| Policy | `oci_identity_policy` |
| Dynamic Group | `oci_identity_dynamic_group` |

## Key GitHub Repositories

| Repository | Purpose |
|-----------|---------|
| [terraform-oci-lakehouse](https://github.com/oracle-devrel/terraform-oci-lakehouse) | ADW + Object Storage + Data Catalog module |
| [terraform-oci-arch-data-flow](https://github.com/oracle-devrel/terraform-oci-arch-data-flow) | Data Flow + buckets + IAM module |
| [terraform-oci-open-lz](https://github.com/oracle-quickstart/terraform-oci-open-lz) | Landing zone blueprints |
| [oci-cis-landingzone-quickstart](https://github.com/oci-landing-zones/oci-cis-landingzone-quickstart) | CIS security baseline |
| [oci-data-science-ai-samples](https://github.com/oracle-samples/oci-data-science-ai-samples) | ML training/deploy samples |
| [oracle-dataflow-samples](https://github.com/oracle-samples/oracle-dataflow-samples) | PySpark samples (CSV→Parquet, ADW) |
| [terraform-provider-oci](https://github.com/oracle/terraform-provider-oci) | Official Terraform provider |

## Fabric → OCI Migration Mapping

| Microsoft Fabric | OCI Equivalent |
|-----------------|----------------|
| Lakehouse (Bronze) | Object Storage bucket: `{prefix}-bronze` |
| Lakehouse (Silver) | Object Storage bucket: `{prefix}-silver` |
| Lakehouse (Gold) | Object Storage bucket: `{prefix}-gold` |
| Delta Lake format | Parquet (partitioned) |
| Spark Notebooks | OCI Data Flow (PySpark applications) |
| notebookutils | OCI CLI / ADS SDK |
| MLflow experiment | OCI Data Science Model Catalog |
| MLflow model registry | OCI Model Catalog |
| Workspace | OCI Compartment |
| OneLake path | `oci://{bucket}@{namespace}/{path}` |
| MERGE INTO (Delta) | Read + dedup + overwrite partition |
| Fabric pipeline | OCI Data Integration / Functions + Events |

## OCI Region: São Paulo

- Region name: `sa-saopaulo-1`
- Region key: `GRU`
- Availability Domains: 1 (AD-1)
- Fault Domains: 3 per AD

## Additional Terraform Resources

| Resource | Purpose |
|----------|---------|
| `oci_resource_scheduler_schedule` | Auto start/stop compute/ADW on CRON schedule |
| [terraform-oci-oracle-cloud-foundation](https://github.com/oracle-devrel/terraform-oci-oracle-cloud-foundation) | Comprehensive module framework (includes Data Lakehouse RM zip) |
| [oci-lakehouse (quickstart)](https://github.com/oracle-quickstart/oci-lakehouse) | Resource Manager stack for full lakehouse |
| [terraform-oci-oke](https://github.com/oracle-terraform-modules/terraform-oci-oke) | OKE (Kubernetes) module |
| [terraform-oci-vcn](https://github.com/oracle-terraform-modules/terraform-oci-vcn) | Reusable VCN module |
| [oci-mlflow](https://github.com/oracle/oci-mlflow) | MLflow plugin for OCI integration |
| [oci-python-sdk](https://github.com/oracle/oci-python-sdk) | Official Python SDK |

## Terraform State Management

### OCI Native Backend (Recommended)
```hcl
terraform {
  backend "oci" {
    bucket    = "terraform-state"
    namespace = "your_namespace"
    prefix    = "project/env"
    region    = "sa-saopaulo-1"
  }
}
```
- Built-in state locking via optimistic concurrency (no DynamoDB needed)
- Enable bucket versioning for state recovery
- Alternative: OCI Resource Manager (managed Terraform-as-a-Service)

## OCI Resource Scheduler (Auto Start/Stop)

```hcl
resource "oci_resource_scheduler_schedule" "dev_stop" {
  compartment_id     = var.compartment_id
  action             = "STOP"
  recurrence_details = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=20"
  recurrence_type    = "ICAL"
  resources { id = var.adw_id }
}

resource "oci_resource_scheduler_schedule" "dev_start" {
  compartment_id     = var.compartment_id
  action             = "START"
  recurrence_details = "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=08"
  recurrence_type    = "ICAL"
  resources { id = var.adw_id }
}
```
- Up to 25 resources per schedule
- Supports: Compute, Instance Pools, ADW, Functions

## GitHub Organizations to Watch

| Organization | Focus |
|-------------|-------|
| [oracle](https://github.com/oracle) | Core SDKs, providers, ADS |
| [oracle-samples](https://github.com/oracle-samples) | Data Science AI samples, Data Flow samples |
| [oracle-quickstart](https://github.com/oracle-quickstart) | Resource Manager stacks, QuickStart architectures |
| [oracle-devrel](https://github.com/oracle-devrel) | Developer Relations — Terraform arch modules |
| [oracle-terraform-modules](https://github.com/oracle-terraform-modules) | Reusable Terraform modules (OKE, VCN, compute) |
| [oci-landing-zones](https://github.com/oci-landing-zones) | Enterprise landing zones, CIS benchmarks |

## Expert References

| Expert | Focus | Resource |
|--------|-------|----------|
| Pradeep Vincent | Chief Technical Architect & EVP, OCI | Founding engineer of OCI |
| David Allan | Data Intelligence Platform Architect | dave-allan-us.medium.com (Data Integration, Data Flow) |
| Ali Mukadam | Oracle Developer Relations | Terraform modules, OKE patterns |
| Mark Rittman | Data Engineering, OCI Analytics | rittmanmead.com/blog |
| Lucas Jellema | OCI Development, Data Integration | blogs.oracle.com |
| Prasenjit Sarkar | OCI Architecture | "OCI for Solutions Architects" (Packt) |
| Roopesh Ramklass | OCI Architect, OCP/OCM | "OCI Architect All-in-One Exam Guide" |
| Oracle A-Team | Architecture best practices | ateam-oracle.com |
| OCI Architecture Center | Reference designs | oracle.com/cloud/architecture-center |

## Recommended Tools & Integrations

### MCP Servers (Agent Enhancement)

| MCP Server | Purpose | Agent |
|-----------|---------|-------|
| [terraform-mcp-server](https://github.com/hashicorp/terraform-mcp-server) | Terraform Registry docs, module discovery | infra-architect |
| [mcp-server-oci](https://github.com/jopsis/mcp-server-oci) | 85 tools for OCI resource management | infra-architect |
| [oracle-sqlcl-mcp](https://github.com/oracle/mcp) | Native MCP access to Oracle Database | data-engineer |

### Security & Compliance CLI Tools

| Tool | Purpose | Agent |
|------|---------|-------|
| [Steampipe + OCI Plugin](https://hub.steampipe.io/plugins/turbot/oci) | SQL-based OCI resource querying | security-engineer |
| [Powerpipe OCI Compliance](https://hub.powerpipe.io/mods/turbot/steampipe-mod-oci-compliance) | CIS OCI Foundations v3.0 dashboards | security-engineer |
| [Checkov](https://www.checkov.io/) | Static analysis for Terraform | infra-architect |

### ML Enhancement Libraries

| Library | Purpose | Agent |
|---------|---------|-------|
| [Evidently AI](https://github.com/evidentlyai/evidently) | Data drift + model monitoring (100+ metrics) | ml-engineer |
| [SHAP](https://github.com/shap/shap) | Model explainability (Shapley values) | ml-engineer |
| [Optuna](https://github.com/optuna/optuna) | Hyperparameter optimization (native LightGBM) | ml-engineer |
| [oci-mlflow](https://github.com/oracle/oci-mlflow) | MLflow plugin for OCI Model Catalog | ml-engineer |

### Data Quality Libraries

| Library | Purpose | Agent |
|---------|---------|-------|
| [Pandera](https://pandera.readthedocs.io/en/stable/pyspark_sql.html) | PySpark schema validation | data-engineer |
| [Great Expectations](https://github.com/great-expectations/great_expectations) | Data quality validation framework | data-engineer |

### OCI APIs for Automation

| API | Purpose | Agent |
|-----|---------|-------|
| OCI Usage API | Cost/usage data with filters and reports | cloud-ops |
| OCI Monitoring API | Metric queries, alarms, custom metrics | infra-architect |
| OCI Vault API | Secrets rotation, key management | security-engineer |
| OCI Data Catalog API | Metadata governance, data lineage | data-engineer |

## Model Routing (*optimize Analysis — 2026-02-15)

**Philosophy:** All Opus — maximum quality for first OCI execution.

| Component | Model | Rationale |
|-----------|-------|-----------|
| Orchestrator (oci-chief) | **Opus** | Planning and coordination |
| All 13 tasks | **Opus** | First execution — zero margin for error |

**Future optimization:** After first successful OCI run, downgrade 10 SHOULD_BE_WORKER tasks to Haiku (93.5% det → safe). Potential savings: $340/year.

### Determinism Analysis (153 atomic actions)

| Task | Det% | Classification | Actions |
|------|------|---------------|---------|
| deploy-network | 100% | SHOULD_BE_WORKER | 10/10 pure Terraform |
| deploy-storage | 100% | SHOULD_BE_WORKER | 9/9 pure Terraform |
| deploy-database | 100% | SHOULD_BE_WORKER | 9/9 Terraform + SQL |
| deploy-dataflow | 100% | SHOULD_BE_WORKER | 9/9 Terraform + CLI |
| deploy-datascience | 100% | SHOULD_BE_WORKER | 10/10 Terraform + conda |
| ingest-bronze | 100% | SHOULD_BE_WORKER | 8/8 PySpark |
| transform-silver | 100% | SHOULD_BE_WORKER | 10/10 PySpark config-driven |
| engineer-gold | 100% | SHOULD_BE_WORKER | 13/13 PySpark joins |
| train-model | 100% | SHOULD_BE_WORKER | 14/14 fixed hyperparams |
| manage-costs | 100% | SHOULD_BE_WORKER | 13/13 CLI + Terraform |
| deploy-model | 90% | COULD_BE_WORKER | 9/10 (score distribution = Agent) |
| destroy-infra | 80% | COULD_BE_WORKER | 8/10 (human confirms destroy) |
| setup-oci-cli | 75% | COULD_BE_WORKER | 6/8 (browser upload = Human) |

### Token Economy

| Metric | Current (All Opus) | Future (after validation) | Potential Savings |
|--------|--------------------|---------------------------|-------------------|
| Cost/execution | $0.137 avg | $0.028 avg (11H+2O) | 79.7% |
| Monthly (20 exec) | $35.62 | $7.24 | $28.38 |
| Annual | $427.44 | $86.88 | $340.56 |

*Haiku optimization deferred until tasks validated on OCI.*

## Reference Architectures (Official Oracle)

- [Data platform - data lakehouse](https://docs.oracle.com/en/solutions/data-platform-lakehouse/index.html)
- [Deploy open-source data lakehouse on OCI](https://docs.oracle.com/en/solutions/oci-open-source-lakehouse/index.html)
- [OCI Architecture Center - Lakehouse](https://docs.oracle.com/solutions/?q=lakehouse)
- [OCI FinOps Hub](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/FinOps.htm)
- [ADS SDK Documentation](https://accelerated-data-science.readthedocs.io/)
