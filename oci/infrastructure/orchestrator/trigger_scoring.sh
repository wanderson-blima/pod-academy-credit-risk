#!/bin/bash
# Trigger Data Science batch scoring job after Gold pipeline completes
# Usage: ./trigger_scoring.sh
#
# Prerequisites: SCORING_JOB_OCID, COMPARTMENT_OCID environment variables

set -euo pipefail

echo "--- Triggering Batch Scoring ---"

if [ -z "${SCORING_JOB_OCID:-}" ]; then
    echo "[WARN] SCORING_JOB_OCID not set. Skipping batch scoring."
    echo "  Set SCORING_JOB_OCID to enable automatic scoring after pipeline."
    exit 0
fi

# Submit Data Science job run
JOB_RUN=$(oci data-science job-run create \
    --job-id "${SCORING_JOB_OCID}" \
    --compartment-id "${COMPARTMENT_OCID}" \
    --display-name "batch-scoring-$(date +%Y%m%d-%H%M)" \
    --wait-for-state SUCCEEDED \
    --wait-for-state FAILED \
    --wait-interval-seconds 30 \
    --max-wait-seconds 7200 2>&1) || true

JOB_STATE=$(echo "$JOB_RUN" | jq -r '.data."lifecycle-state" // empty' 2>/dev/null)
JOB_RUN_ID=$(echo "$JOB_RUN" | jq -r '.data.id // empty' 2>/dev/null)

echo "  Job Run ID: ${JOB_RUN_ID:-unknown}"
echo "  State: ${JOB_STATE:-unknown}"

if [ "${JOB_STATE}" = "SUCCEEDED" ]; then
    echo "[SCORING] Batch scoring complete."

    # Notify success
    if [ -n "${ONS_TOPIC_OCID:-}" ]; then
        oci ons message publish \
            --topic-id "${ONS_TOPIC_OCID}" \
            --title "Pipeline + Scoring COMPLETE" \
            --body "Full pipeline and scoring completed at $(date). Job: ${JOB_RUN_ID}" \
            2>/dev/null || true
    fi
else
    echo "[SCORING] FAILED. Check: oci data-science job-run get --job-run-id ${JOB_RUN_ID}"
    if [ -n "${ONS_TOPIC_OCID:-}" ]; then
        oci ons message publish \
            --topic-id "${ONS_TOPIC_OCID}" \
            --title "Scoring FAILED" \
            --body "Batch scoring failed at $(date). Job Run: ${JOB_RUN_ID}" \
            2>/dev/null || true
    fi
    exit 1
fi
