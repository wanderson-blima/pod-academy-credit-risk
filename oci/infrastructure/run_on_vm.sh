#!/bin/bash
# Script to download data and run ensemble pipeline on OCI VM
set -e

export PATH=/root/.local/bin:$PATH
export OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING=True
export OCI_NAMESPACE="grlxi07jz1mo"
export GOLD_BUCKET="pod-academy-gold"
export ARTIFACT_DIR="/home/opc/artifacts"
export DATA_PATH="/home/opc/data/feature_store/clientes_consolidado/"

LOG_FILE="/home/opc/pipeline_run.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "$(date) === Starting data download and pipeline ==="

# Download pipeline scripts
echo "$(date) — Downloading pipeline scripts..."
mkdir -p /home/opc/pipeline
oci os object bulk-download \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --prefix "pipeline_scripts/" \
  --download-dir /home/opc/pipeline/ \
  --overwrite 2>&1 | tail -5

echo "$(date) — Pipeline scripts downloaded:"
ls -la /home/opc/pipeline/pipeline_scripts/

# Download feature store data
echo "$(date) — Downloading feature store data..."
mkdir -p /home/opc/data/feature_store/clientes_consolidado/
oci os object bulk-download \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --prefix "feature_store/clientes_consolidado/" \
  --download-dir /home/opc/data/ \
  --overwrite 2>&1 | tail -10

echo "$(date) — Data downloaded:"
ls -la /home/opc/data/feature_store/clientes_consolidado/ | head -15
du -sh /home/opc/data/feature_store/clientes_consolidado/

# Download baseline model
echo "$(date) — Downloading baseline model..."
mkdir -p /home/opc/artifacts/models
oci os object get \
  --bucket-name "$GOLD_BUCKET" \
  --namespace "$OCI_NAMESPACE" \
  --name "model_artifacts/models/lgbm_oci_20260217_214614.pkl" \
  --file "/home/opc/artifacts/models/lgbm_oci_20260217_214614.pkl" 2>&1

echo "$(date) — Baseline model downloaded:"
ls -la /home/opc/artifacts/models/

# Run the pipeline
echo "$(date) === Starting full ensemble pipeline ==="
cd /home/opc/pipeline/pipeline_scripts/

echo "$(date) — Python version: $(python3 --version)"
echo "$(date) — CPUs: $(nproc)"
echo "$(date) — Pipeline directory: $(pwd)"
ls -la *.py

python3 run_full_pipeline.py \
  --n-trials 50 \
  --data-path "$DATA_PATH" \
  2>&1

PIPELINE_EXIT=$?

if [ $PIPELINE_EXIT -eq 0 ]; then
  echo "$(date) === Pipeline complete! (exit code 0) ==="
  echo "DONE" > /home/opc/pipeline_status.txt
else
  echo "$(date) === Pipeline failed! (exit code $PIPELINE_EXIT) ==="
  echo "FAILED:$PIPELINE_EXIT" > /home/opc/pipeline_status.txt
fi

touch /home/opc/PIPELINE_COMPLETE
