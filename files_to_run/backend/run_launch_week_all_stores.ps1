# --- run_launch_week_all_stores.ps1 ---
# Purpose: OCR AUTO + Ingest/Parse for all launch stores (no admin tool)
# Run from anywhere.

$ErrorActionPreference = "Stop"

$project = "C:\Users\jwein\OneDrive\Desktop\deals-4me"
Set-Location $project

$week   = "wk_20251228"   # <-- CHANGE THIS WEEK EACH RUN
$region = "NE"

# IMPORTANT: edit this list to match your actual 10ish launch stores
$stores = @(
  "whole_foods",
  "aldi",
  "shaws",
  "market_basket",
  "stop_and_shop_mari",
  "stop_and_shop_ct",
  "wegmans",
  "roche_bros",
  "hannaford",
  "big_y",
  "price_chopper",
  "pricerite",
  "trucchis"
)

$missing = $launchStores | Where-Object { $allStores -notcontains $_ }
if ($missing.Count -gt 0) {
  Write-Host "[WARN] Launch stores not found under $regionRoot" -ForegroundColor Yellow
  $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}


$logRoot = Join-Path $project "flyers\logs\launch_runs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$logFile = Join-Path $logRoot ("launch_run_" + $week + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

Start-Transcript -Path $logFile -Append

Write-Host ""
Write-Host "=== LAUNCH WEEK PIPELINE ===" -ForegroundColor Cyan
Write-Host "Week:   $week"
Write-Host "Region: $region"
Write-Host "Stores: $($stores -join ', ')"
Write-Host ""

$results = @()

foreach ($store in $stores) {

  $weekDir = Join-Path $project ("flyers\{0}\{1}\{2}" -f $region, $store, $week)
  if (!(Test-Path $weekDir)) {
    Write-Host "[SKIP] Missing week folder: $weekDir" -ForegroundColor DarkYellow
    $results += [PSCustomObject]@{ store=$store; status="SKIP"; note="Missing week folder" }
    continue
  }

  try {
    Write-Host ""
    Write-Host "----- $store : OCR AUTO -----" -ForegroundColor Cyan
    python ".\files_to_run\backend\ocr_week_auto.py" $store --week $week --region $region
    if ($LASTEXITCODE -ne 0) { throw "OCR failed (exit $LASTEXITCODE)" }

    Write-Host "----- $store : INGEST (parse/export) -----" -ForegroundColor Cyan
    python ".\files_to_run\backend\ingest_store_week.py" --store $store --week $week --region $region --ocr auto
    if ($LASTEXITCODE -ne 0) { throw "Ingest failed (exit $LASTEXITCODE)" }

    $results += [PSCustomObject]@{ store=$store; status="OK"; note="" }

  } catch {
    Write-Host "[FAIL] $store : $($_.Exception.Message)" -ForegroundColor Yellow
    $results += [PSCustomObject]@{ store=$store; status="FAIL"; note=$_.Exception.Message }
    continue
  }
}

Write-Host ""
Write-Host "=== FINAL SUMMARY ($week / $region) ===" -ForegroundColor Green
$results | Format-Table -AutoSize

Write-Host ""
Write-Host "Log written to: $logFile" -ForegroundColor Yellow
Stop-Transcript
