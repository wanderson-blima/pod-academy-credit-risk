# Orchestrator Module — Compute Instance for Pipeline Orchestration
# Supports multiple shapes:
#   - VM.Standard.E4.Flex (AMD, paid, recommended for Airflow + Docker)
#   - VM.Standard.A1.Flex (ARM, Always Free, capacity-limited in sa-saopaulo-1)
#   - VM.Standard.E2.1.Micro (AMD, Always Free, 1 OCPU/1 GB, very limited)
#
# Cost strategy: Use E4.Flex during project, stop/destroy when not needed.
# Terraform recreates everything from scratch (cloud-init auto-configures).

locals {
  # Fixed shapes (no shape_config block)
  is_fixed_shape = var.orchestrator_shape == "VM.Standard.E2.1.Micro"
  # ARM shapes need ARM-specific images
  is_arm         = length(regexall("A1", var.orchestrator_shape)) > 0
}

# --- Image lookup: AMD (E4.Flex, E2.1.Micro, etc.) ---
data "oci_core_images" "oracle_linux_amd" {
  count                    = local.is_arm ? 0 : 1
  compartment_id           = var.compartment_ocid
  operating_system         = "Oracle Linux"
  operating_system_version = "8"
  shape                    = var.orchestrator_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = ["Oracle-Linux-8.*-20.*"]
    regex  = true
  }
}

# --- Image lookup: ARM (A1.Flex) ---
data "oci_core_images" "oracle_linux_arm" {
  count                    = local.is_arm ? 1 : 0
  compartment_id           = var.compartment_ocid
  operating_system         = "Oracle Linux"
  operating_system_version = "8"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"

  filter {
    name   = "display_name"
    values = ["Oracle-Linux-8.*-aarch64-.*"]
    regex  = true
  }
}

resource "oci_core_instance" "orchestrator" {
  count               = var.create_orchestrator ? 1 : 0
  compartment_id      = var.compartment_ocid
  display_name        = "${var.project_prefix}-orchestrator"
  availability_domain = var.availability_domain
  shape               = var.orchestrator_shape

  # Flex shapes need explicit OCPU/memory config; fixed shapes do not
  dynamic "shape_config" {
    for_each = local.is_fixed_shape ? [] : [1]
    content {
      ocpus         = var.orchestrator_ocpus
      memory_in_gbs = var.orchestrator_memory_gb
    }
  }

  source_details {
    source_type = "image"
    source_id   = local.is_arm ? data.oci_core_images.oracle_linux_arm[0].images[0].id : data.oci_core_images.oracle_linux_amd[0].images[0].id
  }

  create_vnic_details {
    subnet_id        = var.compute_subnet_id
    assign_public_ip = var.assign_public_ip
    display_name     = "${var.project_prefix}-orchestrator-vnic"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(file("${path.module}/../../../../infrastructure/orchestrator/cloud_init.sh"))
  }

  freeform_tags = {
    "project"     = var.project_prefix
    "environment" = var.environment
    "role"        = "orchestrator"
    "stoppable"   = "true"
  }
}
