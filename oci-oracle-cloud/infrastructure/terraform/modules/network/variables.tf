# Network Module — Variables
# VCN, subnets, gateways, security lists

variable "compartment_ocid" {
  description = "OCID of the compartment where network resources will be created"
  type        = string
}

variable "vcn_cidr" {
  description = "CIDR block for the VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed for SSH access to bastion subnet (restrict to VPN/office IP)"
  type        = string
  default     = "10.0.0.0/16" # VCN-only by default (no internet SSH)
}
