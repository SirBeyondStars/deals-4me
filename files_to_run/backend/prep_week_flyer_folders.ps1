param(
    # "current"  -> create just the next week after the latest existing one
    # "both"     -> create the next two weeks after the latest existing one
    # "next"     -> treated same as "current" here
    [ValidateSet("current","next","both")]
    [string]$Mode = "both"
)

$ErrorActionPreference = "Stop"

# ----------------- Paths -----------------
# Script is in: deals-4me\files_to_run\backend
# Project root : deals-4me
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$flyersRoot  = Join-Path $projectRoot "flyers"

Write-Host "Deals-4Me: Prep Week Flyer Folders" -ForegroundColor Cyan
Write-Host "project_root : $projectRoot"
Write-Host "flyers_root  : $flyersRoot"
Write-Host ""

# ----------------- Store list -----------------
$stores = @(
    "aldi",
    "big_y",
    "hannaford",
    "market_basket",
    "price_chopper_market_32",
    "pricerite",
    "roche_bros",
    "shaws",
    "sprouts",
    "stop_and_shop_ct",
    "stop_and_shop_mari",
    "trucchis",
    "wegmans",
    "whole_foods"
)

Write-Host "Stores configured for flyer prep:" -ForegroundColor Yellow
foreach ($s in $stores) { Write-Host " - $s" }
Write-Host ""

# ----------------- Figure out latest week (from sample store) -----------------
$sampleStore = $stores[0]                  # "aldi"
$sampleRoot  = Join-Path $flyersRoot $sampleStore

$existingWeeks = @()

if (Test-Path $sampleRoot) {
    Get-ChildItem -Path $sampleRoot -Directory |
        Where-Object { $_.Name -match '^week(\d{1,2})$' } |
        ForEach-Object {
            $num = [int]$matches[1]
            if ($num -ge 1 -and $num -le 99) {
                $existingWeeks += $num
            }
        }
}

[int]$latestWeek = 0
if ($existingWeeks.Count -gt 0) {
    $latestWeek = ($existingWeeks | Measure-Object -Maximum).Maximum
}

Write-Host "Latest existing week in '$sampleStore' = $latestWeek"

# ----------------- Decide which NEW weeks to create -----------------
if ($latestWeek -eq 0) {
    # No folders yet -> start at week01
    $next1 = 1
} else {
    $next1 = $latestWeek + 1
}
if ($next1 -gt 52) { $next1 = 1 }

$next2 = $next1 + 1
if ($next2 -gt 52) { $next2 = 1 }

Write-Host "Next week candidates: $next1 and $next2"
Write-Host ""

$weeksToCreate = @()

switch ($Mode.ToLower()) {
    "current" {
        $weeksToCreate += ("week{0:D2}" -f $next1)
    }
    "next" {
        $weeksToCreate += ("week{0:D2}" -f $next1)
    }
    "both" {
        $weeksToCreate += ("week{0:D2}" -f $next1)
        $weeksToCreate += ("week{0:D2}" -f $next2)
    }
}

if (-not $weeksToCreate -or $weeksToCreate.Count -eq 0) {
    Write-Error "No weeks were selected to create. Mode='$Mode', latestWeek='$latestWeek'."
    return
}

Write-Host "Weeks to create:"
foreach ($w in $weeksToCreate) { Write-Host " - $w" }
Write-Host ""

# ----------------- Work out the GUTS template -----------------
# Default template if nothing exists yet:
$subFolders = @("ocr", "raw_json", "raw_pdf", "raw_png", "snips")

if ($latestWeek -gt 0) {
    $templateWeekName = "week{0:D2}" -f $latestWeek
    $templateWeekDir  = Join-Path $sampleRoot $templateWeekName

    if (Test-Path $templateWeekDir) {
        $found = Get-ChildItem -Path $templateWeekDir -Directory |
                 Select-Object -ExpandProperty Name
        if ($found -and $found.Count -gt 0) {
            $subFolders = $found
        }
    }
}

Write-Host "Subfolder template (from $sampleStore/week$('{0:D2}' -f $latestWeek)):"
Write-Host "  $($subFolders -join ', ')"
Write-Host ""

# ----------------- Creation loop (stores + weeks + guts) -----------------
foreach ($store in $stores) {
    $storeRoot = Join-Path $flyersRoot $store
    if (-not (Test-Path $storeRoot)) {
        Write-Host "Creating store folder: $storeRoot"
        New-Item -ItemType Directory -Force -Path $storeRoot | Out-Null
    }

    foreach ($weekName in $weeksToCreate) {
        $weekDir = Join-Path $storeRoot $weekName
        if (-not (Test-Path $weekDir)) {
            Write-Host "  Creating week folder: $store/$weekName"
            New-Item -ItemType Directory -Force -Path $weekDir | Out-Null
        }
        else {
            Write-Host "  Verified existing folder: $store/$weekName"
        }

        # Create/verify guts
        foreach ($sub in $subFolders) {
            $subDir = Join-Path $weekDir $sub
            if (-not (Test-Path $subDir)) {
                Write-Host "    Creating subfolder: $store/$weekName/$sub"
                New-Item -ItemType Directory -Force -Path $subDir | Out-Null
            }
            else {
                Write-Host "    Verified subfolder: $store/$weekName/$sub"
            }
        }
    }
}

Write-Host ""
Write-Host "All requested flyer-week folders created / verified." -ForegroundColor Green
