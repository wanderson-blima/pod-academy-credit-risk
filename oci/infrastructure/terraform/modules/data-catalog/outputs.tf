# Data Catalog Module — Outputs

output "catalog_id" {
  description = "OCID of the Data Catalog"
  value       = oci_datacatalog_catalog.credit_risk.id
}
