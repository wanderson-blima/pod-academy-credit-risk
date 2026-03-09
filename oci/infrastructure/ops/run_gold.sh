#!/bin/bash
# Execute Gold Data Flow run and capture evidence
# Usage: ./run_gold.sh
# Output: oci/tests/evidence/story-3.3/gold_run.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
NAMESPACE="${NAMESPACE:-grlxi07jz1mo}"
GOLD_APP_OCID="${GOLD_APP_OCID:?Set GOLD_APP_OCID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-3.3"
mkdir -p "$EVIDENCE_DIR"

RUN_DATE=$(date +%Y%m%d)
DISPLAY_NAME="e2e-gold-$RUN_DATE"

echo "============================================================"
echo "GOLD DATA FLOW RUN — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Application: $GOLD_APP_OCID"
echo "Display Name: $DISPLAY_NAME"
echo "============================================================"

# Submit run
echo "[1/4] Submitting Data Flow run..."
RUN_RESPONSE=$(oci data-flow run create \
    --application-id "$GOLD_APP_OCID" \
    --compartment-id "$COMPARTMENT_OCID" \
    --display-name "$DISPLAY_NAME" \
    --arguments '["pod-academy-silver","pod-academy-gold","'"$NAMESPACE"'","pod-academy-landing"]' \
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

# Validate Gold output
echo "[4/4] Validating Gold output..."

# Check books
BOOKS="book_recarga_cmv book_pagamento book_faturamento"
BOOK_COUNTS="["
BOOKS_FOUND=0
for book in $BOOKS; do
    COUNT=$(oci os object list --bucket-name pod-academy-gold --prefix "$book/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    echo "  $book: $COUNT objects"
    BOOK_COUNTS+="{\"book\": \"$book\", \"objects\": $COUNT}"
    if [ "$COUNT" -gt "0" ]; then BOOKS_FOUND=$((BOOKS_FOUND + 1)); fi
    BOOK_COUNTS+=","
done
BOOK_COUNTS="${BOOK_COUNTS%,}]"

# Check feature store partitions
PARTITION_COUNT=$(oci os object list --bucket-name pod-academy-gold --prefix "feature_store/clientes_consolidado/SAFRA=" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
echo "  clientes_consolidado: $PARTITION_COUNT objects"

# Capture logs
DRIVER_LOG=$(oci data-flow run get-log --run-id "$RUN_ID" --name spark_driver_stderr --query 'data' --raw-output 2>/dev/null | head -200 || echo "log unavailable")

# Save evidence
EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"run_id\": \"$RUN_ID\",
  \"display_name\": \"$DISPLAY_NAME\",
  \"status\": \"$RUN_STATUS\",
  \"duration_minutes\": $DURATION_MIN,
  \"books\": $BOOK_COUNTS,
  \"books_found\": $BOOKS_FOUND,
  \"books_expected\": 3,
  \"feature_store_objects\": $PARTITION_COUNT,
  \"validation\": \"$([ $BOOKS_FOUND -ge 3 ] && [ $PARTITION_COUNT -gt 0 ] && echo PASSED || echo FAILED)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/gold_run.json"
echo "$DRIVER_LOG" > "$EVIDENCE_DIR/spark_driver_stderr.log" 2>/dev/null || true

echo ""
echo "Result: $RUN_STATUS (${DURATION_MIN}min), $BOOKS_FOUND/3 books, $PARTITION_COUNT partition objects"
echo "Evidence: $EVIDENCE_DIR/"
echo "============================================================"

[ "$RUN_STATUS" = "SUCCEEDED" ] && [ $BOOKS_FOUND -ge 3 ] && exit 0 || exit 1
