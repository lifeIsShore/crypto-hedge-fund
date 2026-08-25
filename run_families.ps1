$families = @("db_regime", "pead", "earnings", "crosssectional", "acceleration", "target_refinement")
foreach ($f in $families) {
    Write-Host "========================================"
    Write-Host " RUNNING FEATURE FAMILY: $f"
    Write-Host "========================================"
    python before-go-live/better-alpha/gate2_run.py --family $f --n-seeds 3 --force
}
Write-Host "All family tests completed!"
