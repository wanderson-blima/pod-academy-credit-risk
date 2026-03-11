# Database Module — Outputs

output "adw_id" {
  description = "OCID of the Autonomous Data Warehouse"
  value       = oci_database_autonomous_database.adw.id
}

output "adw_db_name" {
  description = "Database name of the ADW instance"
  value       = oci_database_autonomous_database.adw.db_name
}

output "adw_connection_urls" {
  description = "Connection URLs for the ADW instance"
  value       = oci_database_autonomous_database.adw.connection_urls
}
