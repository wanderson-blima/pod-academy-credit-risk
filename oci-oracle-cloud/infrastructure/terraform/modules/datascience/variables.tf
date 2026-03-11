# Data Science Module — Variables
# ML project and notebook session

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

variable "notebook_shape" {
  description = "Shape for the notebook session VM"
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "compute_subnet_id" {
  description = "OCID of the compute subnet for the notebook session"
  type        = string
}

variable "notebook_ocpus" {
  description = "OCPUs for the notebook session (flex shape). Trial limit: 10 E4 OCPUs."
  type        = number
  default     = 10
}

variable "notebook_memory_gb" {
  description = "Memory in GB for the notebook session (flex shape). 16 GB/OCPU for E4.Flex = 160 GB at 10 OCPUs."
  type        = number
  default     = 160
}

variable "create_notebook" {
  description = "Whether to create the notebook session (set false for free tier accounts)"
  type        = bool
  default     = true
}

variable "job_ocpus" {
  description = "OCPUs for batch scoring job"
  type        = number
  default     = 4
}

variable "job_memory_gb" {
  description = "Memory in GB for batch scoring job"
  type        = number
  default     = 64
}
