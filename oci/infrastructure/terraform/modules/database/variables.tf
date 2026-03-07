# Database Module — Variables
# Autonomous Data Warehouse (ADW) Serverless

variable "compartment_ocid" {
  description = "OCID of the compartment where ADW will be created"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment label for tagging"
  type        = string
  default     = "dev"
}

variable "adw_ecpu_count" {
  description = "Number of ECPUs for ADW (minimum 2)"
  type        = number
  default     = 2
}

variable "adw_admin_password" {
  description = "Admin password for ADW"
  type        = string
  sensitive   = true
}

variable "use_free_tier" {
  description = "Whether to use Always Free tier for ADW"
  type        = bool
  default     = false
}

variable "data_subnet_id" {
  description = "OCID of the private data subnet for ADW private endpoint"
  type        = string
}

variable "adw_nsg_ids" {
  description = "List of NSG OCIDs to attach to the ADW instance"
  type        = list(string)
  default     = []
}
