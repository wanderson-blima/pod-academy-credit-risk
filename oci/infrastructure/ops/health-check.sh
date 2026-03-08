#!/bin/bash
# Health Check Script — Phase 6.3
# Verifies status of all OCI infrastructure components
#
# Usage: bash health-check.sh
# Requires: OCI CLI configured, environment variables set
#   - COMPARTMENT_OCID
#   - TENANCY_OCID
#   - ADW_OCID (optional)
#   - NOTEBOOK_OCID (optional)
set -uo pipefail

PREFIX=${PREFIX:-"pod-academy"}
PASS=0
FAIL=0
WARN=0

check() {
  local label="$1"
  local cmd="$2"
  local result
  result=$(eval "$cmd" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "  [OK]   $label"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $label"
    FAIL=$((FAIL + 1))
  fi
}

check_warn() {
  local label="$1"
  local cmd="$2"
  local result
  result=$(eval "$cmd" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "  [OK]   $label"
    PASS=$((PASS + 1))
  else
    echo "  [WARN] $label (non-critical)"
    WARN=$((WARN + 1))
  fi
}

echo "========================================"
echo "OCI Infrastructure Health Check"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "========================================"

# ── 1. Object Storage Buckets ────────────────────────────────────────────
echo ""
echo "--- Object Storage (6 buckets) ---"
for bucket in landing bronze silver gold logs scripts; do
  check "${PREFIX}-${bucket} bucket" \
    "oci os bucket get --name ${PREFIX}-${bucket} --query 'data.name' --raw-output"
done

# ── 2. Data Science Project ──────────────────────────────────────────────
echo ""
echo "--- Data Science ---"
check "Data Science project exists" \
  "oci data-science project list --compartment-id $COMPARTMENT_OCID --query 'data[?contains(\"display-name\",\`${PREFIX}\`)].id | [0]' --raw-output"

check_warn "Notebook session" \
  "oci data-science notebook-session list --compartment-id $COMPARTMENT_OCID --lifecycle-state ACTIVE --query 'data[0].id' --raw-output"

# ── 3. Data Flow ─────────────────────────────────────────────────────────
echo ""
echo "--- Data Flow ---"
check "Data Flow applications exist" \
  "oci data-flow application list --compartment-id $COMPARTMENT_OCID --query 'data[0].id' --raw-output"

# ── 4. Network ───────────────────────────────────────────────────────────
echo ""
echo "--- Network ---"
check "VCN exists" \
  "oci network vcn list --compartment-id $COMPARTMENT_OCID --query 'data[?contains(\"display-name\",\`${PREFIX}\`)].id | [0]' --raw-output"

# ── 5. Database (ADW) ────────────────────────────────────────────────────
echo ""
echo "--- Autonomous Data Warehouse ---"
if [ -n "${ADW_OCID:-}" ]; then
  ADW_STATE=$(oci db autonomous-database get --autonomous-database-id $ADW_OCID --query 'data."lifecycle-state"' --raw-output 2>/dev/null)
  if [ -n "$ADW_STATE" ]; then
    if [ "$ADW_STATE" = "AVAILABLE" ]; then
      echo "  [OK]   ADW state: $ADW_STATE"
      PASS=$((PASS + 1))
    else
      echo "  [WARN] ADW state: $ADW_STATE (stopped for cost savings)"
      WARN=$((WARN + 1))
    fi
  else
    echo "  [FAIL] ADW not accessible"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  [WARN] ADW_OCID not set — skipping"
  WARN=$((WARN + 1))
fi

# ── 6. Budget ────────────────────────────────────────────────────────────
echo ""
echo "--- Budget & Cost ---"
check "Budget exists" \
  "oci budgets budget list --compartment-id ${TENANCY_OCID:-$COMPARTMENT_OCID} --query 'data[0].\"display-name\"' --raw-output"

BUDGET_SPEND=$(oci budgets budget list --compartment-id ${TENANCY_OCID:-$COMPARTMENT_OCID} --query 'data[0]."actual-spend"' --raw-output 2>/dev/null)
BUDGET_AMOUNT=$(oci budgets budget list --compartment-id ${TENANCY_OCID:-$COMPARTMENT_OCID} --query 'data[0].amount' --raw-output 2>/dev/null)
if [ -n "$BUDGET_SPEND" ] && [ -n "$BUDGET_AMOUNT" ]; then
  echo "  [INFO] Spend: $BUDGET_SPEND / $BUDGET_AMOUNT"
fi

# ── 7. Model Artifacts ──────────────────────────────────────────────────
echo ""
echo "--- Model Artifacts (Gold bucket) ---"
check "LR model artifact" \
  "oci os object head --bucket-name ${PREFIX}-gold --name model_artifacts/models/lr_l1_oci_20260217_214614.pkl --query 'content-length' 2>/dev/null"

check "LGBM model artifact" \
  "oci os object head --bucket-name ${PREFIX}-gold --name model_artifacts/models/lgbm_oci_20260217_214614.pkl --query 'content-length' 2>/dev/null"

check "Training metrics" \
  "oci os object head --bucket-name ${PREFIX}-gold --name model_artifacts/metrics/training_results_20260217_214614.json --query 'content-length' 2>/dev/null"

check "Batch scoring output" \
  "oci os object head --bucket-name ${PREFIX}-gold --name model_artifacts/scoring/clientes_scores_all.parquet --query 'content-length' 2>/dev/null"

# ── Summary ──────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "Health Check Summary"
echo "  PASS: $PASS"
echo "  WARN: $WARN"
echo "  FAIL: $FAIL"
echo "========================================"

if [ $FAIL -gt 0 ]; then
  echo "STATUS: DEGRADED — $FAIL check(s) failed"
  exit 1
else
  echo "STATUS: HEALTHY"
  exit 0
fi
