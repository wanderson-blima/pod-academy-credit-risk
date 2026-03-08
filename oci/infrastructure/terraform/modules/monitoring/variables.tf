variable "compartment_ocid" {
  description = "OCID of the compartment for monitoring resources"
  type        = string
}

variable "project_prefix" {
  description = "Project prefix for naming resources"
  type        = string
}

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
}
