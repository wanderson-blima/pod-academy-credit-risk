# OCI Provider Configuration — Hackathon PoD Academy
# Region: sa-saopaulo-1 (Sao Paulo)

terraform {
  required_version = ">= 1.3.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }

  # Remote state backend (OCI Object Storage via S3-compatible API)
  # Uncomment after running: bash oci/infrastructure/bootstrap/create_state_bucket.sh
  # Then run: terraform init -migrate-state
  #
  # backend "s3" {
  #   bucket   = "pod-academy-terraform"
  #   key      = "dev/terraform.tfstate"
  #   region   = "sa-saopaulo-1"
  #   endpoint = "https://grlxi07jz1mo.compat.objectstorage.sa-saopaulo-1.oraclecloud.com"
  #
  #   skip_region_validation      = true
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   force_path_style            = true
  # }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
