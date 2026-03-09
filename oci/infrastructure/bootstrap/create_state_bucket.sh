#!/bin/bash
# Bootstrap: Create Terraform state bucket (run BEFORE terraform init)
# This bucket must exist before Terraform can use it as a backend.
# Cannot be managed by Terraform itself (chicken-and-egg problem).
#
# Usage: bash create_state_bucket.sh
# Prerequisites: OCI CLI configured, COMPARTMENT_OCID set

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Error: COMPARTMENT_OCID not set}"
BUCKET_NAME="pod-academy-terraform"
NAMESPACE=$(oci os ns get --query 'data' --raw-output)

echo "=== Terraform State Bucket Bootstrap ==="
echo "Namespace: ${NAMESPACE}"
echo "Compartment: ${COMPARTMENT_OCID}"
echo ""

# Check if bucket already exists
EXISTING=$(oci os bucket get --bucket-name "${BUCKET_NAME}" 2>/dev/null && echo "yes" || echo "no")

if [ "${EXISTING}" = "yes" ]; then
    echo "[OK] Bucket '${BUCKET_NAME}' already exists."
else
    echo "Creating bucket '${BUCKET_NAME}'..."
    oci os bucket create \
        --name "${BUCKET_NAME}" \
        --compartment-id "${COMPARTMENT_OCID}" \
        --versioning Enabled \
        --public-access-type NoPublicAccess \
        --freeform-tags '{"project":"pod-academy","purpose":"terraform-state"}'

    echo "[OK] Bucket created with versioning enabled."
fi

# Verify versioning
VERSIONING=$(oci os bucket get --bucket-name "${BUCKET_NAME}" \
    --query 'data.versioning' --raw-output 2>/dev/null)
echo "Versioning: ${VERSIONING}"

echo ""
echo "=== Next Steps ==="
echo "1. Update provider.tf with the S3-compatible backend config"
echo "2. Run: terraform init -migrate-state"
echo "3. Verify: terraform state list"
echo ""
echo "Backend config for provider.tf:"
echo "  endpoint = \"https://${NAMESPACE}.compat.objectstorage.sa-saopaulo-1.oraclecloud.com\""
echo "  bucket   = \"${BUCKET_NAME}\""
