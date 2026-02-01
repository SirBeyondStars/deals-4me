# files_to_run/backend/run_export_and_parse_offers.ps1
# Option 2:
# - Convert manual_imports\excel\*.xlsx -> manual_imports\csv\*.csv
# - Merge per-store CSVs into ONE region/week CSV

param(
  [Parameter(Mandatory = $true)]
  [string]$Region,

  [Parameter(Mandatory = $true)]
  [string]$WeekCode,

  [string]$OutRoot = "",

  [switch]$Strict
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -------------------------
# Console helpers
# -------------------------
function Write-Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host $m -ForegroundColor Gray }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }
function Write-Err  { param([string]$m) Write-Host $m -ForegroundColor Red }

# -------------------------
# Local helpers
# -------------------------
function Get-ProjectRootLocal {
  return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Ensure-DirLocal {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Invoke-PythonLocal {
  param([string]$Path, [string[]]$ArgumentList)

  if (!(Test-Path $Path)) { throw "Python script not found: $Path" }

  Write-Note ("-> python `"{0}`" {1}" -f $Path, ($ArgumentList -join " "))
  python $Path @ArgumentList

  if ($LASTEXITCODE -ne 0) { throw "Python failed: $Path (exit $LASTEXITCODE)" }
}

# ✅ This is the helper you were looking for (and we use it everywhere in Step 2)
function Get-PropOrBlank {
  param(
    [Parameter(Mandatory = $true)] $Obj,
    [Parameter(Mandatory = $true)] [string]$Name
  )
  if ($null -eq $Obj) { return "" }
  if ($Obj.PSObject.Properties.Match($Name).Count -gt 0) {
    $v = $Obj.$Name
    if ($null -eq $v) { return "" }
    return [string]$v
  }
  return ""
}

function Find-StoreCsvLocal {
  param([string]$StoreWeekRoot)

  if (!(Test-Path $StoreWeekRoot)) { return $null }

  function Test-HasItemNameHeader {
    param([string]$CsvPath)
    try {
      $first = Get-Content -Path $CsvPath -TotalCount 1 -ErrorAction Stop
      return ($first -match '(?i)(^|,)\s*item_name\s*(,|$)')
    } catch {
      return $false
    }
  }

  # 1) HARD PREFERENCE: manual_imports\csv (most deterministic)
  $manualCsvDir = Join-Path $StoreWeekRoot "manual_imports\csv"
  if (Test-Path $manualCsvDir) {
    $manualHits = @(
      Get-ChildItem -Path $manualCsvDir -File -Filter "*.csv" -ErrorAction SilentlyContinue |
        Where-Object { Test-HasItemNameHeader $_.FullName } |
        Sort-Object LastWriteTime -Descending
    )
    if ($manualHits.Count -gt 0) { return $manualHits[0].FullName }
  }

  # 2) FALLBACK: search common export/output folders, but only accept "offer-like" names
  $candidatePaths = @(
    (Join-Path $StoreWeekRoot "exports"),
    (Join-Path $StoreWeekRoot "_exports"),
    (Join-Path $StoreWeekRoot "parsed"),
    (Join-Path $StoreWeekRoot "parse"),
    (Join-Path $StoreWeekRoot "output"),
    $StoreWeekRoot
  )

  $hits = @()
  foreach ($p in $candidatePaths) {
    if (Test-Path $p) {
      $hits += @(
        Get-ChildItem -Path $p -File -Recurse -ErrorAction SilentlyContinue |
          Where-Object {
            $_.Extension -ieq ".csv" -and
            $_.Name -notmatch '(?i)manifest|counts|debug_offers|_debug|raw'
          }
      )
    }
  }

  if (-not $hits -or $hits.Count -eq 0) { return $null }

  $offerHits = @(
    $hits |
      Where-Object { $_.Name -match '(?i)offers?|offer|deal|parsed|export' } |
      Where-Object { Test-HasItemNameHeader $_.FullName } |
      Sort-Object LastWriteTime -Descending
  )
  if ($offerHits.Count -gt 0) { return $offerHits[0].FullName }

  # 3) LAST RESORT: any CSV that still has item_name header
  $anyValid = @(
    $hits |
      Where-Object { Test-HasItemNameHeader $_.FullName } |
      Sort-Object LastWriteTime -Descending
  )
  if ($anyValid.Count -gt 0) { return $anyValid[0].FullName }

  return $null
}

# -------------------------
# Load shared rules
# -------------------------
$ProjectRoot = Get-ProjectRootLocal
$RulesPath   = Join-Path $PSScriptRoot "store_week_rules.ps1"
if (!(Test-Path $RulesPath)) { throw "store_week_rules.ps1 not found: $RulesPath" }
. $RulesPath

$RegionNorm   = (Normalize-Region -Region $Region)
$WeekCodeNorm = $WeekCode.Trim().ToLowerInvariant()
if (-not (Test-WeekCode -WeekCode $WeekCodeNorm)) { throw "Invalid WeekCode '$WeekCode' (expected wk_YYYYMMDD)." }

$stores = @(Get-CanonicalStores -Region $RegionNorm)
if (-not $stores -or $stores.Count -eq 0) { throw "No stores defined for region '$RegionNorm'." }

# -------------------------
# Output root
# -------------------------
if ([string]::IsNullOrWhiteSpace($OutRoot)) {
  $OutRoot = Join-Path $ProjectRoot (Join-Path "exports" (Join-Path $RegionNorm $WeekCodeNorm))
}
Ensure-DirLocal -Path $OutRoot
$outCsv = Join-Path $OutRoot ("offers_{0}_{1}.csv" -f $RegionNorm, $WeekCodeNorm)

# -------------------------
# Converter
# -------------------------
$ConverterPy = Join-Path $PSScriptRoot "convert_manual_excel_to_offers_csv.py"
if (!(Test-Path $ConverterPy)) {
  throw "Converter script not found: $ConverterPy"
}

Write-Host ""
Write-Info "=== Export + Parse Offers (Excel->CSV + Merge) ==="
Write-Note "ProjectRoot: $ProjectRoot"
Write-Note "Region     : $RegionNorm"
Write-Note "Week       : $WeekCodeNorm"
Write-Note "OutRoot    : $OutRoot"
Write-Note "OutCsv     : $outCsv"
Write-Host ""

# -------------------------
# Step 1: Convert manual Excel -> manual CSV per store
# -------------------------
foreach ($s in $stores) {
  $storeRoot = Get-StoreWeekRoot -Region $RegionNorm -Store $s -WeekCode $WeekCodeNorm
  $excelDir  = Join-Path $storeRoot "manual_imports\excel"
  $csvDir    = Join-Path $storeRoot "manual_imports\csv"
  Ensure-DirLocal -Path $csvDir

  if (!(Test-Path $excelDir)) { continue }

  $xlsxFiles = @(Get-ChildItem -Path $excelDir -File -Filter "*.xlsx" -ErrorAction SilentlyContinue)
  if (-not $xlsxFiles -or $xlsxFiles.Count -eq 0) { continue }

  foreach ($xf in $xlsxFiles) {
    $outStoreCsv = Join-Path $csvDir (($xf.BaseName) + ".csv")
    Write-Info ("Convert {0} -> {1}" -f $xf.FullName, $outStoreCsv)

    Invoke-PythonLocal -Path $ConverterPy -ArgumentList @(
      "--input",  $xf.FullName,
      "--output", $outStoreCsv,
      "--store",  $s,
      "--region", $RegionNorm,
      "--week",   $WeekCodeNorm
    )
  }
}

# -------------------------
# Step 2: Merge per-store CSVs into one region/week CSV
# -------------------------
$allRows        = New-Object System.Collections.Generic.List[object]
$missingStores  = New-Object System.Collections.Generic.List[string]
$perStoreCounts = @{}

foreach ($s in $stores) {
  $storeRoot = Get-StoreWeekRoot -Region $RegionNorm -Store $s -WeekCode $WeekCodeNorm
  $storeCsv  = Find-StoreCsvLocal -StoreWeekRoot $storeRoot

  if (-not $storeCsv) {
    $missingStores.Add($s) | Out-Null
    $perStoreCounts[$s] = 0
    Write-Warn ("Missing CSV for store: {0} (looked under {1})" -f $s, $storeRoot)
    continue
  }

  Write-Info ("Using CSV for {0}: {1}" -f $s, $storeCsv)

  $rows = @()
  try {
    $rows = @(Import-Csv -Path $storeCsv -ErrorAction Stop)
  } catch {
    $perStoreCounts[$s] = 0
    Write-Warn ("Failed to Import-Csv for store {0}: {1}" -f $s, $_.Exception.Message)
    continue
  }

  if (-not $rows -or $rows.Count -eq 0) {
    $perStoreCounts[$s] = 0
    Write-Warn ("CSV empty for store: {0}" -f $s)
    continue
  }

  # If item_name isn't present, this file is not usable for the merged output
  if ($rows[0].PSObject.Properties.Match("item_name").Count -eq 0) {
    $perStoreCounts[$s] = 0
    Write-Warn ("CSV for store {0} has no 'item_name' column; skipping: {1}" -f $s, $storeCsv)
    continue
  }

  $perStoreCounts[$s] = $rows.Count

  foreach ($r in $rows) {

    # Pull everything safely (blank if column missing)
    $itemName = Get-PropOrBlank -Obj $r -Name "item_name"

    # If a row somehow has no item_name, you can choose to skip it
    if ([string]::IsNullOrWhiteSpace($itemName)) {
      continue
    }

    $storeVal  = Get-PropOrBlank -Obj $r -Name "store"
    $regionVal = Get-PropOrBlank -Obj $r -Name "region"
    $weekVal   = Get-PropOrBlank -Obj $r -Name "week_code"

    $promoStart = Get-PropOrBlank -Obj $r -Name "promo_start"
    $promoEnd   = Get-PropOrBlank -Obj $r -Name "promo_end"

    $pctPrime    = Get-PropOrBlank -Obj $r -Name "percent_off_prime"
    $pctNonPrime = Get-PropOrBlank -Obj $r -Name "percent_off_nonprime"

    $salePrice = Get-PropOrBlank -Obj $r -Name "sale_price"

    $reviewReason = Get-PropOrBlank -Obj $r -Name "manual_review_reason"
    $sourceFile   = Get-PropOrBlank -Obj $r -Name "source_file"

    # Build unified row with guaranteed schema
    $h = [ordered]@{
      item_name            = $itemName
      store                = $storeVal
      region               = $regionVal
      week_code            = $weekVal
      promo_start          = $promoStart
      promo_end            = $promoEnd
      percent_off_prime    = $pctPrime
      percent_off_nonprime = $pctNonPrime
      sale_price           = $salePrice
      manual_review_reason = $reviewReason
      source_file          = $sourceFile
    }

    # Fill canonical defaults if blank
    if ([string]::IsNullOrWhiteSpace($h.store))     { $h.store     = $s }
    if ([string]::IsNullOrWhiteSpace($h.region))    { $h.region    = $RegionNorm }
    if ([string]::IsNullOrWhiteSpace($h.week_code)) { $h.week_code = $WeekCodeNorm }
    if ([string]::IsNullOrWhiteSpace($h.source_file)) { $h.source_file = (Split-Path $storeCsv -Leaf) }

    $allRows.Add([pscustomobject]$h) | Out-Null
  }
}

Write-Host ""
Write-Info "Store row counts:"
foreach ($k in ($perStoreCounts.Keys | Sort-Object)) {
  Write-Note ("  {0,-18} {1,6}" -f $k, $perStoreCounts[$k])
}

Write-Host ""
Write-Info ("Merged total rows: {0}" -f $allRows.Count)

if ($missingStores.Count -gt 0) {
  if ($Strict) {
    Write-Err ("Missing CSV for {0} store(s): {1}" -f $missingStores.Count, ($missingStores -join ", "))
    exit 2
  }
  Write-Warn ("Missing CSV for {0} store(s): {1}" -f $missingStores.Count, ($missingStores -join ", "))
}

if ($allRows.Count -eq 0) {
  Write-Err "No rows found to export. (No store CSVs were discovered / usable.)"
  exit 2
}

$allRows | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8
Write-Host ""
Write-Ok ("Wrote merged CSV: {0}" -f $outCsv)
exit 0
