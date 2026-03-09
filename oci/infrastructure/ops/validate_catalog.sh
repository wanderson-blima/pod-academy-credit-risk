#!/bin/bash
# Validate OCI Data Catalog harvest
# Usage: ./validate_catalog.sh
# Output: oci/tests/evidence/story-5.3/catalog_harvest.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
PREFIX="${PREFIX:-pod-academy}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-5.3"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "DATA CATALOG VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Find catalog
CATALOGS=$(oci data-catalog catalog list \
    --compartment-id "$COMPARTMENT_OCID" \
    --query 'data.items[].{"id":id,"name":"display-name","state":"lifecycle-state"}' \
    --output json 2>/dev/null || echo "[]")

echo "Catalogs found:"
echo "$CATALOGS" | jq -r '.[] | "  \(.name) [\(.state)] — \(.id)"' 2>/dev/null || echo "  (none)"

CATALOG_COUNT=$(echo "$CATALOGS" | jq 'length' 2>/dev/null || echo "0")
CATALOG_ID=$(echo "$CATALOGS" | jq -r '.[0].id // "none"' 2>/dev/null)

# List data assets if catalog exists
ASSETS="[]"
if [ "$CATALOG_ID" != "none" ] && [ -n "$CATALOG_ID" ]; then
    ASSETS=$(oci data-catalog data-asset list \
        --catalog-id "$CATALOG_ID" \
        --query 'data.items[].{"key":key,"name":"display-name","type":"type-key"}' \
        --output json 2>/dev/null || echo "[]")
    echo ""
    echo "Data assets:"
    echo "$ASSETS" | jq -r '.[] | "  \(.name) [\(.type)]"' 2>/dev/null || echo "  (none)"
fi

ASSET_COUNT=$(echo "$ASSETS" | jq 'length' 2>/dev/null || echo "0")

EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"catalogs\": $CATALOGS,
  \"catalog_id\": \"$CATALOG_ID\",
  \"catalog_count\": $CATALOG_COUNT,
  \"data_assets\": $ASSETS,
  \"asset_count\": $ASSET_COUNT,
  \"validation\": \"$([ $CATALOG_COUNT -gt 0 ] && echo PASSED || echo NO_CATALOG)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/catalog_harvest.json"
echo ""
echo "Evidence: $EVIDENCE_DIR/catalog_harvest.json"
echo "============================================================"
