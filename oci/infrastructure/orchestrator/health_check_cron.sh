#!/bin/bash
# Periodic health check for the orchestrator
# Checks: OCI CLI connectivity, bucket access, alarm status
# Usage: Run via cron every 6 hours
#   0 */6 * * * /home/opc/orchestrator/health_check_cron.sh

set -euo pipefail

LOG_DIR="/var/log/orchestrator"
LOG_FILE="${LOG_DIR}/health_$(date +%Y%m%d_%H%M%S).log"
NAMESPACE="${OCI_NAMESPACE:-grlxi07jz1mo}"
STATUS="HEALTHY"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Health Check — $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==="

# Check 1: OCI CLI authentication
echo -n "[1] OCI CLI auth... "
if oci iam region list --output table &>/dev/null; then
    echo "OK"
else
    echo "FAILED"
    STATUS="UNHEALTHY"
fi

# Check 2: Object Storage buckets
echo -n "[2] Buckets... "
BUCKET_COUNT=$(oci os bucket list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --query 'data[*].name' --output json 2>/dev/null | jq length)
if [ "${BUCKET_COUNT:-0}" -ge 6 ]; then
    echo "OK (${BUCKET_COUNT} buckets)"
else
    echo "WARN (expected 6, found ${BUCKET_COUNT:-0})"
    STATUS="DEGRADED"
fi

# Check 3: Gold data freshness
echo -n "[3] Gold data... "
GOLD_LATEST=$(oci os object list \
    --bucket-name pod-academy-gold \
    --prefix feature_store/clientes_consolidado/ \
    --query 'data[0]."time-modified"' --output json 2>/dev/null | tr -d '"')
if [ -n "${GOLD_LATEST}" ]; then
    echo "OK (latest: ${GOLD_LATEST})"
else
    echo "WARN (no Gold data found)"
    STATUS="DEGRADED"
fi

# Check 4: Disk space
echo -n "[4] Disk space... "
DISK_PCT=$(df /home/opc --output=pcent | tail -1 | tr -d '% ')
if [ "${DISK_PCT}" -lt 80 ]; then
    echo "OK (${DISK_PCT}% used)"
else
    echo "WARN (${DISK_PCT}% used)"
    STATUS="DEGRADED"
fi

# Summary
echo ""
echo "=== Status: ${STATUS} ==="

# Alert if unhealthy
if [ "${STATUS}" != "HEALTHY" ] && [ -n "${ONS_TOPIC_OCID:-}" ]; then
    oci ons message publish \
        --topic-id "${ONS_TOPIC_OCID}" \
        --title "Orchestrator Health: ${STATUS}" \
        --body "Health check at $(date) returned ${STATUS}. See ${LOG_FILE}" \
        2>/dev/null || true
fi
