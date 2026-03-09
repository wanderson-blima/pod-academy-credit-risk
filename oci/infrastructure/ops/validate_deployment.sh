#!/bin/bash
# Validate OCI Model Deployment REST endpoint
# Usage: ./validate_deployment.sh
# Output: oci/tests/evidence/story-4.5/endpoint_url.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-4.5"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "MODEL DEPLOYMENT VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# List deployments
DEPLOYMENTS=$(oci data-science model-deployment list \
    --compartment-id "$COMPARTMENT_OCID" \
    --lifecycle-state ACTIVE \
    --query 'data[].{"id":id,"name":"display-name","state":"lifecycle-state","url":"model-deployment-url","created":"time-created"}' \
    --output json 2>/dev/null || echo "[]")

echo "Active deployments:"
echo "$DEPLOYMENTS" | jq -r '.[] | "  \(.name) [\(.state)] — \(.url)"' 2>/dev/null || echo "  (none)"

DEPLOYMENT_COUNT=$(echo "$DEPLOYMENTS" | jq 'length' 2>/dev/null || echo "0")
ENDPOINT_URL=$(echo "$DEPLOYMENTS" | jq -r '.[0].url // "none"' 2>/dev/null)

# Health check if endpoint exists
HEALTH_STATUS="not_checked"
if [ "$ENDPOINT_URL" != "none" ] && [ -n "$ENDPOINT_URL" ]; then
    echo ""
    echo "Health check: $ENDPOINT_URL/health"
    HEALTH_RESPONSE=$(curl -sf "$ENDPOINT_URL/health" 2>/dev/null || echo '{"status": "unreachable"}')
    HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status // "unknown"' 2>/dev/null || echo "error")
    echo "  Status: $HEALTH_STATUS"
fi

EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"deployments\": $DEPLOYMENTS,
  \"deployment_count\": $DEPLOYMENT_COUNT,
  \"endpoint_url\": \"$ENDPOINT_URL\",
  \"health_status\": \"$HEALTH_STATUS\",
  \"validation\": \"$([ $DEPLOYMENT_COUNT -gt 0 ] && echo PASSED || echo NO_DEPLOYMENTS)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/endpoint_url.json"
echo ""
echo "Deployments found: $DEPLOYMENT_COUNT"
echo "Evidence: $EVIDENCE_DIR/endpoint_url.json"
echo "============================================================"
