# Root Outputs — OCI Data Lakehouse
# Key outputs from all modules

# ─── Network ────────────────────────────────────────────────────────────────

output "vcn_id" {
  description = "OCID of the VCN"
  value       = module.network.vcn_id
}

output "data_subnet_id" {
  description = "OCID of the private data subnet"
  value       = module.network.data_subnet_id
}

output "compute_subnet_id" {
  description = "OCID of the private compute subnet"
  value       = module.network.compute_subnet_id
}

# ─── Storage ────────────────────────────────────────────────────────────────

output "bucket_names" {
  description = "Map of all bucket names by layer"
  value       = module.storage.bucket_names
}

output "storage_namespace" {
  description = "Object Storage namespace"
  value       = module.storage.namespace
}

# ─── Database ───────────────────────────────────────────────────────────────

output "adw_id" {
  description = "OCID of the Autonomous Data Warehouse"
  value       = module.database.adw_id
}

output "adw_db_name" {
  description = "Database name of the ADW instance"
  value       = module.database.adw_db_name
}

output "adw_admin_password" {
  description = "Generated admin password for ADW (sensitive)"
  value       = random_password.adw_admin.result
  sensitive   = true
}

# ─── Data Flow ──────────────────────────────────────────────────────────────

output "dataflow_pool_id" {
  description = "OCID of the Data Flow pool"
  value       = module.dataflow.pool_id
}

output "dataflow_ingest_bronze_app_id" {
  description = "OCID of the bronze ingestion Data Flow application"
  value       = module.dataflow.ingest_bronze_app_id
}

output "dataflow_transform_silver_app_id" {
  description = "OCID of the silver transformation Data Flow application"
  value       = module.dataflow.transform_silver_app_id
}

output "dataflow_engineer_gold_app_id" {
  description = "OCID of the gold feature engineering Data Flow application"
  value       = module.dataflow.engineer_gold_app_id
}

# ─── Data Science ────────────────────────────────────────────────────────────

output "datascience_project_id" {
  description = "OCID of the Data Science project"
  value       = module.datascience.project_id
}

output "notebook_session_id" {
  description = "OCID of the notebook session"
  value       = module.datascience.notebook_session_id
}

output "notebook_session_url" {
  description = "URL of the notebook session"
  value       = module.datascience.notebook_session_url
}

# ─── Cost Management ────────────────────────────────────────────────────────

output "budget_id" {
  description = "OCID of the budget"
  value       = module.cost.budget_id
}

# ─── Orchestrator ─────────────────────────────────────────────────────────

output "orchestrator_instance_id" {
  description = "OCID of the orchestrator instance"
  value       = module.orchestrator.instance_id
}

output "orchestrator_private_ip" {
  description = "Private IP of the orchestrator"
  value       = module.orchestrator.private_ip
}

output "orchestrator_public_ip" {
  description = "Public IP of the orchestrator (Airflow UI: http://<ip>:8080)"
  value       = module.orchestrator.public_ip
}

# ─── Data Catalog ──────────────────────────────────────────────────────────

output "data_catalog_id" {
  description = "OCID of the Data Catalog"
  value       = module.data_catalog.catalog_id
}
