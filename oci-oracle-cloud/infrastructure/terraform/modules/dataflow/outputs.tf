# Data Flow Module — Outputs

output "pool_id" {
  description = "OCID of the Data Flow pool"
  value       = oci_dataflow_pool.dev.id
}

output "ingest_bronze_app_id" {
  description = "OCID of the bronze ingestion application"
  value       = oci_dataflow_application.ingest_bronze.id
}

output "transform_silver_app_id" {
  description = "OCID of the silver transformation application"
  value       = oci_dataflow_application.transform_silver.id
}

output "engineer_gold_app_id" {
  description = "OCID of the gold feature engineering application"
  value       = oci_dataflow_application.engineer_gold.id
}

output "unified_pipeline_app_id" {
  description = "OCID of the unified pipeline application"
  value       = var.use_unified_pipeline ? oci_dataflow_application.unified_pipeline[0].id : ""
}
