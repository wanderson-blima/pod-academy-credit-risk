# Orchestrator Module — Outputs

output "instance_id" {
  description = "OCID of the orchestrator instance"
  value       = var.create_orchestrator ? oci_core_instance.orchestrator[0].id : ""
}

output "private_ip" {
  description = "Private IP of the orchestrator instance"
  value       = var.create_orchestrator ? oci_core_instance.orchestrator[0].private_ip : ""
}

output "public_ip" {
  description = "Public IP of the orchestrator instance"
  value       = var.create_orchestrator ? oci_core_instance.orchestrator[0].public_ip : ""
}
