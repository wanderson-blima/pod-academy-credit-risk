# Start all stoppable OCI resources
# Usage: powershell -File start-infra.ps1

$ErrorActionPreference = "Stop"
$OCI = "C:\oci-env\Scripts\oci.exe"

# Resource OCIDs (from Terraform output)
$ADW_OCID = "ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"

Write-Host "=== Starting OCI Infrastructure ===" -ForegroundColor Yellow

# 1. Start ADW
Write-Host "[1/1] Starting Autonomous Data Warehouse..." -ForegroundColor Cyan
& $OCI db autonomous-database start --autonomous-database-id $ADW_OCID --wait-for-state AVAILABLE --wait-interval-seconds 15
Write-Host "  ADW: AVAILABLE" -ForegroundColor Green

Write-Host ""
Write-Host "=== All resources started ===" -ForegroundColor Green
Write-Host "ADW:            AVAILABLE"
Write-Host "Notebook:       Not created (free tier)"
Write-Host "Data Flow:      On-demand (no start needed)"
Write-Host "Object Storage: Always available"
