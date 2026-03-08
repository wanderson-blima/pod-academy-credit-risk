# Cost Module — Variables
# Budget and alert rules

variable "tenancy_ocid" {
  description = "OCID of the tenancy (budgets are tenancy-level resources)"
  type        = string
}

variable "compartment_ocid" {
  description = "OCID of the target compartment to monitor"
  type        = string
}

variable "project_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "monthly_budget" {
  description = "Monthly budget alert amount in BRL (monitoring alert, not trial limit). Trial credit: US$ 500."
  type        = number
  default     = 500
}

variable "alert_recipients" {
  description = "Email address(es) for budget alert notifications"
  type        = string
}
