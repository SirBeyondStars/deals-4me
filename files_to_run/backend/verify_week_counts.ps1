# files_to_run/backend/verify_week_counts.ps1
# Purpose:
#   Verify a week is "complete enough" by checking counts per store (PDF/PNG/TXT/CSV)
#
# Usage:
#   pwsh -NoProfile -ExecutionPolicy Bypass -File "files_to_run\backend\verify_week_counts.ps1" -Region NE -WeekCode wk_20260111 -Stage ocr

param(
  [Parameter(Mandatory = $true)]
  [string]$Region,

  [Parameter(Mandatory = $true)]
  [string]$WeekCode,

  [ValidateSet("ingest","ocr","parse")]
  [string]$Stage = "ocr",

  [string[]]$Stores = @(),

  [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -------------------------
# Console helpers (fallback)
# -------------------------
function Write-Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host $m -ForegroundColor Gray }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }
function Write-Err  { param([string]$m) Write-Host $m -ForegroundColor Red }

function Get-ProjectRootLocal {
  return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-FileCountSafeLocal {
  param([string]$Root, [string]$Pattern)
  try { return @(Get-ChildItem -Path $Root -Recurse -File -Filter $Pattern -ErrorAction SilentlyContinue).Count }
  catch { return 0 }
}

# -------------------------
# Load shared rules (library)
# -------------------------
$ProjectRoot = Get-ProjectRootLocal
$RulesPath   = Join-Path $PSScriptRoot "store_week_rules.ps1"
if (!(Test-Path $RulesPath)) { throw "store_week_rules.ps1 not found: $RulesPath" }
. $RulesPath

# -------------------------
# Normalize inputs
# -------------------------
$RegionNorm  = Normalize-Region -Region $Region
$WeekCodeNorm = $WeekCode.Trim().ToLowerInvariant()

if (-not (Test-WeekCode -WeekCode $WeekCodeNorm)) {
  throw "Invalid WeekCode '$WeekCode' (expected wk_YYYYMMDD)."
}

if ([string]::IsNullOrWhiteSpace($Stage)) { $Stage = "ocr" }

# stores list
$StoresFinal = @()
if ($Stores -and $Stores.Count -gt 0) {
  $StoresFinal = $Stores
} else {
  $StoresFinal = @(Get-CanonicalStores -Region $RegionNorm)
}

if (-not $StoresFinal -or $StoresFinal.Count -eq 0) {
  throw "No stores resolved for region '$RegionNorm'."
}

Write-Host ""
Write-Info "=== Verify Week / Counts ==="
Write-Note "ProjectRoot: $ProjectRoot"
Write-Note "Region     : $RegionNorm"
Write-Note "Week       : $WeekCodeNorm"
Write-Note "Stage      : $Stage"
Write-Note ("Stores     : {0}" -f ($StoresFinal -join ", "))
Write-Host ""

# -------------------------
# Expectations by stage
# -------------------------
$expectTxt = $false
$expectCsv = $false
switch ($Stage) {
  "ingest" { $expectTxt = $false; $expectCsv = $false }
  "ocr"    { $expectTxt = $true;  $expectCsv = $false }
  "parse"  { $expectTxt = $true;  $expectCsv = $true  }
}

$failCount = 0
$warnCount = 0

$fmt = "{0,-18} {1,6} {2,6} {3,6} {4,6}  {5,-7}  {6}"
Write-Host ($fmt -f "Store", "PDF", "PNG", "TXT", "CSV", "Status", "Notes")
Write-Host ("-" * 110)

foreach ($s in $StoresFinal) {
  $root = Get-StoreWeekRoot -Region $RegionNorm -WeekCode $WeekCodeNorm -Store $s -ProjectRoot $ProjectRoot

  if (!(Test-Path $root)) {
    $failCount++
    Write-Host ($fmt -f $s, "-", "-", "-", "-", "FAIL", "Root missing: $root")
    continue
  }

  $pdf = Get-FileCountSafeLocal -Root $root -Pattern "*.pdf"
  $png = Get-FileCountSafeLocal -Root $root -Pattern "*.png"
  $txt = Get-FileCountSafeLocal -Root $root -Pattern "*.txt"
  $csv = Get-FileCountSafeLocal -Root $root -Pattern "*.csv"

  $notes = @()
  $status = "OK"

  if (($pdf + $png) -eq 0) {
    $status = "FAIL"
    $notes += "No PDF/PNG"
  }

  if ($expectTxt -and $txt -eq 0) {
    if ($status -ne "FAIL") { $status = "WARN" }
    $notes += "Missing TXT"
  }

  if ($expectCsv -and $csv -eq 0) {
    if ($status -ne "FAIL") { $status = "WARN" }
    $notes += "Missing CSV"
  }

  if ($status -eq "FAIL") { $failCount++ }
  elseif ($status -eq "WARN") { $warnCount++ }

  Write-Host ($fmt -f $s, $pdf, $png, $txt, $csv, $status, ($notes -join "; "))
}

Write-Host ""
Write-Info ("Summary: FAIL={0} WARN={1}" -f $failCount, $warnCount)

if ($failCount -gt 0) { Write-Err "Verification FAILED."; exit 2 }

if ($warnCount -gt 0) {
  if ($Strict) { Write-Err "Warnings present and -Strict set."; exit 2 }
  Write-Warn "Warnings present."
  exit 1
}

Write-Ok "Verification OK."
exit 0
