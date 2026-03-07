# Quick cost check script — uses ConvertFrom-Json (no JMESPath issues)
$OCI = "C:\oci-env\Scripts\oci.exe"
$BUDGET_ID = "ocid1.budget.oc1.sa-saopaulo-1.amaaaaaa6dlb45iavwczk6i5qmhd4kjsd3f535r4r2kepndwbamxz4wo3ufa"
$COMP_ID = "ocid1.compartment.oc1..aaaaaaaa7uh2lfpsc6qf73g7zalgbr262a2v6veb4lreykqn57gtjvoojeuq"
$ADW_ID = "ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"

Write-Host "`n=== BUDGET ===" -ForegroundColor Cyan
$b = & $OCI budgets budget budget get --budget-id $BUDGET_ID | ConvertFrom-Json
Write-Host "Name:          $($b.data.'display-name')"
Write-Host "Monthly Limit: `$$($b.data.amount)"
Write-Host "Actual Spend:  $($b.data.'actual-spend')"
Write-Host "Forecast:      $($b.data.'forecasted-spend')"
Write-Host "State:         $($b.data.'lifecycle-state')"
Write-Host "Alert Rules:   $($b.data.'alert-rule-count')"

Write-Host "`n=== ALERT RULES ===" -ForegroundColor Cyan
$alerts = & $OCI budgets alert-rule list --budget-id $BUDGET_ID | ConvertFrom-Json
foreach ($r in $alerts.data) {
    Write-Host "  $($r.'display-name') | Threshold: $($r.threshold)% | Type: $($r.type) | State: $($r.'lifecycle-state')"
}

Write-Host "`n=== ADW STATUS ===" -ForegroundColor Cyan
$adw = & $OCI db autonomous-database get --autonomous-database-id $ADW_ID | ConvertFrom-Json
Write-Host "Name:      $($adw.data.'display-name')"
Write-Host "State:     $($adw.data.'lifecycle-state')"
Write-Host "ECPUs:     $($adw.data.'compute-count')"
Write-Host "Storage:   $($adw.data.'data-storage-size-in-tbs') TB"
Write-Host "Free Tier: $($adw.data.'is-free-tier')"

Write-Host "`n=== BUCKETS ===" -ForegroundColor Cyan
$ns = (& $OCI os ns get | ConvertFrom-Json).data
$buckets = (& $OCI os bucket list --compartment-id $COMP_ID --namespace $ns | ConvertFrom-Json).data
foreach ($bkt in $buckets) {
    Write-Host "  $($bkt.name) | Tier: $($bkt.'storage-tier')"
}

Write-Host "`n=== VAULT ===" -ForegroundColor Cyan
$vaults = (& $OCI kms management vault list --compartment-id $COMP_ID | ConvertFrom-Json).data
foreach ($v in $vaults) {
    Write-Host "  $($v.'display-name') | State: $($v.'lifecycle-state') | Type: $($v.'vault-type')"
}

Write-Host "`n=== COST SUMMARY ===" -ForegroundColor Yellow
Write-Host "ADW (STOPPED):     ~`$0/hr (storage only ~`$0.10/hr)"
Write-Host "Data Flow pool:    `$0 (min=0, idle)"
Write-Host "Object Storage:    pay-per-GB/month (~`$0.12/GB)"
Write-Host "Vault:             Free (DEFAULT type)"
Write-Host "DS Notebook:       Not created (disabled)"
Write-Host ""
Write-Host "** ADW is STOPPED = minimal cost. Start only when needed. **" -ForegroundColor Green
