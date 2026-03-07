# Storage Module — Variables
# Object Storage buckets for the data lakehouse

variable "compartment_ocid" {
  description = "OCID of the compartment where buckets will be created"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for bucket names (e.g. pod-academy)"
  type        = string
}

variable "environment" {
  description = "Environment label for tagging (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "kms_key_id" {
  description = "OCID of the KMS key for customer-managed encryption (empty string = Oracle-managed)"
  type        = string
  default     = ""
}
