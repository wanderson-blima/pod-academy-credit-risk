#!/bin/bash
# Upload pipeline scripts to Object Storage
# Usage: ./upload_scripts.sh
# Output: oci/tests/evidence/story-3.1/app_ocids.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
NAMESPACE="${NAMESPACE:-grlxi07jz1mo}"
SCRIPTS_BUCKET="pod-academy-scripts"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-3.1"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "UPLOAD SCRIPTS & VALIDATE APPS — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Upload pipeline scripts
SCRIPTS=(
    "pipeline/transform_silver.py"
    "pipeline/engineer_gold.py"
    "pipeline/unified_pipeline.py"
)

echo "[1/2] Uploading scripts..."
UPLOADED="["
for i in "${!SCRIPTS[@]}"; do
    SCRIPT_PATH="$SCRIPT_DIR/${SCRIPTS[$i]}"
    SCRIPT_NAME=$(basename "${SCRIPTS[$i]}")

    if [ -f "$SCRIPT_PATH" ]; then
        oci os object put \
            --bucket-name "$SCRIPTS_BUCKET" \
            --file "$SCRIPT_PATH" \
            --name "$SCRIPT_NAME" \
            --force --no-retry 2>/dev/null
        echo "  Uploaded: $SCRIPT_NAME"
        UPLOADED+="{\"name\": \"$SCRIPT_NAME\", \"status\": \"uploaded\"}"
    else
        echo "  [WARN] Not found: $SCRIPT_PATH"
        UPLOADED+="{\"name\": \"$SCRIPT_NAME\", \"status\": \"not_found\"}"
    fi
    if [ "$i" -lt "$((${#SCRIPTS[@]} - 1))" ]; then
        UPLOADED+=","
    fi
done
UPLOADED+="]"

# List Data Flow applications
echo ""
echo "[2/2] Listing Data Flow applications..."
APPS_JSON=$(oci data-flow application list \
    --compartment-id "$COMPARTMENT_OCID" \
    --query 'data[].{"id":id,"name":"display-name","state":"lifecycle-state"}' \
    --output json 2>/dev/null || echo "[]")

echo "  Applications found:"
echo "$APPS_JSON" | jq -r '.[] | "    \(.name) [\(.state)] — \(.id)"' 2>/dev/null || echo "    (none or error)"

# Extract specific app OCIDs
SILVER_APP=$(echo "$APPS_JSON" | jq -r '.[] | select(.name | contains("silver")) | .id' 2>/dev/null || echo "")
GOLD_APP=$(echo "$APPS_JSON" | jq -r '.[] | select(.name | contains("gold")) | .id' 2>/dev/null || echo "")

# Save evidence
EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"scripts_uploaded\": $UPLOADED,
  \"applications\": $APPS_JSON,
  \"silver_app_ocid\": \"$SILVER_APP\",
  \"gold_app_ocid\": \"$GOLD_APP\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/app_ocids.json"

echo ""
echo "Evidence saved: $EVIDENCE_DIR/app_ocids.json"
echo "============================================================"
