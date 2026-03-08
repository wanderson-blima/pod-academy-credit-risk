#!/bin/bash
# Cloud-init script for OCI Compute Instance
# Installs dependencies, downloads data, runs full ensemble pipeline
set -e

LOG_FILE="/home/opc/pipeline.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "$(date) — Starting ensemble training pipeline setup..."

# Install Python 3.9 (OL8 default python3 is 3.6 — too old for catboost/xgboost/optuna)
echo "$(date) — Installing Python 3.9..."
sudo dnf module install -y python39 2>/dev/null || true
sudo dnf install -y python39-pip python39-devel gcc gcc-c++ 2>/dev/null || true
sudo alternatives --set python3 /usr/bin/python3.9 2>/dev/null || true

echo "$(date) — Python version: $(python3 --version)"

# Install Python dependencies
echo "$(date) — Installing Python packages..."
python3 -m pip install --user --upgrade pip
python3 -m pip install --user numpy pandas scikit-learn scipy pyarrow lightgbm xgboost catboost optuna category_encoders shap oci oci-cli 2>&1 | tail -20

# OCI CLI config — use instance principal auth
export OCI_CLI_AUTH=instance_principal
export OCI_NAMESPACE="grlxi07jz1mo"
export GOLD_BUCKET="pod-academy-gold"
export NOTEBOOK_OCPUS=$(nproc)
export ARTIFACT_DIR="/home/opc/artifacts"
export DATA_PATH="/home/opc/data/feature_store/clientes_consolidado/"

echo "$(date) — CPUs: $(nproc), ARTIFACT_DIR: $ARTIFACT_DIR"

# Download data from Object Storage
echo "$(date) — Downloading feature store data..."
mkdir -p /home/opc/data/feature_store/clientes_consolidado/
oci os object bulk-download \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --prefix "feature_store/clientes_consolidado/" \
  --download-dir /home/opc/data/ \
  --overwrite 2>&1 | tail -5

echo "$(date) — Data download complete"
ls -la /home/opc/data/feature_store/clientes_consolidado/ | head -10

# Download baseline model
echo "$(date) — Downloading baseline model..."
mkdir -p /home/opc/artifacts/models
oci os object get \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --name "model_artifacts/models/lgbm_oci_20260217_214614.pkl" \
  --file "/home/opc/artifacts/models/lgbm_oci_20260217_214614.pkl" 2>&1 || true

# Download pipeline scripts from Object Storage
echo "$(date) — Downloading pipeline scripts..."
mkdir -p /home/opc/pipeline
oci os object bulk-download \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --prefix "pipeline_scripts/" \
  --download-dir /home/opc/pipeline/ \
  --overwrite 2>&1 || true

# Run the full pipeline
echo "$(date) — Starting full ensemble pipeline..."
cd /home/opc/pipeline/pipeline_scripts/ 2>/dev/null || cd /home/opc/pipeline/

echo "$(date) — Pipeline directory: $(pwd)"
ls -la *.py 2>/dev/null || echo "No Python files found"

# Use set +e so pipeline errors don't kill cloud-init
set +e
python3 run_full_pipeline.py \
  --n-trials 50 \
  --data-path "$DATA_PATH" \
  2>&1
PIPELINE_EXIT=$?
set -e

if [ $PIPELINE_EXIT -eq 0 ]; then
  echo "$(date) — Pipeline complete! (exit code 0)"
  echo "DONE" > /home/opc/pipeline_status.txt
else
  echo "$(date) — Pipeline failed! (exit code $PIPELINE_EXIT)"
  echo "FAILED:$PIPELINE_EXIT" > /home/opc/pipeline_status.txt
fi

# Signal completion
touch /home/opc/PIPELINE_COMPLETE
