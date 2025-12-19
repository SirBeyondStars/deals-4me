# ==============================================================================
# Deals-4Me Mini Admin
# Automates OCR, folder creation, log review & all-store reprocessing
# ==============================================================================

function Get-WeekList {
    param($root = "flyers")
    if (-not (Test-Path $root)) { return @() }
    Get-ChildItem $root -Directory |
        Where-Object { $_.Name -match '^\d{6}$' } |
        Select-Object -ExpandProperty Name |
        Sort-Object
}

function Get-StoreSlugs {
    param($week)
    $path = Join-Path "flyers" $week
    if (-not (Test-Path $path)) { return @() }
    Get-ChildItem $path -Directory |
        Where-Object { $_.Name -notin @("_inbox","logs") } |
        Select-Object -ExpandProperty Name |
        Sort-Object
}

function Show-Menu {
    param($weekNow)

    Clear-Host
    Write-Host ""
    Write-Host "=== Deals-4Me Mini Admin ===" -ForegroundColor Cyan
    Write-Host "Current Week (from latest folder): $weekNow"
    Write-Host ""
    Write-Host "1) Process snips (OCR + upload) for a store/week"
    Write-Host "2) Create new week folder for a store"
    Write-Host "3) Re-run OCR for a store/week"
    Write-Host "4) View recent logs"
    Write-Host "5) Re-run OCR for ALL stores (this week)"
    Write-Host "0) Exit"
    return Read-Host "Choose an option"
}

function Select-FromList {
    param(
        [string]$Prompt,
        [string[]]$Items
    )
    if ($Items.Count -eq 0) { return $null }

    Write-Host ""
    for ($i = 0; $i -lt $Items.Count; $i++) {
        Write-Host "$($i+1)) $($Items[$i])"
    }
    $choice = Read-Host "$Prompt"
    if ($choice -match '^\d+$' -and $choice -ge 1 -and $choice -le $Items.Count) {
        return $Items[$choice-1]
    }
    return $null
}

# ---------------------------------------------------------------
# MENU ACTIONS
# ---------------------------------------------------------------

function Action-ProcessSnips {
    $weeks = Get-WeekList
    $week = Select-FromList "Select week" $weeks
    if (-not $week) { return }

    $stores = Get-StoreSlugs $week
    $store = Select-FromList "Select store" $stores
    if (-not $store) { return }

    Write-Host "`n🔄 Running OCR + Upload for $store ($week)"
    python .\scripts\extract_flyer_text.py --store $store --week $week
    Pause
}

function Action-CreateWeekFolder {
    $stores = Get-StoreSlugs (Get-WeekList | Select-Object -Last 1)
    $store = Select-FromList "Select store" $stores
    if (-not $store) { return }

    $newWeek = Read-Host "Enter new WEEK (e.g. 102625)"
    $path = Join-Path "flyers" $newWeek
    $path = Join-Path $path $store

    if (!(Test-Path $path)) {
        New-Item -ItemType Directory -Force -Path (Join-Path "flyers" $newWeek)
        New-Item -ItemType Directory -Force -Path $path
        Write-Host "✅ Created $path"
    }
    else {
        Write-Host "⚠️ Folder already exists."
    }
    Pause
}

function Action-RerunOCR {
    $weeks = Get-WeekList
    $week = Select-FromList "Select week" $weeks
    if (-not $week) { return }

    $stores = Get-StoreSlugs $week
    $store = Select-FromList "Select store" $stores
    if (-not $store) { return }

    Write-Host "`n🔄 Re-running OCR for $store ($week)"
    python .\scripts\extract_flyer_text.py --store $store --week $week
    Pause
}

function Action-ViewLogs {
    $logFolder = "flyers\logs"
    if (!(Test-Path $logFolder)) { Write-Host "No logs found."; Pause; return }

    Write-Host "`n📝 Recent Logs:"
    Get-ChildItem $logFolder -File | Sort-Object LastWriteTime -Descending | Select-Object -First 10
    Pause
}

function Action-RerunAllForWeek {
    $week = (Get-WeekList | Select-Object -Last 1)
    Write-Host "`n🔁 Processing ALL stores for Week $week"
    $stores = Get-StoreSlugs $week

    foreach ($s in $stores) {
        Write-Host "`n➡️  $s"
        python .\scripts\extract_flyer_text.py --store $s --week $week
    }
    Pause
}

# ---------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------

while ($true) {
    $weekNow = (Get-WeekList | Select-Object -Last 1)
    $opt = Show-Menu $weekNow

    switch ($opt) {
        "1" { Action-ProcessSnips }
        "2" { Action-CreateWeekFolder }
        "3" { Action-RerunOCR }
        "4" { Action-ViewLogs }
        "5" { Action-RerunAllForWeek }
        "0" { break }
        default { Write-Host "Invalid option." -ForegroundColor Yellow }
    }
}
