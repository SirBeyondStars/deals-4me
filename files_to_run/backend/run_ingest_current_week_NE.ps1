# run_ingest_current_week_NE.ps1
# Purpose: one-shot wrapper to run export + ingest for the
# CURRENT ISO week for the NE region, across all stores.

$ErrorActionPreference = "Stop"

$backendDir  = $PSScriptRoot
$projectRoot = Split-Path $backendDir -Parent
$flyersRoot  = Join-Path $projectRoot "flyers"

function Get-CurrentIsoWeekNumber {
    $today    = Get-Date
    $calendar = [System.Globalization.CultureInfo]::InvariantCulture.Calendar
    $rule     = [System.Globalization.CalendarWeekRule]::FirstFourDayWeek
    $firstDay = [System.DayOfWeek]::Monday

    return $calendar.GetWeekOfYear($today, $rule, $firstDay)
}

$isoWeek   = Get-CurrentIsoWeekNumber
$weekCode  = ("week{0:D2}" -f $isoWeek)   # weekNN

Write-Host "Running export + ingest for the current week..." -ForegroundColor Cyan
Write-Host "Detected current ISO week: $isoWeek"
Write-Host "Using week code:          $weekCode"
Write-Host "Flyers root:              $flyersRoot"
Write-Host ""

$allScript = Join-Path $backendDir "run_export_and_ocr_all.ps1"
if (-not (Test-Path $allScript)) {
    Write-Host "ERROR: run_export_and_ocr_all.ps1 not found in $backendDir" -ForegroundColor Red
    exit 1
}

& $allScript -weekCode $weekCode -flyersRoot $flyersRoot

exit $LASTEXITCODE
