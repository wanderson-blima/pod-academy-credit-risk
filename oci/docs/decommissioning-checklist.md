# Decommissioning Checklist — OCI Data Platform

**Purpose**: Safe teardown of all OCI infrastructure after hackathon
**Estimated Time**: 30 minutes

---

## Pre-Destruction (15 min)

- [ ] **Export model artifacts** to local storage
  ```bash
  bash oci/infrastructure/ops/backup-data.sh
  ```
- [ ] **Download Terraform state** for audit trail
  ```bash
  cp oci/infrastructure/terraform/terraform.tfstate ./backup/terraform.tfstate
  ```
- [ ] **Export cost report** for final accounting
  ```bash
  bash oci/infrastructure/ops/cost-report.sh > ./backup/final-cost-report.txt
  ```
- [ ] **Verify backup completeness**
  - Gold feature store parquet files
  - Model .pkl files (LR + LGBM)
  - Training metrics JSON
  - Batch scoring output
  - Feature importance CSV
- [ ] **Notify team** of planned teardown
  - Send email/message with teardown date and time
  - Confirm no one has active sessions
- [ ] **Commit and push** all code changes to Git

## Destruction Sequence (10 min)

Execute in this exact order:

### Step 1: Stop All Resources
```bash
bash oci/infrastructure/ops/stop-infra.sh
```
- ADW -> STOPPED
- Notebook -> INACTIVE
- Model Deployments -> deactivated

### Step 2: Delete Model Deployments (if any)
```bash
oci data-science model-deployment list \
  --compartment-id $COMPARTMENT_OCID \
  --query 'data[*].id' --raw-output | \
  xargs -I {} oci data-science model-deployment delete --model-deployment-id {} --force
```

### Step 3: Terraform Destroy
```bash
cd oci/infrastructure/terraform
terraform plan -destroy -out=destroy.tfplan
# Review the plan carefully
terraform apply destroy.tfplan
```

Expected: 43 resources destroyed (network, storage, database, dataflow, datascience, cost, monitoring).

### Step 4: Clean Up Remaining Resources
Resources not managed by Terraform (if any):
```bash
# Check for orphaned resources
oci search resource structured-search \
  --query-text "query all resources where compartmentId = '$COMPARTMENT_OCID'" \
  --query 'data.items[*].{"Type":"resource-type","Name":"display-name","State":"lifecycle-state"}' \
  --output table
```

## Post-Destruction Verification (5 min)

- [ ] **Verify $0 compute charges**
  - Check OCI Console > Cost Analysis > Current charges
  - Confirm no running instances, sessions, or deployments
- [ ] **Verify resource cleanup**
  ```bash
  oci search resource structured-search \
    --query-text "query all resources where compartmentId = '$COMPARTMENT_OCID'" \
    --query 'data.items | length(@)' --raw-output
  ```
  Expected: 0 (or only the compartment itself)
- [ ] **Archive Terraform state**
  - Store `terraform.tfstate` and `.terraform.lock.hcl` in backup
  - These allow re-creation if needed
- [ ] **Update project documentation**
  - Mark OCI infrastructure as DECOMMISSIONED
  - Record final cost total
  - Update transition-signoff.md

---

## Recovery (if needed)

To re-create infrastructure from scratch:
```bash
cd oci/infrastructure/terraform
terraform init
terraform plan
terraform apply
```

Estimated time: 15-20 minutes to provision all resources.

---

*Checklist created: 2026-03-07*
