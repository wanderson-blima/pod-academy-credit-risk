# Data Flow Module — Variables
# Spark applications and compute pool

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

variable "driver_shape" {
  description = "Shape for Data Flow driver"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "executor_shape" {
  description = "Shape for Data Flow executors"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "executor_ocpus" {
  description = "OCPUs per executor (flex shape)"
  type        = number
  default     = 1
}

variable "executor_memory_gb" {
  description = "Memory in GB per executor (flex shape)"
  type        = number
  default     = 16
}

variable "max_executors" {
  description = "Maximum number of executors in the pool"
  type        = number
  default     = 4
}

variable "num_executors" {
  description = "Number of executors for standard applications"
  type        = number
  default     = 1
}

variable "num_executors_heavy" {
  description = "Number of executors for heavy applications (gold)"
  type        = number
  default     = 2
}

variable "scripts_bucket" {
  description = "Name of the Object Storage bucket for Spark scripts"
  type        = string
}

variable "logs_bucket" {
  description = "Name of the Object Storage bucket for logs"
  type        = string
}

variable "namespace" {
  description = "Object Storage namespace"
  type        = string
}

variable "landing_bucket" {
  description = "Name of the landing bucket (source for bronze ingestion)"
  type        = string
}

variable "bronze_bucket" {
  description = "Name of the bronze bucket (target for ingestion)"
  type        = string
}

variable "use_unified_pipeline" {
  description = "Deploy unified pipeline application (single Spark job for all phases)"
  type        = bool
  default     = true
}

variable "silver_bucket" {
  description = "Name of the silver bucket"
  type        = string
  default     = ""
}

variable "gold_bucket" {
  description = "Name of the gold bucket"
  type        = string
  default     = ""
}
