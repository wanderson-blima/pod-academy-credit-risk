#!/bin/bash
# Setup Airflow on AMD E3.Flex orchestrator instance
# Run this after SSH into the instance (post cloud-init)
#
# Usage: bash setup_airflow.sh

set -euo pipefail

ORCHESTRATOR_DIR="/home/opc/orchestrator"

echo "=== Airflow Setup ==="
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

# Verify Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Check cloud-init log."
    echo "  Run: sudo systemctl start docker"
    exit 1
fi
echo "[OK] Docker is running"

# Verify Docker Compose
if ! docker compose version > /dev/null 2>&1; then
    echo "[ERROR] Docker Compose not available"
    exit 1
fi
echo "[OK] Docker Compose available"

# Verify OCI CLI
if ! oci --version > /dev/null 2>&1; then
    echo "[WARN] OCI CLI not installed. Install with: pip3 install oci-cli"
fi

# Create required directories
mkdir -p "$ORCHESTRATOR_DIR/dags/scripts"
mkdir -p "$ORCHESTRATOR_DIR/logs"
mkdir -p "$ORCHESTRATOR_DIR/plugins"

# Start Airflow
cd "$ORCHESTRATOR_DIR"
echo ""
echo "Starting Airflow services..."
docker compose up -d

# Wait for health
echo "Waiting for Airflow to be healthy..."
RETRIES=30
for i in $(seq 1 $RETRIES); do
    if docker compose exec -T airflow-webserver curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        echo "[OK] Airflow webserver is healthy"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "[WARN] Airflow not yet healthy after $RETRIES attempts. Check logs."
    fi
    sleep 10
done

# Status
echo ""
echo "=== Airflow Status ==="
docker compose ps
echo ""
echo "Airflow version:"
docker compose exec -T airflow-webserver airflow version 2>/dev/null || echo "  (check manually)"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Access Airflow UI via SSH tunnel:"
echo "  ssh -L 8080:localhost:8080 opc@<instance-private-ip>"
echo "  Then open: http://localhost:8080"
echo "  Login: admin / admin"
