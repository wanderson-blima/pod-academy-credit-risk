#!/bin/bash
# Validate OCI Data Science Notebook Session
# Usage: ./validate_notebook.sh
# Output: oci/tests/evidence/story-4.1/notebook_status.json

set -euo pipefail

COMPARTMENT_OCID="${COMPARTMENT_OCID:?Set COMPARTMENT_OCID}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="$SCRIPT_DIR/tests/evidence/story-4.1"
mkdir -p "$EVIDENCE_DIR"

echo "============================================================"
echo "NOTEBOOK SESSION VALIDATION — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================================"

# List notebook sessions
SESSIONS=$(oci data-science notebook-session list \
    --compartment-id "$COMPARTMENT_OCID" \
    --lifecycle-state ACTIVE \
    --query 'data[].{"id":id,"name":"display-name","state":"lifecycle-state","shape":"notebook-session-configuration-details"."shape","ocpus":"notebook-session-configuration-details"."notebook-session-shape-config-details"."ocpus","memory_gb":"notebook-session-configuration-details"."notebook-session-shape-config-details"."memory-in-gbs","url":"notebook-session-url"}' \
    --output json 2>/dev/null || echo "[]")

echo "Active notebook sessions:"
echo "$SESSIONS" | jq -r '.[] | "  \(.name) [\(.state)] — \(.shape) (\(.ocpus) OCPUs, \(.memory_gb) GB)"' 2>/dev/null || echo "  (none found)"

# Get first active session details
SESSION_ID=$(echo "$SESSIONS" | jq -r '.[0].id // empty' 2>/dev/null)
SESSION_NAME=$(echo "$SESSIONS" | jq -r '.[0].name // "none"' 2>/dev/null)
SESSION_URL=$(echo "$SESSIONS" | jq -r '.[0].url // "none"' 2>/dev/null)

EVIDENCE="{
  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\",
  \"sessions\": $SESSIONS,
  \"active_session_id\": \"${SESSION_ID:-none}\",
  \"session_name\": \"$SESSION_NAME\",
  \"session_url\": \"$SESSION_URL\",
  \"validation\": \"$([ -n "$SESSION_ID" ] && echo PASSED || echo NO_ACTIVE_SESSION)\"
}"

echo "$EVIDENCE" | jq '.' > "$EVIDENCE_DIR/notebook_status.json"

echo ""
echo "Evidence saved: $EVIDENCE_DIR/notebook_status.json"
echo "============================================================"
