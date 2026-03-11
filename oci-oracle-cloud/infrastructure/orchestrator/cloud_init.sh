#!/bin/bash
# Cloud-init script for orchestrator instance
# Installs Docker, Docker Compose, OCI CLI, Python 3.9, and Apache Airflow
#
# Shape: VM.Standard.E3.Flex (2 OCPUs, 16 GB RAM) - Paid (~$1.68/day)
# OS: Oracle Linux 8 (x86_64)

set -e
exec > /var/log/cloud-init-orchestrator.log 2>&1

echo "=== Orchestrator Cloud Init ==="
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Shape: VM.Standard.E3.Flex (AMD x86_64)"

# --- System updates -------------------------------------------------------
echo "[1/6] System updates..."
dnf update -y
dnf install -y python39 python39-pip jq zip unzip curl wget

# Set Python 3.9 as default
alternatives --set python3 /usr/bin/python3.9

# --- Install Docker -------------------------------------------------------
echo "[2/6] Installing Docker..."
dnf install -y dnf-utils
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
systemctl start docker
systemctl enable docker

# Add opc user to docker group
usermod -aG docker opc

echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"

# --- Install OCI CLI ------------------------------------------------------
echo "[3/6] Installing OCI CLI..."
pip3 install oci-cli --upgrade

# --- Create orchestrator directories --------------------------------------
echo "[4/6] Creating directories..."
mkdir -p /home/opc/orchestrator/dags/scripts
mkdir -p /home/opc/orchestrator/logs
mkdir -p /home/opc/orchestrator/plugins
mkdir -p /var/log/orchestrator

# --- Copy Docker Compose file ---------------------------------------------
echo "[5/6] Setting up Airflow Docker Compose..."
cat > /home/opc/orchestrator/docker-compose.yaml << 'COMPOSE_EOF'
x-airflow-common: &airflow-common
  image: apache/airflow:2.8.1
  environment: &airflow-env
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__CORE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
    AIRFLOW__CORE__FERNET_KEY: ''
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
    AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    AIRFLOW__CORE__PARALLELISM: '4'
    AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG: '4'
    AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG: '2'
    AIRFLOW__CORE__DEFAULT_TIMEZONE: America/Sao_Paulo
    AIRFLOW__WEBSERVER__DEFAULT_UI_TIMEZONE: America/Sao_Paulo
    OCI_CLI_CONFIG_FILE: /home/airflow/.oci/config
  volumes:
    - ./dags:/opt/airflow/dags
    - ./logs:/opt/airflow/logs
    - ./plugins:/opt/airflow/plugins
    - /home/opc/.oci:/home/airflow/.oci:ro
  user: "50000:0"
  restart: unless-stopped

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  airflow-init:
    <<: *airflow-common
    entrypoint: /bin/bash
    command:
      - -c
      - |
        airflow db init
        airflow users create \
          --username admin --firstname Admin --lastname User \
          --role Admin --email admin@pod-academy.local --password admin
    depends_on:
      postgres:
        condition: service_healthy
    restart: "no"

  airflow-webserver:
    <<: *airflow-common
    command: webserver
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
    depends_on:
      postgres:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully

  airflow-scheduler:
    <<: *airflow-common
    command: scheduler
    depends_on:
      postgres:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully

volumes:
  postgres-data:
COMPOSE_EOF

# --- Open firewall ports ---------------------------------------------------
echo "[6/8] Opening firewall ports (SSH + Airflow UI)..."
# Wait for firewalld to be fully ready (avoids DBus race condition on first boot)
sleep 5
systemctl restart firewalld || true
firewall-cmd --permanent --add-port=8080/tcp || true
firewall-cmd --permanent --add-port=22/tcp || true
firewall-cmd --reload || true

# --- Set permissions -------------------------------------------------------
echo "[7/8] Setting permissions..."
chown -R opc:opc /home/opc/orchestrator
chown -R opc:opc /var/log/orchestrator
# Airflow container runs as UID 50000 — logs/plugins must be writable
chown -R 50000:0 /home/opc/orchestrator/logs
chown -R 50000:0 /home/opc/orchestrator/plugins
chmod -R 775 /home/opc/orchestrator/logs
chmod -R 775 /home/opc/orchestrator/plugins

# --- Start Airflow automatically -------------------------------------------
echo "[8/8] Starting Airflow Docker Compose..."
cd /home/opc/orchestrator
sudo -u opc docker compose up -d

echo "=== Cloud Init Complete ==="
echo "Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""
echo "Access Airflow UI: http://<public-ip>:8080"
echo "Login: admin / admin"
