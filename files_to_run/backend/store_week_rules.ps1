# files_to_run/backend/store_week_rules.ps1
# Single source of truth:
# - Week starts Sunday
# - Week code format: wk_YYYYMMDD (Sunday start date)
# - Region-first folder layout: flyers/<REGION>/<store_slug>/<wk_YYYYMMDD>/
# - Canonical NE store list

Set-StrictMode -Version Latest

function Get-SundayStart {
  param([datetime]$Date = (Get-Date))
  $delta = [int]$Date.DayOfWeek   # Sunday=0 .. Saturday=6
  return $Date.Date.AddDays(-1 * $delta)
}

function Get-WeekCode {
  param([datetime]$Date = (Get-Date))
  $sunday = Get-SundayStart -Date $Date
  return ("wk_" + $sunday.ToString("yyyyMMdd"))
}

function Get-CurrentWeekCode { return (Get-WeekCode -Date (Get-Date)) }
function Get-NextWeekCode    { return (Get-WeekCode -Date ((Get-Date).AddDays(7))) }

function Test-WeekCode {
  param([string]$WeekCode)
  if ([string]::IsNullOrWhiteSpace($WeekCode)) { return $false }
  return ($WeekCode -match '^wk_\d{8}$')
}

function Parse-WeekCodeStartDate {
  param([string]$WeekCode)
  if (-not (Test-WeekCode -WeekCode $WeekCode)) {
    throw "Invalid week code '$WeekCode'. Expected format: wk_YYYYMMDD"
  }
  $yyyymmdd = $WeekCode.Substring(3,8)
  return [datetime]::ParseExact($yyyymmdd, 'yyyyMMdd', $null).Date
}

function Test-WeekCodeIsSundayStart {
  param([string]$WeekCode)
  $d = Parse-WeekCodeStartDate -WeekCode $WeekCode
  return ($d.DayOfWeek -eq [System.DayOfWeek]::Sunday)
}

function Normalize-Region {
  param([string]$Region = "NE")
  if ([string]::IsNullOrWhiteSpace($Region)) { return "NE" }
  return $Region.Trim().ToUpperInvariant()
}

function Get-ProjectRoot {
  param([string]$PSScriptRootPath = $PSScriptRoot)
  # Assumes: .../deals-4me/files_to_run/backend/
  return (Resolve-Path (Join-Path $PSScriptRootPath "..\..")).Path
}

function Get-FlyersRoot {
  param([string]$ProjectRoot)
  return (Join-Path $ProjectRoot "flyers")
}

function Get-RegionRoot {
  param(
    [string]$ProjectRoot,
    [string]$Region = "NE"
  )
  $r = Normalize-Region -Region $Region
  return (Join-Path (Get-FlyersRoot -ProjectRoot $ProjectRoot) $r)
}

function Get-StoreRoot {
  param(
    [string]$ProjectRoot,
    [string]$Region,
    [string]$StoreSlug
  )
  return (Join-Path (Get-RegionRoot -ProjectRoot $ProjectRoot -Region $Region) $StoreSlug)
}

function Get-WeekRoot {
  param(
    [string]$ProjectRoot,
    [string]$Region,
    [string]$StoreSlug,
    [string]$WeekCode
  )
  return (Join-Path (Get-StoreRoot -ProjectRoot $ProjectRoot -Region $Region -StoreSlug $StoreSlug) $WeekCode)
}

function Get-CanonicalStores {
  param([string]$Region = "NE")
  $r = Normalize-Region -Region $Region

  if ($r -eq "NE") {
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

  # For future regions, return empty until you define them.
  return @()
}

function Ensure-RegionAndStoresExist {
  param(
    [string]$ProjectRoot,
    [string]$Region = "NE"
  )

  $flyersRoot = Get-FlyersRoot -ProjectRoot $ProjectRoot
  if (!(Test-Path $flyersRoot)) { throw "Flyers root not found: $flyersRoot" }

  $regionRoot = Get-RegionRoot -ProjectRoot $ProjectRoot -Region $Region
  New-Item -ItemType Directory -Force -Path $regionRoot | Out-Null

  $stores = Get-CanonicalStores -Region $Region
  foreach ($s in $stores) {
    $p = Join-Path $regionRoot $s
    if (!(Test-Path $p)) {
      New-Item -ItemType Directory -Force -Path $p | Out-Null
    }
  }

  return $stores
}
