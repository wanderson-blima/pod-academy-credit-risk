#!/bin/bash
# Data Catalog Harvesting — Create assets and run harvest jobs
# Discovers schemas from Object Storage Parquet files
#
# Usage: bash harvest-catalog.sh
# Prerequisites: COMPARTMENT_OCID, Data Catalog created via Terraform

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Error: COMPARTMENT_OCID not set}"
NAMESPACE="${OCI_NAMESPACE:-grlxi07jz1mo}"
PREFIX="${PREFIX:-pod-academy}"

echo "=== OCI Data Catalog Harvesting ==="
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Find the catalog
CATALOG_OCID=$(oci data-catalog catalog list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --query "data.items[?contains(\"display-name\",'${PREFIX}')].id | [0]" \
    --raw-output 2>/dev/null)

if [ -z "${CATALOG_OCID}" ] || [ "${CATALOG_OCID}" = "null" ]; then
    echo "[ERROR] Data Catalog not found. Run terraform apply first."
    exit 1
fi
echo "Catalog: ${CATALOG_OCID}"

# Create data assets for each medallion layer
for LAYER in bronze silver gold; do
    BUCKET_NAME="${PREFIX}-${LAYER}"
    ASSET_NAME="${LAYER}-object-storage"

    echo ""
    echo "--- Creating data asset: ${ASSET_NAME} ---"

    # Check if asset already exists
    EXISTING=$(oci data-catalog data-asset list \
        --catalog-id "${CATALOG_OCID}" \
        --display-name "${ASSET_NAME}" \
        --query 'data.items[0].key' \
        --raw-output 2>/dev/null)

    if [ -n "${EXISTING}" ] && [ "${EXISTING}" != "null" ]; then
        echo "  Asset already exists: ${EXISTING}"
        ASSET_KEY="${EXISTING}"
    else
        ASSET_RESPONSE=$(oci data-catalog data-asset create \
            --catalog-id "${CATALOG_OCID}" \
            --display-name "${ASSET_NAME}" \
            --type-key "oracle_object_storage" \
            --properties "{\"default.namespace\":\"${NAMESPACE}\",\"default.url\":\"https://objectstorage.sa-saopaulo-1.oraclecloud.com\"}" \
            2>/dev/null)
        ASSET_KEY=$(echo "${ASSET_RESPONSE}" | jq -r '.data.key // empty')
        echo "  Created: ${ASSET_KEY}"
    fi

    # Create harvest job
    if [ -n "${ASSET_KEY}" ] && [ "${ASSET_KEY}" != "null" ]; then
        echo "  Creating harvest job for ${LAYER}..."
        oci data-catalog job create \
            --catalog-id "${CATALOG_OCID}" \
            --job-type "HARVEST" \
            --display-name "harvest-${LAYER}-$(date +%Y%m%d)" \
            --description "Harvest metadata from ${BUCKET_NAME} bucket" \
            2>/dev/null || echo "  [WARN] Job creation failed (may need manual config in Console)"
    fi
done

echo ""
echo "=== Harvesting Setup Complete ==="
echo ""
echo "Next Steps:"
echo "  1. Open Data Catalog in OCI Console"
echo "  2. Configure connection details for each data asset"
echo "  3. Run harvest jobs to discover schemas"
echo "  4. Add custom properties for lineage annotations:"
echo "     Landing -> Bronze -> Silver -> Gold -> Scores"
