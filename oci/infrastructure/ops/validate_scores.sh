#!/bin/bash
# Validate batch scoring output in Gold bucket
# Usage: ./validate_scores.sh
# Output: oci/tests/evidence/story-4.4/score_distribution.json

set -euo pipefail

GOLD_BUCKET="pod-academy-gold"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-4.4"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "SCORING VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# Check clientes_scores partition objects
echo "Checking Gold bucket for scored data..."
SCORE_OBJECTS=$(oci os object list --bucket-name "$GOLD_BUCKET" --prefix "clientes_scores/" --query 'data[].{name:name,size:size}' --output json 2>/dev/null || echo "[]")
SCORE_COUNT=$(echo "$SCORE_OBJECTS" | jq 'length' 2>/dev/null || echo "0")

echo "  clientes_scores objects: $SCORE_COUNT"

# Check for SAFRA partitions
SAFRAS="202410 202411 202412 202501 202502 202503"
SAFRA_COUNTS="["
SAFRA_FOUND=0
for safra in $SAFRAS; do
    COUNT=$(oci os object list --bucket-name "$GOLD_BUCKET" --prefix "clientes_scores/SAFRA=$safra/" --query 'length(data)' --raw-output 2>/dev/null || echo "0")
    echo "  SAFRA=$safra: $COUNT objects"
    SAFRA_COUNTS+="{\"safra\": \"$safra\", \"objects\": $COUNT}"
    if [ "$COUNT" -gt "0" ]; then SAFRA_FOUND=$((SAFRA_FOUND + 1)); fi
    SAFRA_COUNTS+=","
done
SAFRA_COUNTS="${SAFRA_COUNTS%,}]"

EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"total_score_objects\": $SCORE_COUNT,
  \"safra_partitions\": $SAFRA_COUNTS,
  \"safras_found\": $SAFRA_FOUND,
  \"safras_expected\": 6,
  \"validation\": \"$([ $SAFRA_FOUND -ge 1 ] && echo PASSED || echo NO_SCORES)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/score_distribution.json"
echo ""
echo "Partitions found: $SAFRA_FOUND / 6"
echo "Evidence: $EVIDENCE_DIR/score_distribution.json"
echo "============================================================"
