#!/bin/bash
# Configure cron schedule for the pipeline orchestrator
# Usage: ./schedule_pipeline.sh [weekly|daily|manual]

set -euo pipefail

SCHEDULE="${1:-weekly}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${SCHEDULE}" in
    weekly)
        CRON_EXPR="0 2 * * 1"  # Monday 2 AM
        ;;
    daily)
        CRON_EXPR="0 2 * * *"  # Daily 2 AM
        ;;
    manual)
        echo "Removing pipeline cron entry..."
        crontab -l 2>/dev/null | grep -v "run_pipeline.sh" | crontab - || true
        echo "Pipeline cron removed. Run manually with: ${SCRIPT_DIR}/run_pipeline.sh"
        exit 0
        ;;
    *)
        echo "Usage: $0 [weekly|daily|manual]"
        exit 1
        ;;
esac

# Add cron entry (replace existing if present)
(crontab -l 2>/dev/null | grep -v "run_pipeline.sh"; \
 echo "${CRON_EXPR} ${SCRIPT_DIR}/run_pipeline.sh >> /var/log/orchestrator/cron.log 2>&1") | crontab -

echo "Pipeline scheduled: ${SCHEDULE} (${CRON_EXPR})"
echo "  Script: ${SCRIPT_DIR}/run_pipeline.sh"
echo "  Logs: /var/log/orchestrator/cron.log"
