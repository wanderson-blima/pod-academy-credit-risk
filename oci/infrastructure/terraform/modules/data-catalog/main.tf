# Data Catalog Module — Schema Harvesting & Data Lineage
# Enables automatic metadata discovery from Object Storage buckets

resource "oci_datacatalog_catalog" "credit_risk" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.project_prefix}-data-catalog"

  freeform_tags = {
    "project"     = var.project_prefix
    "environment" = var.environment
  }
}
