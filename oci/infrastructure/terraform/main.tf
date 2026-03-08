# Root Configuration — OCI Data Lakehouse
# Orchestrates all modules: network, storage, database, dataflow, datascience, cost
#
# Usage:
#   cd infra/
#   terraform init
#   terraform plan
#   terraform apply
#
# Architecture:
#   Network  -->  Storage (independent)
#              |-> Database (needs data_subnet_id from network)
#              |-> Data Flow (needs bucket names from storage)
#              |-> Data Science (needs compute_subnet_id from network)
#              |-> Cost (independent — tenancy-level)

# ─── Random Password for ADW Admin ──────────────────────────────────────────

resource "random_password" "adw_admin" {
  length           = 20
  special          = true
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "#$%&*()-_=+[]{}|:,.<>?"
}

# ─── Module: Network ────────────────────────────────────────────────────────

module "network" {
  source = "./modules/network"

  compartment_ocid = var.compartment_ocid
  vcn_cidr         = var.vcn_cidr
  ssh_allowed_cidr = var.ssh_allowed_cidr
}

# ─── OCI Vault & CMK (Customer-Managed Encryption Key) ─────────────────────

resource "oci_kms_vault" "lakehouse" {
  count          = var.enable_vault ? 1 : 0
  compartment_id = var.compartment_ocid
  display_name   = "${var.prefix}-vault"
  vault_type     = "DEFAULT"
}

resource "oci_kms_key" "data_key" {
  count              = var.enable_vault ? 1 : 0
  compartment_id     = var.compartment_ocid
  display_name       = "${var.prefix}-data-key"
  management_endpoint = oci_kms_vault.lakehouse[0].management_endpoint

  key_shape {
    algorithm = "AES"
    length    = 32
  }

  protection_mode = "SOFTWARE"
}

# ─── Module: Storage ────────────────────────────────────────────────────────

module "storage" {
  source = "./modules/storage"

  compartment_ocid = var.compartment_ocid
  project_prefix   = var.prefix
  environment      = var.environment
  kms_key_id       = var.enable_vault ? oci_kms_key.data_key[0].id : ""
}

# ─── Module: Database (ADW) ─────────────────────────────────────────────────

module "database" {
  source = "./modules/database"

  compartment_ocid   = var.compartment_ocid
  project_prefix     = var.prefix
  environment        = var.environment
  adw_ecpu_count     = var.adw_ecpu_count
  adw_admin_password = random_password.adw_admin.result
  use_free_tier      = var.use_free_tier
  data_subnet_id     = module.network.data_subnet_id
  adw_nsg_ids        = [module.network.adw_nsg_id]

  depends_on = [module.network]
}

# ─── Module: Data Flow ──────────────────────────────────────────────────────

module "dataflow" {
  source = "./modules/dataflow"

  compartment_ocid    = var.compartment_ocid
  project_prefix      = var.prefix
  environment         = var.environment
  driver_shape        = var.driver_shape
  executor_shape      = var.executor_shape
  executor_ocpus      = var.executor_ocpus
  executor_memory_gb  = var.executor_memory_gb
  max_executors       = var.max_executors
  num_executors       = var.num_executors
  num_executors_heavy = var.num_executors_heavy
  scripts_bucket      = module.storage.scripts_bucket
  logs_bucket         = module.storage.logs_bucket
  namespace           = var.namespace
  landing_bucket      = module.storage.landing_bucket
  bronze_bucket       = module.storage.bronze_bucket

  depends_on = [module.storage]
}

# ─── Module: Data Science ───────────────────────────────────────────────────

module "datascience" {
  source = "./modules/datascience"

  compartment_ocid  = var.compartment_ocid
  project_prefix    = var.prefix
  environment       = var.environment
  notebook_shape    = var.notebook_shape
  compute_subnet_id = module.network.compute_subnet_id
  notebook_ocpus    = var.notebook_ocpus
  notebook_memory_gb = var.notebook_memory_gb
  create_notebook    = true   # Enabled: Data Science has separate trial limits (24 OCPUs E4, 384 GB).

  depends_on = [module.network]
}

# ─── Module: Cost Management ────────────────────────────────────────────────

module "cost" {
  source = "./modules/cost"

  tenancy_ocid     = var.tenancy_ocid
  compartment_ocid = var.compartment_ocid
  project_prefix   = var.prefix
  monthly_budget   = var.monthly_budget
  alert_recipients = var.alert_recipients
}

# ─── Module: Monitoring ────────────────────────────────────────────────────

module "monitoring" {
  source = "./modules/monitoring"

  compartment_ocid = var.compartment_ocid
  project_prefix   = var.prefix
  alert_email      = var.alert_recipients
}

# ─── IAM: Dynamic Groups ──────────────────────────────────────────────────

resource "oci_identity_dynamic_group" "dataflow" {
  compartment_id = var.tenancy_ocid
  name           = "${var.prefix}-dataflow-dg"
  description    = "Dynamic group for Data Flow runs in lakehouse compartment"
  matching_rule  = "ALL {resource.type='dataflowrun', resource.compartment.id='${var.compartment_ocid}'}"
}

resource "oci_identity_dynamic_group" "datascience" {
  compartment_id = var.tenancy_ocid
  name           = "${var.prefix}-datascience-dg"
  description    = "Dynamic group for Data Science resources in lakehouse compartment"
  matching_rule  = "ANY {resource.type='datasciencenotebooksession', resource.type='datasciencemodeldeployment', resource.type='datasciencejobrun'}"
}

# ─── IAM: Least-Privilege Policies ────────────────────────────────────────

resource "oci_identity_policy" "dataflow_policy" {
  compartment_id = var.compartment_ocid
  name           = "${var.prefix}-dataflow-policy"
  description    = "Least-privilege policy for Data Flow to access Object Storage"
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.dataflow.name} to read objectstorage-namespaces in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.dataflow.name} to manage objects in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.dataflow.name} to read buckets in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.dataflow.name} to use dataflow-family in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.dataflow.name} to use virtual-network-family in compartment id ${var.compartment_ocid}",
  ]
}

resource "oci_identity_policy" "datascience_policy" {
  compartment_id = var.compartment_ocid
  name           = "${var.prefix}-datascience-policy"
  description    = "Least-privilege policy for Data Science notebook and model deployment"
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to use virtual-network-family in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to manage data-science-family in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to manage objects in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to read buckets in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to use log-groups in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group ${oci_identity_dynamic_group.datascience.name} to use log-content in compartment id ${var.compartment_ocid}",
  ]
}

resource "oci_identity_policy" "service_policy" {
  compartment_id = var.tenancy_ocid
  name           = "${var.prefix}-service-policy"
  description    = "Service-level policy for OCI Data Flow and Data Science"
  statements = [
    "Allow service dataflow to read objects in compartment id ${var.compartment_ocid}",
    "Allow service datascience to use virtual-network-family in compartment id ${var.compartment_ocid}",
    "Allow service objectstorage-${var.region} to use keys in compartment id ${var.compartment_ocid}",
  ]
}
