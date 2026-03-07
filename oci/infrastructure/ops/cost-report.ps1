# Quick cost check
# Usage: powershell -File cost-report.ps1

$OCI = "C:\oci-env\Scripts\oci.exe"

# Resource OCIDs (from Terraform output)
$TENANCY_OCID = "ocid1.tenancy.oc1..aaaaaaaahse5thvzinsvm7bkyrd3zravzao2i6kpfl4bfxkplbu7ppla5x5a"
$ADW_OCID = "ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"
$BUDGET_OCID = "ocid1.budget.oc1.sa-saopaulo-1.amaaaaaa6dlb45iavwczk6i5qmhd4kjsd3f535r4r2kepndwbamxz4wo3ufa"

Write-Host "=== OCI Cost Report ===" -ForegroundColor Yellow

# Budget status
Write-Host "`n--- Budget ---" -ForegroundColor Cyan
& $OCI budgets budget budget get --budget-id $BUDGET_OCID --query "data.{Name:""display-name"",Amount:amount,Actual:""actual-spend"",Forecast:""forecasted-spend"",State:""lifecycle-state""}" --output table

# ADW status
Write-Host "`n--- ADW Status ---" -ForegroundColor Cyan
& $OCI db autonomous-database get --autonomous-database-id $ADW_OCID --query "data.{State:""lifecycle-state"",ECPUs:""compute-count"",Storage_TB:""data-storage-size-in-tbs"",FreeTier:""is-free-tier""}" --output table

# Alert rules
Write-Host "`n--- Alert Rules ---" -ForegroundColor Cyan
& $OCI budgets budget alert-rule list --budget-id $BUDGET_OCID --query "data[*].{Name:""display-name"",Threshold:threshold,Type:type,State:""lifecycle-state""}" --output table
