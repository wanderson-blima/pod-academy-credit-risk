#!/bin/bash
# Orchestrator: Run unified pipeline end-to-end
# Usage: ./run_pipeline.sh [--start-phase bronze|silver|gold]
#
# Prerequisites:
#   - OCI CLI configured (~/.oci/config)
#   - Environment variables: COMPARTMENT_OCID, UNIFIED_APP_OCID, SCORING_JOB_OCID

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/orchestrator"
LOG_FILE="${LOG_DIR}/pipeline_$(date +%Y%m%d_%H%M%S).log"
NAMESPACE="${OCI_NAMESPACE:-grlxi07jz1mo}"
SCRIPTS_BUCKET="${SCRIPTS_BUCKET:-pod-academy-scripts}"
START_PHASE="${1:---start-phase}"
PHASE_VALUE="${2:-bronze}"

# Logging
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo "PIPELINE ORCHESTRATOR — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Start Phase: ${PHASE_VALUE}"
echo "============================================================"

# Step 1: Upload latest scripts
echo ""
echo "[1/4] Uploading pipeline scripts to Object Storage..."
for script in ingest_bronze.py transform_silver.py engineer_gold.py unified_pipeline.py; do
    if [ -f "${SCRIPT_DIR}/../../pipeline/${script}" ]; then
        oci os object put \
            --bucket-name "${SCRIPTS_BUCKET}" \
            --file "${SCRIPT_DIR}/../../pipeline/${script}" \
            --name "${script}" \
            --force --no-retry
        echo "  Uploaded: ${script}"
    fi
done

# Create archive with dependencies for Data Flow
echo "  Creating pipeline_deps.zip..."
cd "${SCRIPT_DIR}/../../pipeline"
zip -j /tmp/pipeline_deps.zip ingest_bronze.py transform_silver.py engineer_gold.py 2>/dev/null || true
oci os object put \
    --bucket-name "${SCRIPTS_BUCKET}" \
    --file /tmp/pipeline_deps.zip \
    --name "pipeline_deps.zip" \
    --force --no-retry
echo "  Uploaded: pipeline_deps.zip"
cd "${SCRIPT_DIR}"

# Step 2: Submit Data Flow run
echo ""
echo "[2/4] Submitting unified pipeline to Data Flow..."
RUN_RESPONSE=$(oci data-flow run submit \
    --application-id "${UNIFIED_APP_OCID}" \
    --display-name "unified-pipeline-$(date +%Y%m%d-%H%M)" \
    --arguments "[\"--start-phase\", \"${PHASE_VALUE}\"]" \
    --wait-for-state SUCCEEDED \
    --wait-for-state FAILED \
    --wait-interval-seconds 60 \
    --max-wait-seconds 21600 2>&1) || true

RUN_ID=$(echo "$RUN_RESPONSE" | jq -r '.data.id // empty' 2>/dev/null)
RUN_STATE=$(echo "$RUN_RESPONSE" | jq -r '.data."lifecycle-state" // empty' 2>/dev/null)

echo "  Run ID: ${RUN_ID:-unknown}"
echo "  State: ${RUN_STATE:-unknown}"

# Step 3: Check result
if [ "${RUN_STATE}" = "SUCCEEDED" ]; then
    echo ""
    echo "[3/4] Data Flow SUCCEEDED. Triggering scoring..."
    bash "${SCRIPT_DIR}/trigger_scoring.sh"
else
    echo ""
    echo "[3/4] Data Flow FAILED or timed out."
    echo "  Check logs: oci data-flow run get-log --run-id ${RUN_ID} --name spark_driver_stderr"

    # Send failure notification
    if [ -n "${ONS_TOPIC_OCID:-}" ]; then
        oci ons message publish \
            --topic-id "${ONS_TOPIC_OCID}" \
            --title "Pipeline FAILED" \
            --body "Unified pipeline failed at $(date). Run ID: ${RUN_ID}. Check Data Flow logs." \
            2>/dev/null || true
    fi
    exit 1
fi

# Step 4: Summary
echo ""
echo "[4/4] Pipeline orchestration complete."
echo "============================================================"
echo "PIPELINE COMPLETE — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "  Data Flow Run: ${RUN_ID}"
echo "  Log: ${LOG_FILE}"
echo "============================================================"
