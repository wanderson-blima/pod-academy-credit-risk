#!/bin/bash
# Validate OCI Model Catalog registration
# Usage: ./validate_model_catalog.sh
# Output: oci/tests/evidence/story-4.3/model_ocids.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-4.3"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "MODEL CATALOG VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# List models
MODELS=$(oci data-science model list \
    --compartment-id "$COMPARTMENT_OCID" \
    --query 'data[].{"id":id,"name":"display-name","state":"lifecycle-state","created":"time-created","tags":"freeform-tags"}' \
    --output json 2>/dev/null || echo "[]")

echo "Registered models:"
echo "$MODELS" | jq -r '.[] | "  \(.name) [\(.state)] — \(.id)"' 2>/dev/null || echo "  (none)"

MODEL_COUNT=$(echo "$MODELS" | jq 'length' 2>/dev/null || echo "0")

EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"models\": $MODELS,
  \"model_count\": $MODEL_COUNT,
  \"validation\": \"$([ $MODEL_COUNT -gt 0 ] && echo PASSED || echo NO_MODELS)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/model_ocids.json"
echo ""
echo "Models found: $MODEL_COUNT"
echo "Evidence: $EVIDENCE_DIR/model_ocids.json"
echo "============================================================"
