# Stop all stoppable OCI resources to save costs
# Usage: powershell -File stop-infra.ps1

$ErrorActionPreference = "Stop"
$OCI = "C:\oci-env\Scripts\oci.exe"

# Resource OCIDs (from Terraform output)
$ADW_OCID = "ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"
$COMPARTMENT_OCID = "ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"

Write-Host "=== Stopping OCI Infrastructure ===" -ForegroundColor Yellow

# 1. Stop ADW (zero CPU cost, storage only)
Write-Host "[1/2] Stopping Autonomous Data Warehouse..." -ForegroundColor Cyan
& $OCI db autonomous-database stop --autonomous-database-id $ADW_OCID --wait-for-state STOPPED --wait-interval-seconds 15
Write-Host "  ADW: STOPPED" -ForegroundColor Green

# 2. Check and deactivate Model Deployments (if any)
Write-Host "[2/2] Checking Model Deployments..." -ForegroundColor Cyan
$deployments = & $OCI data-science model-deployment list --compartment-id $COMPARTMENT_OCID --lifecycle-state ACTIVE --query "data[*].id" --raw-output 2>$null
if ($deployments -and $deployments -ne "[]") {
    Write-Host "  Deactivating active deployments..."
    $ids = $deployments | ConvertFrom-Json
    foreach ($dep_id in $ids) {
        Write-Host "  Deactivating: $dep_id"
        & $OCI data-science model-deployment deactivate --model-deployment-id $dep_id
    }
} else {
    Write-Host "  No active deployments found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== All resources stopped ===" -ForegroundColor Green
Write-Host "ADW:            STOPPED (zero CPU cost)"
Write-Host "Notebook:       Not created (free tier)"
Write-Host "Data Flow:      On-demand (no idle cost)"
Write-Host "Object Storage: Always available"
