#!/bin/bash
# Validate OCI Object Storage buckets and generate inventory
# Usage: ./validate_buckets.sh
# Output: oci/tests/evidence/story-2.1/bucket_inventory.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
NAMESPACE="${NAMESPACE:-grlxi07jz1mo}"
EVIDENCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/tests/evidence/story-2.1"
mkdir -p "$EVIDENCE_DIR"

EXPECTED_BUCKETS=(
    "pod-academy-landing"
    "pod-academy-bronze"
    "pod-academy-silver"
    "pod-academy-gold"
    "pod-academy-logs"
    "pod-academy-scripts"
)

echo "============================================================"
echo "BUCKET VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Compartment: $COMPARTMENT_OCID"
echo "============================================================"

INVENTORY="{"
INVENTORY+="\"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
INVENTORY+="\"compartment\": \"$COMPARTMENT_OCID\","
INVENTORY+="\"namespace\": \"$NAMESPACE\","
INVENTORY+="\"buckets\": ["

FOUND=0
TOTAL=${#EXPECTED_BUCKETS[@]}

for i in "${!EXPECTED_BUCKETS[@]}"; do
    BUCKET="${EXPECTED_BUCKETS[$i]}"

    # Check if bucket exists
    EXISTS=$(oci os bucket get --bucket-name "$BUCKET" --query 'data.name' --raw-output 2>/dev/null || echo "NOT_FOUND")

    if [ "$EXISTS" != "NOT_FOUND" ]; then
        # Count objects
        OBJ_COUNT=$(oci os object list --bucket-name "$BUCKET" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
        STATUS="OK"
        FOUND=$((FOUND + 1))
        echo "  [OK] $BUCKET — $OBJ_COUNT objects"
    else
        OBJ_COUNT=0
        STATUS="MISSING"
        echo "  [MISSING] $BUCKET"
    fi

    INVENTORY+="{\"name\": \"$BUCKET\", \"status\": \"$STATUS\", \"object_count\": $OBJ_COUNT}"
    if [ "$i" -lt "$((TOTAL - 1))" ]; then
        INVENTORY+=","
    fi
done

INVENTORY+="],"
INVENTORY+="\"found\": $FOUND,"
INVENTORY+="\"expected\": $TOTAL,"
INVENTORY+="\"validation\": \"$([ $FOUND -eq $TOTAL ] && echo PASSED || echo FAILED)\""
INVENTORY+="}"

# Save evidence
echo "$INVENTORY" | jq '.' > "$EVIDENCE_DIR/bucket_inventory.json"

echo ""
echo "Result: $FOUND / $TOTAL buckets found"
echo "Evidence saved: $EVIDENCE_DIR/bucket_inventory.json"
echo "============================================================"

[ $FOUND -eq $TOTAL ] && exit 0 || exit 1
