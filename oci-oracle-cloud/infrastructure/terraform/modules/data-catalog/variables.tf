# Data Catalog Module — Variables

variable "compartment_ocid" {
  description = "OCID of the compartment"
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
