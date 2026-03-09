#!/bin/bash
# Validate Bronze layer data integrity
# Usage: ./validate_bronze.sh
# Output: oci/tests/evidence/story-2.2/bronze_tables.json

set -euo pipefail

NAMESPACE="${NAMESPACE:-grlxi07jz1mo}"
BRONZE_BUCKET="pod-academy-bronze"
EVIDENCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/tests/evidence/story-2.2"
mkdir -p "$EVIDENCE_DIR"

MAIN_TABLES=(
    "dados_cadastrais"
    "telco"
    "score_bureau_movel"
    "recarga"
    "pagamento"
    "faturamento"
    "dim_calendario"
)

echo "============================================================"
echo "BRONZE VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Bucket: $BRONZE_BUCKET"
echo "============================================================"

RESULT="{\"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\", \"bucket\": \"$BRONZE_BUCKET\", \"tables\": ["
FOUND=0
TOTAL=${#MAIN_TABLES[@]}

for i in "${!MAIN_TABLES[@]}"; do
    TABLE="${MAIN_TABLES[$i]}"

    # Count objects under table prefix
    OBJ_COUNT=$(oci os object list --bucket-name "$BRONZE_BUCKET" --prefix "${TABLE}/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")

    # Check for Delta Lake metadata
    DELTA_LOG=$(oci os object list --bucket-name "$BRONZE_BUCKET" --prefix "${TABLE}/_delta_log/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")

    if [ "$OBJ_COUNT" -gt "0" ]; then
        STATUS="OK"
        FOUND=$((FOUND + 1))
        FORMAT=$([ "$DELTA_LOG" -gt "0" ] && echo "delta" || echo "parquet")
        echo "  [OK] $TABLE — $OBJ_COUNT objects (format: $FORMAT)"
    else
        STATUS="MISSING"
        FORMAT="none"
        echo "  [MISSING] $TABLE"
    fi

    RESULT+="{\"name\": \"$TABLE\", \"status\": \"$STATUS\", \"object_count\": $OBJ_COUNT, \"format\": \"$FORMAT\", \"has_delta_log\": $([ "$DELTA_LOG" -gt "0" ] && echo true || echo false)}"
    if [ "$i" -lt "$((TOTAL - 1))" ]; then
        RESULT+=","
    fi
done

RESULT+="], \"found\": $FOUND, \"expected\": $TOTAL, \"validation\": \"$([ $FOUND -eq $TOTAL ] && echo PASSED || echo FAILED)\"}"

echo "$RESULT" | jq '.' > "$EVIDENCE_DIR/bronze_tables.json"

echo ""
echo "Result: $FOUND / $TOTAL main tables found in Bronze"
echo "Evidence saved: $EVIDENCE_DIR/bronze_tables.json"
echo "============================================================"

[ $FOUND -eq $TOTAL ] && exit 0 || exit 1
