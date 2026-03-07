# Network Module — Outputs

output "vcn_id" {
  description = "OCID of the created VCN"
  value       = oci_core_vcn.lakehouse.id
}

output "public_subnet_id" {
  description = "OCID of the public subnet"
  value       = oci_core_subnet.public.id
}

output "data_subnet_id" {
  description = "OCID of the private data subnet (ADW, Data Catalog)"
  value       = oci_core_subnet.data.id
}

output "compute_subnet_id" {
  description = "OCID of the private compute subnet (Data Flow, Data Science)"
  value       = oci_core_subnet.compute.id
}

output "nat_gateway_id" {
  description = "OCID of the NAT gateway"
  value       = oci_core_nat_gateway.natgw.id
}

output "service_gateway_id" {
  description = "OCID of the service gateway"
  value       = oci_core_service_gateway.sgw.id
}

output "adw_nsg_id" {
  description = "OCID of the NSG for ADW (defense-in-depth)"
  value       = oci_core_network_security_group.adw.id
}

output "log_group_id" {
  description = "OCID of the network log group"
  value       = oci_logging_log_group.network.id
}
