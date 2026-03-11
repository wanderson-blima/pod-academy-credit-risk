# Orchestrator Module — Variables

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

variable "compute_subnet_id" {
  description = "OCID of the subnet for the orchestrator instance"
  type        = string
}

variable "assign_public_ip" {
  description = "Whether to assign a public IP (requires public subnet)"
  type        = bool
  default     = true
}

variable "availability_domain" {
  description = "Availability domain for the instance"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key for instance access"
  type        = string
  default     = ""
}

variable "orchestrator_shape" {
  description = "Shape for the orchestrator instance. Options: VM.Standard.E4.Flex (paid, recommended), VM.Standard.A1.Flex (ARM, Always Free), VM.Standard.E2.1.Micro (AMD, Always Free, limited)"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "orchestrator_ocpus" {
  description = "OCPUs for flex shapes (ignored for fixed shapes like E2.1.Micro)"
  type        = number
  default     = 2
}

variable "orchestrator_memory_gb" {
  description = "Memory in GB for flex shapes (ignored for fixed shapes like E2.1.Micro)"
  type        = number
  default     = 16
}

variable "create_orchestrator" {
  description = "Whether to create the orchestrator instance"
  type        = bool
  default     = true
}
