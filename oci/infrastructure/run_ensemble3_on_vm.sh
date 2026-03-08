#!/bin/bash
# ============================================================
# Ensemble v2 — Top-3 Champion Models Only
# Quick run: load existing HPO-optimized models, create ensemble
# Expected time: ~20 minutes total
# ============================================================
set -e

echo "=========================================="
echo "  Ensemble v2 — Top-3 Champions"
echo "  $(date)"
echo "=========================================="

# ── 1. Setup Python environment ──
echo "[1/5] Setting up Python environment..."
sudo dnf install -y python3.11 python3.11-pip > /dev/null 2>&1
python3.11 -m pip install --quiet numpy pandas scikit-learn lightgbm xgboost catboost oci-sdk

# ── 2. Create OCI config ──
echo "[2/5] Configuring OCI SDK..."
mkdir -p ~/.oci
cat > ~/.oci/config << 'OCIEOF'
[DEFAULT]
user=ocid1.user.oc1..aaaaaaaagmruwfvulphb4jupvfcvhl44s3bzdfrnrpauwqhg3mfsdcvd4ppa
fingerprint=c5:55:e5:1b:4b:e7:0c:30:e3:cc:78:86:e3:03:a5:25
tenancy=ocid1.tenancy.oc1..aaaaaaaahse5thvzinsvm7bkyrd3zravzao2i6kpfl4bfxkplbu7ppla5x5a
region=sa-saopaulo-1
key_file=~/.oci/oci_api_key.pem
OCIEOF

# Key will be injected via metadata or scp
echo "[2/5] Waiting for OCI key..."
while [ ! -f ~/.oci/oci_api_key.pem ]; do sleep 2; done
chmod 600 ~/.oci/oci_api_key.pem
echo "[2/5] OCI config ready."

# ── 3. Download feature store + models ──
echo "[3/5] Downloading data and models from OCI..."
NAMESPACE="grlxi07jz1mo"
BUCKET="pod-academy-gold"
WORK_DIR="/home/opc/ensemble3"
mkdir -p $WORK_DIR/models

# Download feature store
oci os object get -ns $NAMESPACE -bn $BUCKET \
    --name "feature_store/clientes_consolidado.parquet" \
    --file "$WORK_DIR/clientes_consolidado.parquet" 2>/dev/null && \
    echo "  Downloaded feature store" || echo "  Trying CSV..."

# If parquet not available, try the gold path
if [ ! -f "$WORK_DIR/clientes_consolidado.parquet" ]; then
    oci os object get -ns $NAMESPACE -bn $BUCKET \
        --name "gold/clientes_consolidado.parquet" \
        --file "$WORK_DIR/clientes_consolidado.parquet" 2>/dev/null || true
fi

# Download the 3 champion models
for MODEL in LightGBM_v2 XGBoost CatBoost; do
    oci os object get -ns $NAMESPACE -bn $BUCKET \
        --name "model_artifacts/ensemble_v1/models_v2/${MODEL}.pkl" \
        --file "$WORK_DIR/models/${MODEL}.pkl"
    echo "  Downloaded ${MODEL}.pkl"
done

# Also download the ensemble v1 for comparison
oci os object get -ns $NAMESPACE -bn $BUCKET \
    --name "model_artifacts/ensemble_v1/ensemble/ensemble_results.json" \
    --file "$WORK_DIR/ensemble_v1_results.json" 2>/dev/null || true

echo "[3/5] Downloads complete."

# ── 4. Run ensemble script ──
echo "[4/5] Running ensemble-3 pipeline..."
python3.11 $WORK_DIR/run_ensemble3.py 2>&1 | tee $WORK_DIR/ensemble3.log

# ── 5. Upload results ──
echo "[5/5] Uploading results to OCI..."
for f in $WORK_DIR/output/*; do
    fname=$(basename $f)
    oci os object put -ns $NAMESPACE -bn $BUCKET \
        --name "model_artifacts/ensemble_v2_top3/$fname" \
        --file "$f" --force
    echo "  Uploaded $fname"
done

echo "=========================================="
echo "  DONE — $(date)"
echo "=========================================="
