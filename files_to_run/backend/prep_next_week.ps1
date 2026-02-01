# files_to_run/backend/prep_next_week.ps1
# Purpose:
#   Prepare the next grocery week inside the EXISTING flyers structure.
#   Idempotent: safe to run multiple times.
#
# Canonical layout:
#   flyers\<REGION>\<STORE>\<WEEKCODE>\  (+ standard subfolders)

[CmdletBinding()]
param(
  # Region code like NE, MIDATL
  [Parameter(Mandatory = $false)]
  [string]$Region = "NE",

  # Date (yyyy-MM-dd) representing the Sunday start date for the week folder
  # If omitted, script uses the NEXT Sunday from today
  [Parameter(Mandatory = $false)]
  [string]$ForDate = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -------------------------
# Console helpers
# -------------------------
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

# -------------------------
# Idempotent directory creator
# -------------------------
function New-DirIfMissing {
  param([Parameter(Mandatory=$true)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    Write-Info "Created: $Path"
  }
}

# -------------------------
# Load shared rules (stores, paths, etc.)
# -------------------------
$RulesPath = Join-Path $PSScriptRoot "store_week_rules.ps1"
if (-not (Test-Path -LiteralPath $RulesPath)) {
  throw "store_week_rules.ps1 not found: $RulesPath"
}
. $RulesPath

# -------------------------
# Helpers
# -------------------------
function Resolve-TargetWeekCode {
  param([string]$ForDateText)

  if (-not [string]::IsNullOrWhiteSpace($ForDateText)) {
    # Expect yyyy-MM-dd
    try {
      $d = [datetime]::ParseExact($ForDateText.Trim(), "yyyy-MM-dd", $null)
      return ("wk_{0}" -f $d.ToString("yyyyMMdd"))
    } catch {
      throw "Invalid -ForDate '$ForDateText'. Expected yyyy-MM-dd (example: 2026-01-18)."
    }
  }

  # Default behavior: NEXT Sunday
  $today = Get-Date
  $daysUntilSunday = (7 - [int]$today.DayOfWeek) % 7
  if ($daysUntilSunday -eq 0) { $daysUntilSunday = 7 }
  $weekStart = $today.Date.AddDays($daysUntilSunday)

  return ("wk_{0}" -f $weekStart.ToString("yyyyMMdd"))
}

function Ensure-WeekGuts {
  param(
    [Parameter(Mandatory=$true)][string]$WeekRoot
  )

  # Top-level standard folders
  $rawPdf     = Join-Path $WeekRoot "raw_pdf"
  $rawPng     = Join-Path $WeekRoot "raw_png"
  $rawImages  = Join-Path $WeekRoot "raw_images"
  $snips      = Join-Path $WeekRoot "snips"
  $ocr        = Join-Path $WeekRoot "ocr"
  $exports    = Join-Path $WeekRoot "exports"
  $processed  = Join-Path $WeekRoot "processed"
  $logs       = Join-Path $WeekRoot "logs"

  New-DirIfMissing -Path $WeekRoot
  New-DirIfMissing -Path $rawPdf
  New-DirIfMissing -Path $rawPng
  New-DirIfMissing -Path $rawImages
  New-DirIfMissing -Path $snips
  New-DirIfMissing -Path $ocr
  New-DirIfMissing -Path $exports
  New-DirIfMissing -Path $processed
  New-DirIfMissing -Path $logs

  # OCR “guts” (common subfolders used by pipelines)
  $ocrPasses  = Join-Path $ocr "_passes"
  $ocrText    = Join-Path $ocr "text"
  $ocrJson    = Join-Path $ocr "json"
  New-DirIfMissing -Path $ocrPasses
  New-DirIfMissing -Path $ocrText
  New-DirIfMissing -Path $ocrJson

  # Exports “guts”
  $expDebugOffers = Join-Path $exports "_debug_offers"
  $expDebugPages  = Join-Path $exports "_debug_pages"
  $expCsv         = Join-Path $exports "csv"
  $expJson        = Join-Path $exports "json"
  New-DirIfMissing -Path $expDebugOffers
  New-DirIfMissing -Path $expDebugPages
  New-DirIfMissing -Path $expCsv
  New-DirIfMissing -Path $expJson

  # Manual imports “guts”
  $manualRoot = Join-Path $WeekRoot "manual_imports"
  $manualExcel = Join-Path $manualRoot "excel"
  $manualCsv   = Join-Path $manualRoot "csv"
  $manualNotes = Join-Path $manualRoot "notes"
  New-DirIfMissing -Path $manualRoot
  New-DirIfMissing -Path $manualExcel
  New-DirIfMissing -Path $manualCsv
  New-DirIfMissing -Path $manualNotes
}

# -------------------------
# Main
# -------------------------
try {
  # Normalize inputs (from rules file)
  $RegionNorm   = (Normalize-Region -Region $Region)
  $WeekCode     = (Resolve-TargetWeekCode -ForDateText $ForDate)
  $WeekCodeNorm = (Normalize-WeekCode -WeekCode $WeekCode)

  Write-Info ("ProjectRoot : {0}" -f (Get-ProjectRoot))
  Write-Info ("FlyersRoot  : {0}" -f (Get-FlyersRoot -ProjectRoot (Get-ProjectRoot)))


  if (-not (Test-WeekCode -WeekCode $WeekCodeNorm)) {
    throw "Computed invalid week code '$WeekCodeNorm'."
  }

  Write-Info "Starting prep_next_week (idempotent)"
  Write-Info "Region    : $RegionNorm"
  Write-Info "Target wk : $WeekCodeNorm"

  # Optional gate (only if present in rules)
  if (Get-Command Is-RegionEnabled -ErrorAction SilentlyContinue) {
    if (-not (Is-RegionEnabled -Region $RegionNorm)) {
      throw "Region '$RegionNorm' is currently disabled by Is-RegionEnabled."
    }
  }

  $stores = @(Get-CanonicalStores -Region $RegionNorm)
  if (-not $stores -or $stores.Count -eq 0) {
    throw "No stores defined for region '$RegionNorm'. (Check Get-CanonicalStores in store_week_rules.ps1.)"
  }

  foreach ($s in $stores) {
    $weekRoot = Get-StoreWeekRoot -Region $RegionNorm -Store $s -WeekCode $WeekCodeNorm

    # Create full folder “guts”
    Ensure-WeekGuts -WeekRoot $weekRoot

    # week_manifest.json placeholder if missing
    $manifestPath = Join-Path $weekRoot "week_manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
      $manifest = [ordered]@{
        region      = $RegionNorm
        store       = $s
        week_code   = $WeekCodeNorm
        created_utc = [datetime]::UtcNow.ToString("o")
        notes       = ""
      } | ConvertTo-Json -Depth 6

      $manifest | Out-File -FilePath $manifestPath -Encoding UTF8
      Write-Info "Created: $manifestPath"
    }
  }

  Write-Ok "prep_next_week completed successfully (no duplicates created)."
  exit 0
}
catch {
  Write-Err $_.Exception.Message
  exit 2
}
