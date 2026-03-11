#!/bin/bash
# Execute Silver Data Flow run and capture evidence
# Usage: ./run_silver.sh
# Output: oci/tests/evidence/story-3.2/silver_run.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
NAMESPACE="${NAMESPACE:-grlxi07jz1mo}"
SILVER_APP_OCID="${SILVER_APP_OCID:?Set SILVER_APP_OCID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-3.2"
mkdir -p "$EVIDENCE_DIR"

RUN_DATE=$(date +%Y%m%d)
DISPLAY_NAME="e2e-silver-$RUN_DATE"

echo "============================================================"
echo "SILVER DATA FLOW RUN — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Application: $SILVER_APP_OCID"
echo "Display Name: $DISPLAY_NAME"
echo "============================================================"

# Submit run
echo "[1/4] Submitting Data Flow run..."
RUN_RESPONSE=$(oci data-flow run create \
    --application-id "$SILVER_APP_OCID" \
    --compartment-id "$COMPARTMENT_OCID" \
    --display-name "$DISPLAY_NAME" \
    --arguments '["pod-academy-bronze","pod-academy-silver","'"$NAMESPACE"'","pod-academy-landing"]' \
    2>/dev/null)

RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.data.id')
echo "  Run ID: $RUN_ID"

# Poll until terminal state
echo "[2/4] Polling for completion..."
START_TIME=$(date +%s)

while true; do
    RUN_STATUS=$(oci data-flow run get --run-id "$RUN_ID" --query 'data."lifecycle-state"' --raw-output 2>/dev/null)
    ELAPSED=$(( $(date +%s) - START_TIME ))
    echo "  [$((ELAPSED/60))m] State: $RUN_STATUS"

    if [ "$RUN_STATUS" = "SUCCEEDED" ] || [ "$RUN_STATUS" = "FAILED" ] || [ "$RUN_STATUS" = "CANCELED" ]; then
        break
    fi
    sleep 60
done

END_TIME=$(date +%s)
DURATION_MIN=$(( (END_TIME - START_TIME) / 60 ))

# Get run details
echo "[3/4] Fetching run details..."
RUN_DETAILS=$(oci data-flow run get --run-id "$RUN_ID" 2>/dev/null)

# Validate Silver output
echo "[4/4] Validating Silver tables..."
TABLES="dados_cadastrais telco score_bureau_movel recarga pagamento faturamento dim_calendario"
TABLE_COUNTS="["
FOUND=0
for table in $TABLES; do
    COUNT=$(oci os object list --bucket-name pod-academy-silver --prefix "rawdata/$table/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    echo "  $table: $COUNT objects"
    TABLE_COUNTS+="{\"table\": \"$table\", \"objects\": $COUNT}"
    if [ "$COUNT" -gt "0" ]; then FOUND=$((FOUND + 1)); fi
    TABLE_COUNTS+=","
done
TABLE_COUNTS="${TABLE_COUNTS%,}]"

# Capture logs (first 200 lines)
echo "  Capturing Spark driver stderr..."
DRIVER_LOG=$(oci data-flow run get-log --run-id "$RUN_ID" --name spark_driver_stderr --query 'data' --raw-output 2>/dev/null | head -200 || echo "log unavailable")

# Save evidence
EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"run_id\": \"$RUN_ID\",
  \"display_name\": \"$DISPLAY_NAME\",
  \"status\": \"$RUN_STATUS\",
  \"duration_minutes\": $DURATION_MIN,
  \"silver_tables\": $TABLE_COUNTS,
  \"tables_found\": $FOUND,
  \"tables_expected\": 7,
  \"validation\": \"$([ $FOUND -ge 7 ] && echo PASSED || echo FAILED)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/silver_run.json"
echo "$DRIVER_LOG" > "$EVIDENCE_DIR/spark_driver_stderr.log" 2>/dev/null || true

echo ""
echo "Result: $RUN_STATUS (${DURATION_MIN}min), $FOUND/7 tables"
echo "Evidence: $EVIDENCE_DIR/"
echo "============================================================"

[ "$RUN_STATUS" = "SUCCEEDED" ] && [ $FOUND -ge 7 ] && exit 0 || exit 1
