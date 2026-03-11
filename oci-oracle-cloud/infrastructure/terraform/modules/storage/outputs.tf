# Storage Module — Outputs

output "bucket_names" {
  description = "Map of bucket layer to bucket name"
  value       = { for k, v in oci_objectstorage_bucket.lakehouse : k => v.name }
}

output "bucket_ids" {
  description = "Map of bucket layer to bucket OCID (namespace/name)"
  value       = { for k, v in oci_objectstorage_bucket.lakehouse : k => v.name }
}

output "namespace" {
  description = "Object Storage namespace"
  value       = data.oci_objectstorage_namespace.ns.namespace
}

output "landing_bucket" {
  description = "Name of the landing bucket"
  value       = oci_objectstorage_bucket.lakehouse["landing"].name
}

output "bronze_bucket" {
  description = "Name of the bronze bucket"
  value       = oci_objectstorage_bucket.lakehouse["bronze"].name
}

output "silver_bucket" {
  description = "Name of the silver bucket"
  value       = oci_objectstorage_bucket.lakehouse["silver"].name
}

output "gold_bucket" {
  description = "Name of the gold bucket"
  value       = oci_objectstorage_bucket.lakehouse["gold"].name
}

output "logs_bucket" {
  description = "Name of the logs bucket"
  value       = oci_objectstorage_bucket.lakehouse["logs"].name
}

output "scripts_bucket" {
  description = "Name of the scripts bucket"
  value       = oci_objectstorage_bucket.lakehouse["scripts"].name
}
