# files_to_run/backend/run_admin.ps1
# Deals-4Me backend admin menu (final 1–5)
# Region-first + wk_YYYYMMDD

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- dot-source shared rules ---
. (Join-Path $PSScriptRoot "store_week_rules.ps1")

function Write-Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host $m -ForegroundColor Gray }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }

$ProjectRoot = Get-ProjectRoot -PSScriptRootPath $PSScriptRoot
$FlyersRoot  = Get-FlyersRoot -ProjectRoot $ProjectRoot

# --- Configure your underlying runner scripts here (paths are explicit) ---
$PrepScript      = Join-Path $ProjectRoot "files_to_run\backend\prep_week_flyer_folders.ps1"
$IngestPy        = Join-Path $ProjectRoot "files_to_run\backend\ingest_store_week.py"

# If you have specific export/verify scripts, point these at them:
$ExportScript    = Join-Path $ProjectRoot "files_to_run\backend\run_export_and_parse_offers.ps1"
$VerifyScript    = Join-Path $ProjectRoot "files_to_run\backend\verify_week_counts.ps1"

function Read-Choice {
  param([string]$Prompt, [string]$Default)
  $v = Read-Host "$Prompt [$Default]"
  if ([string]::IsNullOrWhiteSpace($v)) { return $Default }
  return $v.Trim()
}

function Ensure-File {
  param([string]$Path, [string]$Label)
  if (!(Test-Path $Path)) {
    throw "$Label not found: $Path"
  }
}

function Run-IngestForStores {
  param(
    [string]$Region,
    [string]$WeekCode,
    [ValidateSet("none","auto","full")]
    [string]$OcrMode
  )

  Ensure-File -Path $IngestPy -Label "Ingest script (Python)"
  $stores = Get-CanonicalStores -Region $Region
  if ($stores.Count -eq 0) {
    throw "No canonical stores defined for region '$Region'. Add them to store_week_rules.ps1 (Get-CanonicalStores)."
  }

  foreach ($s in $stores) {
    Write-Info "Running ingest for store: $s (Region=$Region Week=$WeekCode OCR=$OcrMode)"
    python $IngestPy --region $Region --store $s --week $WeekCode --ocr $OcrMode
    if ($LASTEXITCODE -ne 0) { throw "Ingest failed for store '$s' (exit $LASTEXITCODE)" }
  }

  Write-Ok "Completed ingest loop for region $Region week $WeekCode"
}

# --- Region selection (top-level) ---
Write-Info "=== Deals-4Me Admin ==="
Write-Note "ProjectRoot: $ProjectRoot"
Write-Note "FlyersRoot : $FlyersRoot"
Write-Host ""

$Region = Normalize-Region -Region (Read-Choice -Prompt "Select region" -Default "NE")

# Ensure region + canonical store folders exist
$null = Ensure-RegionAndStoresExist -ProjectRoot $ProjectRoot -Region $Region

# --- Week selection ---
$defaultWeek = Get-CurrentWeekCode
$WeekCode = Read-Choice -Prompt "Week code (wk_YYYYMMDD)" -Default $defaultWeek

if (-not (Test-WeekCode -WeekCode $WeekCode)) {
  throw "Invalid week code '$WeekCode'. Expected wk_YYYYMMDD."
}

if (-not (Test-WeekCodeIsSundayStart -WeekCode $WeekCode)) {
  Write-Warn "Week code '$WeekCode' is not a Sunday start. (We will proceed, but this is unusual.)"
}

Write-Host ""
Write-Ok "Region: $Region"
Write-Ok "Week  : $WeekCode"
Write-Host ""

# --- Ensure week folders exist for selected scope ---
Ensure-File -Path $PrepScript -Label "Prep week folder script"
pwsh -File $PrepScript -Mode current_week -Region $Region -ForDate (Parse-WeekCodeStartDate -WeekCode $WeekCode)

# --- Main menu loop ---
while ($true) {
  Write-Info "Menu (Final 1–5)"
  Write-Host "  1) Ingest Week (no OCR)"
  Write-Host "  2) OCR Week (AUTO)  ✅ default"
  Write-Host "  3) OCR Week (FULL passes)"
  Write-Host "  4) Export + Parse Offers"
  Write-Host "  5) Verify Week / Counts"
  Write-Host "  Q) Quit"
  Write-Host ""

  $choice = Read-Choice -Prompt "Choose option" -Default "2"

  if ($choice -match '^(q|quit)$') { break }

  switch ($choice) {
    "1" {
      Run-IngestForStores -Region $Region -WeekCode $WeekCode -OcrMode "none"
    }
    "2" {
      Run-IngestForStores -Region $Region -WeekCode $WeekCode -OcrMode "auto"
    }
    "3" {
      Run-IngestForStores -Region $Region -WeekCode $WeekCode -OcrMode "full"
    }
    "4" {
      if (Test-Path $ExportScript) {
        Write-Info "Running: Export + Parse Offers"
        pwsh -File $ExportScript -Region $Region -WeekCode $WeekCode
      } else {
        Write-Warn "Export script not found yet: $ExportScript"
        Write-Warn "Tell me your real export script name and I’ll wire it in."
      }
    }
    "5" {
      if (Test-Path $VerifyScript) {
        Write-Info "Running: Verify Week / Counts"
        pwsh -File $VerifyScript -Region $Region -WeekCode $WeekCode
      } else {
        Write-Warn "Verify script not found yet: $VerifyScript"
        Write-Warn "Tell me your real verify script name and I’ll wire it in."
      }
    }
    default {
      Write-Warn "Unknown option: $choice"
    }
  }

  Write-Host ""
}

Write-Ok "Exiting admin."
