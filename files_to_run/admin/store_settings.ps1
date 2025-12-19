# store_settings.ps1
# Single source of truth for store list.

function Get-StoresRegistryPath {
    param([string]$ProjectRoot)

    $flyersRoot = Join-Path $ProjectRoot "flyers"
    return (Join-Path $flyersRoot "stores.json")
}

function Load-StoresRegistry {
    param([string]$ProjectRoot)

    $path = Get-StoresRegistryPath -ProjectRoot $ProjectRoot
    if (-not (Test-Path $path)) {
        throw "stores.json not found at $path"
    }
    return (Get-Content -Raw $path | ConvertFrom-Json)
}

function Save-StoresRegistry {
    param(
        [string]$ProjectRoot,
        $registry
    )
    $path = Get-StoresRegistryPath -ProjectRoot $ProjectRoot
    ($registry | ConvertTo-Json -Depth 10) | Set-Content -Path $path -Encoding UTF8
}

function Get-WeeklyActiveStores {
    param([string]$ProjectRoot)

    $reg = Load-StoresRegistry -ProjectRoot $ProjectRoot
    return $reg.stores | Where-Object { $_.weekly_active -eq $true } | Select-Object -ExpandProperty key
}

function Show-Stores {
    param([string]$ProjectRoot)

    $reg = Load-StoresRegistry -ProjectRoot $ProjectRoot
    $i = 0
    Write-Host ""
    foreach ($s in $reg.stores) {
        $flag = if ($s.weekly_active) { "WEEKLY" } else { "OFF" }
        $disp = if ($s.display) { $s.display } else { $s.key }
        Write-Host ("[{0}] {1}  ({2})" -f $i, $disp, $flag)
        $i++
    }
    Write-Host ""
}

function Toggle-StoreWeekly {
    param([string]$ProjectRoot)

    $reg = Load-StoresRegistry -ProjectRoot $ProjectRoot
    Show-Stores -ProjectRoot $ProjectRoot
    $pick = Read-Host "Choose store index to toggle weekly_active"
    if ($pick -notmatch '^\d+$') { Write-Host "Invalid index."; return }

    $idx = [int]$pick
    if ($idx -ge $reg.stores.Count) { Write-Host "Out of range."; return }

    $reg.stores[$idx].weekly_active = -not $reg.stores[$idx].weekly_active
    Save-StoresRegistry -ProjectRoot $ProjectRoot -registry $reg

    $k = $reg.stores[$idx].key
    $v = $reg.stores[$idx].weekly_active
    Write-Host "Updated $k -> weekly_active=$v" -ForegroundColor Green
}

function Add-Store {
    param([string]$ProjectRoot)

    $reg = Load-StoresRegistry -ProjectRoot $ProjectRoot

    $key = Read-Host "Folder key (snake_case)"
    if ([string]::IsNullOrWhiteSpace($key)) { Write-Host "Key required."; return }

    if ($reg.stores.key -contains $key) {
        Write-Host "Store already exists."; return
    }

    $display = Read-Host "Display name (optional)"
    $weekly  = Read-Host "Weekly active? (Y/N default N)"
    $isWeekly = ($weekly -match '^[Yy]')

    $reg.stores += [pscustomobject]@{
        key = $key
        display = $display
        weekly_active = $isWeekly
    }

    Save-StoresRegistry -ProjectRoot $ProjectRoot -registry $reg
    Write-Host "Added $key" -ForegroundColor Green
}

function Remove-StoreFromRegistry {
    param([string]$ProjectRoot)

    $reg = Load-StoresRegistry -ProjectRoot $ProjectRoot
    Show-Stores -ProjectRoot $ProjectRoot
    $pick = Read-Host "Choose store index to remove from registry"
    if ($pick -notmatch '^\d+$') { Write-Host "Invalid index."; return }

    $idx = [int]$pick
    if ($idx -ge $reg.stores.Count) { Write-Host "Out of range."; return }

    $dead = $reg.stores[$idx].key
    $reg.stores = $reg.stores | Where-Object { $_.key -ne $dead }

    Save-StoresRegistry -ProjectRoot $ProjectRoot -registry $reg
    Write-Host "Removed $dead from registry ONLY (folder not deleted)" -ForegroundColor Yellow
}
