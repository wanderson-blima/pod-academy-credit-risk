# Root Variables — OCI Data Lakehouse
# All top-level variables with defaults where applicable

# ─── OCI Provider Credentials ───────────────────────────────────────────────

variable "tenancy_ocid" {
  description = "OCID of the OCI tenancy"
  type        = string
}

variable "user_ocid" {
  description = "OCID of the OCI user for API authentication"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint of the API signing key"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API private key PEM file"
  type        = string
}

variable "region" {
  description = "OCI region identifier"
  type        = string
  default     = "sa-saopaulo-1"
}

# ─── Project ────────────────────────────────────────────────────────────────

variable "compartment_ocid" {
  description = "OCID of the compartment for all resources"
  type        = string
}

variable "namespace" {
  description = "Object Storage namespace"
  type        = string
}

variable "prefix" {
  description = "Project prefix for naming resources"
  type        = string
  default     = "pod-academy"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# ─── Network ────────────────────────────────────────────────────────────────

variable "vcn_cidr" {
  description = "CIDR block for the VCN"
  type        = string
  default     = "10.0.0.0/16"
}

# ─── Database (ADW) ─────────────────────────────────────────────────────────

variable "adw_ecpu_count" {
  description = "Number of ECPUs for Autonomous Data Warehouse (minimum 2)"
  type        = number
  default     = 2
}

variable "use_free_tier" {
  description = "Whether to use Always Free tier for ADW"
  type        = bool
  default     = false
}

# ─── Data Flow ───────────────────────────────────────────────────────────────

variable "driver_shape" {
  description = "Shape for Data Flow driver nodes"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "executor_shape" {
  description = "Shape for Data Flow executor nodes"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "executor_ocpus" {
  description = "OCPUs per Data Flow executor (flex shape)"
  type        = number
  default     = 1
}

variable "executor_memory_gb" {
  description = "Memory in GB per Data Flow executor (flex shape)"
  type        = number
  default     = 16
}

variable "max_executors" {
  description = "Maximum number of executors in the Data Flow pool"
  type        = number
  default     = 4
}

variable "num_executors" {
  description = "Number of executors for standard Data Flow applications"
  type        = number
  default     = 1
}

variable "num_executors_heavy" {
  description = "Number of executors for heavy Data Flow applications (gold)"
  type        = number
  default     = 2
}

# ─── Data Science ────────────────────────────────────────────────────────────

variable "notebook_shape" {
  description = "Shape for the Data Science notebook session"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "notebook_ocpus" {
  description = "OCPUs for the notebook session (flex shape). Trial limit: 10 E4 OCPUs."
  type        = number
  default     = 10
}

variable "notebook_memory_gb" {
  description = "Memory in GB for the notebook session. 16 GB/OCPU for E4.Flex = 160 GB at 10 OCPUs."
  type        = number
  default     = 160
}

# ─── Cost Management ────────────────────────────────────────────────────────

variable "monthly_budget" {
  description = "Monthly budget alert amount in BRL (monitoring alert, not trial limit). Trial credit: US$ 500."
  type        = number
  default     = 500
}

variable "alert_recipients" {
  description = "Email address(es) for budget alert notifications"
  type        = string
  default     = "wandersonlima20@gmail.com"
}

# ─── Security ──────────────────────────────────────────────────────────────

variable "ssh_allowed_cidr" {
  description = "CIDR allowed for SSH on bastion subnet (default: VCN-only, no internet SSH)"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_vault" {
  description = "Create OCI Vault and CMK for customer-managed encryption (costs per key version)"
  type        = bool
  default     = true
}

# ─── Orchestrator ─────────────────────────────────────────────────────────

variable "availability_domain" {
  description = "Availability domain for compute instances"
  type        = string
  default     = "TjOZ:SA-SAOPAULO-1-AD-1"
}

variable "ssh_public_key" {
  description = "SSH public key for compute instances"
  type        = string
  default     = ""
}

variable "orchestrator_shape" {
  description = "Shape for the orchestrator instance. VM.Standard.E4.Flex (paid, recommended) or VM.Standard.E2.1.Micro (Always Free, limited)"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "orchestrator_ocpus" {
  description = "OCPUs for orchestrator flex shapes"
  type        = number
  default     = 2
}

variable "orchestrator_memory_gb" {
  description = "Memory in GB for orchestrator flex shapes"
  type        = number
  default     = 16
}

variable "create_orchestrator" {
  description = "Whether to create the orchestrator instance"
  type        = bool
  default     = true
}
