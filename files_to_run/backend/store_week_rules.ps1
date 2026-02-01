# files_to_run/backend/store_week_rules.ps1
# Shared backend helper library (dot-source only)
# IMPORTANT:
#   - No top-level param() block
#   - No code that runs on load
#   - Only function definitions

Set-StrictMode -Version Latest

# -------------------------
# Normalizers / validators
# -------------------------

function Normalize-Region {
  param([string]$Region = "NE")

  if ([string]::IsNullOrWhiteSpace($Region)) { return "NE" }

  $r = $Region.Trim()

  # Allow numeric menu choices
  switch -Regex ($r) {
    '^\s*1\s*$' { return "NE" }
    '^\s*2\s*$' { return "MIDATL" }
  }

  # Normalize common spellings
  $r = $r.ToUpperInvariant()
  $r = $r -replace '\s+', ''   # "MID ATL" -> "MIDATL"
  $r = $r -replace '_', ''     # "MID_ATL" -> "MIDATL"
  $r = $r -replace '-', ''     # "MID-ATL" -> "MIDATL"

  if ($r -eq "MIDATLANTIC") { $r = "MIDATL" }

  return $r
}

function Normalize-WeekCode {
  param([string]$WeekCode)

  if ([string]::IsNullOrWhiteSpace($WeekCode)) { return "" }

  $w = $WeekCode.Trim().ToLowerInvariant()

  # Allow plain digits "YYYYMMDD"
  if ($w -match '^\d{8}$') { return ("wk_{0}" -f $w) }

  # Tolerate "wk-YYYYMMDD" / "wk YYYYMMDD"
  $w = $w -replace '^wk[\s\-_]*', 'wk_'

  return $w
}

function Test-WeekCode {
  param([string]$WeekCode)
  $w = Normalize-WeekCode -WeekCode $WeekCode
  return ($w -match '^wk_\d{8}$')
}

function Parse-WeekCodeStartDate {
  param([Parameter(Mandatory = $true)][string]$WeekCode)

  $w = Normalize-WeekCode -WeekCode $WeekCode
  if ($w -notmatch '^wk_\d{8}$') {
    throw "Invalid week code '$WeekCode' (expected wk_YYYYMMDD or YYYYMMDD)"
  }

  $digits = $w.Substring(3)
  return [datetime]::ParseExact($digits, "yyyyMMdd", $null)
}

function Assert-WeekCodeIsSundayStart {
  param([Parameter(Mandatory = $true)][string]$WeekCode)

  $dt = Parse-WeekCodeStartDate -WeekCode $WeekCode
  if ($dt.DayOfWeek -ne [DayOfWeek]::Sunday) {
    throw ("Week code '{0}' resolves to {1:yyyy-MM-dd} which is a {2}. " +
           "Per Deals-4Me rule, week codes must be Sunday-start." -f (Normalize-WeekCode $WeekCode), $dt, $dt.DayOfWeek)
  }
}

function Get-CurrentWeekCode {
  # Sunday-start week code: wk_YYYYMMDD (Sunday date)
  $today = Get-Date
  $daysSinceSunday = [int]$today.DayOfWeek
  $sunday = $today.Date.AddDays(-1 * $daysSinceSunday)
  return ("wk_{0}" -f $sunday.ToString("yyyyMMdd"))
}

# -------------------------
# Project root + flyers root
# -------------------------

function Get-ProjectRoot {
  # Optional override: safe under StrictMode
  $override = $null
  if (Test-Path variable:script:D4M_PROJECT_ROOT) {
    $override = $script:D4M_PROJECT_ROOT
  }

  if ($override -and -not [string]::IsNullOrWhiteSpace("$override")) {
    $p = "$override".Trim()
    $flyers = Join-Path $p "flyers"
    if (-not (Test-Path -LiteralPath $flyers)) {
      throw "D4M_PROJECT_ROOT is set to '$p' but '$flyers' does not exist."
    }
    return $p
  }

  # Auto-detect by walking up from this rules file location
  $start = Resolve-Path -LiteralPath $PSScriptRoot
  $cur = $start.Path

  while ($true) {
    $flyers = Join-Path $cur "flyers"
    if (Test-Path -LiteralPath $flyers) { return $cur }

    $parent = Split-Path -Parent $cur
    if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $cur) {
      throw "Get-ProjectRoot could not find a 'flyers' folder by walking up from: $($start.Path)"
    }
    $cur = $parent
  }
}

function Get-FlyersRoot {
  param([string]$ProjectRoot = "")
  if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Get-ProjectRoot }
  return (Join-Path $ProjectRoot "flyers")
}

function Get-RegionRoot {
  param(
    [string]$Region = "NE",
    [string]$ProjectRoot = ""
  )

  $r = Normalize-Region -Region $Region
  return (Join-Path (Get-FlyersRoot -ProjectRoot $ProjectRoot) $r)
}

# -------------------------
# Region enable flags
# -------------------------

function Is-RegionEnabled {
  param([string]$Region = "NE")

  $r = Normalize-Region -Region $Region
  switch ($r) {
    "NE"     { return $true }
    "MIDATL" { return $true }  # Keep true while you're building MIDATL
    default  { return $false }
  }
}

# -------------------------
# Stores
# -------------------------

function Get-CanonicalStores {
  param([string]$Region = "NE")

  $r = Normalize-Region -Region $Region

  if (-not (Is-RegionEnabled -Region $r)) {
    throw "Region '$r' is not enabled yet. Enable it in Is-RegionEnabled() before creating week folders."
  }

  switch ($r) {

    "NE" {
      return @(
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
    }

    "MIDATL" {
      return @(
        "shoprite",
        "acme",
        "foodtown",
        "tops",
        "h_mart",
        "the_fresh_grocer",
        "supremo",
        "99_ranch_market",
        "hannaford",

        "aldi",
        "wegmans",
        "whole_foods",

        "price_chopper",
        "pricerite"
      )
    }

    default { throw "No stores defined for region '$r'." }
  }
}

# -------------------------
# Paths
# -------------------------

function Get-StoreWeekRoot {
  param(
    [Parameter(Mandatory = $true)][string]$Region,
    [Parameter(Mandatory = $true)][string]$Store,
    [Parameter(Mandatory = $true)][string]$WeekCode,
    [string]$ProjectRoot = ""
  )

  if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Get-ProjectRoot }

  $r = Normalize-Region -Region $Region
  $w = Normalize-WeekCode -WeekCode $WeekCode

  if (-not (Test-WeekCode -WeekCode $w)) {
    throw "Invalid week code '$WeekCode' (expected wk_YYYYMMDD or YYYYMMDD)"
  }

  Assert-WeekCodeIsSundayStart -WeekCode $w

  return (Join-Path (Join-Path (Join-Path (Get-FlyersRoot -ProjectRoot $ProjectRoot) $r) $Store) $w)
}

function Test-StoreRootsExist {
  param(
    [Parameter(Mandatory = $true)][string]$Region,
    [string[]]$Stores = @(),
    [string]$ProjectRoot = ""
  )

  if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Get-ProjectRoot }
  $r = Normalize-Region -Region $Region

  if (-not $Stores -or $Stores.Count -eq 0) {
    $Stores = @(Get-CanonicalStores -Region $r)
  }

  $missing = @()
  foreach ($s in $Stores) {
    $storeRoot = Join-Path (Get-RegionRoot -Region $r -ProjectRoot $ProjectRoot) $s
    if (-not (Test-Path -LiteralPath $storeRoot)) { $missing += $s }
  }

  if ($missing.Count -gt 0) {
    throw ("Missing store root folder(s) under flyers\{0}: {1}" -f $r, ($missing -join ", "))
  }

  return $true
}

# -------------------------
# SINGLE SOURCE OF TRUTH: canonical week guts folders
# -------------------------

function Get-CanonicalWeekGutsFolders {
  param()

  # Canonical (minimal) week structure per store:
  #   raw_pdf, raw_png,
  #   manual_imports/(excel,csv),
  #   ocr_text_auto,
  #   exports/(csv,json),
  #   logs
  return @(
    "raw_pdf",
    "raw_png",

    "manual_imports",
    "manual_imports\excel",
    "manual_imports\csv",

    "ocr_text_auto",

    "exports",
    "exports\csv",
    "exports\json",

    "logs"
  )
}

function Ensure-WeekGuts {
  param(
    [Parameter(Mandatory = $true)][string]$StoreWeekRoot
  )

  if ([string]::IsNullOrWhiteSpace($StoreWeekRoot)) {
    throw "Ensure-WeekGuts: StoreWeekRoot is blank."
  }

  $folders = @(Get-CanonicalWeekGutsFolders)

  foreach ($f in $folders) {
    $p = Join-Path $StoreWeekRoot $f
    New-Item -ItemType Directory -Force -Path $p | Out-Null
  }

  return $true
}

function Ensure-WeekGutsForStores {
  param(
    [Parameter(Mandatory = $true)][string]$Region,
    [Parameter(Mandatory = $true)][string]$WeekCode,
    [string[]]$Stores = @(),
    [string]$ProjectRoot = ""
  )

  if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = Get-ProjectRoot }

  $r = Normalize-Region -Region $Region
  $w = Normalize-WeekCode -WeekCode $WeekCode

  if (-not $Stores -or $Stores.Count -eq 0) {
    $Stores = @(Get-CanonicalStores -Region $r)
  }

  Test-StoreRootsExist -Region $r -Stores $Stores -ProjectRoot $ProjectRoot | Out-Null

  foreach ($s in $Stores) {
    $root = Get-StoreWeekRoot -Region $r -Store $s -WeekCode $w -ProjectRoot $ProjectRoot
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    Ensure-WeekGuts -StoreWeekRoot $root | Out-Null
  }

  return $true
}