$OCI = "C:\oci-env\Scripts\oci.exe"
$ADW_OCID = "ocid1.autonomousdatabase.oc1.sa-saopaulo-1.antxeljr6dlb45iaangy5wpt4wec6ymecn7gpfzxzkag4xnyevcwn2elxlrq"
$json = & $OCI db autonomous-database get --autonomous-database-id $ADW_OCID 2>&1
$data = $json | ConvertFrom-Json
Write-Host "ADW State:    $($data.data.'lifecycle-state')"
Write-Host "ADW ECPUs:    $($data.data.'compute-count')"
Write-Host "ADW FreeTier: $($data.data.'is-free-tier')"
Write-Host "ADW Storage:  $($data.data.'data-storage-size-in-tbs') TB"
