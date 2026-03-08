#!/bin/bash
# Cloud-init for Ensemble v2 (Top-3) VM
# Installs Python 3.11 + ML dependencies
set -e
exec > /var/log/cloud-init-ensemble3.log 2>&1

echo "=== Cloud-init started: $(date) ==="

# Install Python 3.11
dnf install -y python3.11 python3.11-pip

# Install ML packages
python3.11 -m pip install --quiet \
    numpy pandas scikit-learn scipy \
    lightgbm xgboost catboost \
    oci pyarrow

# Setup OCI config for opc user
mkdir -p /home/opc/.oci
mkdir -p /home/opc/ensemble3/output
chown -R opc:opc /home/opc/.oci /home/opc/ensemble3

echo "=== Cloud-init finished: $(date) ==="
