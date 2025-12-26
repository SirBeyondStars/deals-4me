# files_to_run/backend/prep_week_flyer_folders.ps1
# Purpose:
#   Seed flyer folders for a given region and week using a locked-in week code:
#     wk_YYYYMMDD  (Sunday start date of the week)
#
# Folder layout (canonical):
#   flyers/<REGION>/<store_slug>/<wk_YYYYMMDD>/
#     raw_pdf/
#     raw_png/
#     raw_images/
#     processed/
#     ocr/
#     exports/
#     logs/
#     week_manifest.json
#
# Examples (run from project root):
#   pwsh -File ".\files_to_run\backend\prep_week_flyer_folders.ps1" -Mode current_week -Region NE
#   pwsh -File ".\files_to_run\backend\prep_week_flyer_folders.ps1" -Mode next_week   -Region NE
#   pwsh -File ".\files_to_run\backend\prep_week_flyer_folders.ps1" -Mode current_week -Region NE -ForDate "2025-12-28"
#
# Notes:
# - Week starts Sunday, ends Saturday
# - This script auto-creates the store folders under flyers/<REGION>/ using the canonical list
# - Omits non-stores like _inbox, logs, sprouts (per your instruction)

[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [ValidateSet("current_week","next_week")]
  [string]$Mode = "current_week",

  [Parameter(Mandatory = $false)]
  [ValidateNotNullOrEmpty()]
  [string]$Region = "NE",

  # Optional: any date within the week you want; script snaps back to Sunday start.
  [Parameter(Mandatory = $false)]
  [datetime]$ForDate = (Get-Date),

  # Project root (deals-4me). Default assumes script is in files_to_run/backend/
  [Parameter(Mandatory = $false)]
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host $m -ForegroundColor Gray }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }

function Get-SundayStart {
  param([datetime]$Date)
  # .NET DayOfWeek: Sunday=0 .. Saturday=6
  $delta = [int]$Date.DayOfWeek
  return $Date.Date.AddDays(-1 * $delta)
}

function Get-WeekCode {
  param([datetime]$SundayStart)
  return ("wk_" + $SundayStart.ToString("yyyyMMdd"))
}

# --- Canonical store list for NE (per your screenshot) ---
# Omits: _inbox, logs, sprouts
$StoreSlugs = @(
  "aldi",
  "big_y",
  "hannaford",
  "market_basket",
  "price_chopper",
  "pricerite",
  "roche_bros",
  "shaws",
  "stop_and_shop_ct",
  "stop_and_shop_mari",
  "trucchis",
  "wegmans",
  "whole_foods"
)

# --- Resolve paths ---
$flyersRoot = Join-Path $ProjectRoot "flyers"
if (!(Test-Path $flyersRoot)) {
  throw "Flyers root not found: $flyersRoot"
}

# Region folder: flyers/<REGION>
$regionRoot = Join-Path $flyersRoot $Region
New-Item -ItemType Directory -Force -Path $regionRoot | Out-Null

# Logs stay top-level (not per-region)
$logsRoot = Join-Path $flyersRoot "logs"
$taskLogs = Join-Path $logsRoot "tasks"
New-Item -ItemType Directory -Force -Path $taskLogs | Out-Null

# --- Determine week based on Mode + ForDate ---
$baseDate = $ForDate
if ($Mode -eq "next_week") { $baseDate = $baseDate.AddDays(7) }

$sundayStart = Get-SundayStart -Date $baseDate
$weekCode    = Get-WeekCode -SundayStart $sundayStart

Write-Info "ProjectRoot : $ProjectRoot"
Write-Info "FlyersRoot  : $flyersRoot"
Write-Ok   "Region      : $Region"
Write-Info "Mode        : $Mode"
Write-Info "ForDate     : $($ForDate.ToString('yyyy-MM-dd'))"
Write-Ok   ("Week Start  : " + $sundayStart.ToString("yyyy-MM-dd") + " (Sunday)")
Write-Ok   ("Week Code   : " + $weekCode)
Write-Note ""

# --- Ensure canonical store folders exist under flyers/<REGION>/ ---
foreach ($slug in $StoreSlugs) {
  $p = Join-Path $regionRoot $slug
  if (!(Test-Path $p)) {
    New-Item -ItemType Directory -Force -Path $p | Out-Null
    Write-Ok "Created store folder: flyers\$Region\$slug"
  }
}

Write-Info ("Stores in $Region (canonical): " + ($StoreSlugs -join ", "))
Write-Note ""

# --- “Guts” under each store/week folder ---
$weekSubfolders = @(
  "raw_pdf",
  "raw_png",
  "raw_images",
  "processed",
  "ocr",
  "exports",
  "logs"
)

$createdWeekFolders = 0
$alreadyExisted     = 0

foreach ($storeSlug in $StoreSlugs) {
  $storeRoot = Join-Path $regionRoot $storeSlug

  # flyers/<REGION>/<store_slug>/<wk_YYYYMMDD>/
  $weekRoot = Join-Path $storeRoot $weekCode

  if (!(Test-Path $weekRoot)) {
    New-Item -ItemType Directory -Force -Path $weekRoot | Out-Null
    $createdWeekFolders++
    Write-Ok "Created week folder: flyers\$Region\$storeSlug\$weekCode"
  } else {
    $alreadyExisted++
    Write-Warn "Week folder exists:  flyers\$Region\$storeSlug\$weekCode"
  }

  foreach ($sub in $weekSubfolders) {
    $p = Join-Path $weekRoot $sub
    if (!(Test-Path $p)) {
      New-Item -ItemType Directory -Force -Path $p | Out-Null
      Write-Note "  + $sub"
    }
  }

  # Per-store-week manifest (handy for sanity checks)
  $manifestPath = Join-Path $weekRoot "week_manifest.json"
  if (!(Test-Path $manifestPath)) {
    $manifest = [ordered]@{
      region       = $Region
      store_slug   = $storeSlug
      week_code    = $weekCode
      week_start   = $sundayStart.ToString("yyyy-MM-dd")
      created_utc  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
      mode         = $Mode
      structure    = $weekSubfolders
    } | ConvertTo-Json -Depth 5

    $manifest | Out-File -FilePath $manifestPath -Encoding UTF8
    Write-Note "  + week_manifest.json"
  }

  Write-Note ""
}

Write-Ok "Done."
Write-Info "Region               : $Region"
Write-Info "Week folders created : $createdWeekFolders"
Write-Info "Week folders existed : $alreadyExisted"
Write-Info "Week code            : $weekCode"

# Run log
$runLog = Join-Path $taskLogs ("prep_week_flyer_folders_" + $Region + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
@(
  "ProjectRoot=$ProjectRoot"
  "FlyersRoot=$flyersRoot"
  "Region=$Region"
  "Mode=$Mode"
  "ForDate=$($ForDate.ToString('yyyy-MM-dd'))"
  "WeekStart=$($sundayStart.ToString('yyyy-MM-dd'))"
  "WeekCode=$weekCode"
  "Stores=$($StoreSlugs -join ', ')"
  "CreatedWeekFolders=$createdWeekFolders"
  "ExistedWeekFolders=$alreadyExisted"
) | Out-File -FilePath $runLog -Encoding UTF8

Write-Ok "Log written: flyers\logs\tasks\$(Split-Path $runLog -Leaf)"
