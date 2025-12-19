<# 
    run_admin.ps1
    Deals-4-Me Backend Admin Tool

    Menu:
      [1] Prep current+next flyer folders (Mode both)
      [2] Ingest a specific week (prompt)
      [3] Ingest current flyer week (auto)
      [4] Run all stores batch (Python)
      [5] Week status check (counts raw files)
      [6] Store Settings Manager (placeholder)
      [7] Ingestion Status Report (by week, files only)
      [0] Exit

    Folder layout assumed:

      deals-4me\files_to_run\
        admin\run_admin.ps1          (this file)
        backend\*.ps1 / *.py         (helper scripts)
        flyers\<store>\weekNN\...    (raw flyer assets)

#>

$ErrorActionPreference = "Stop"

# ------------------ Paths / basic config ------------------

$adminDir    = $PSScriptRoot
$projectRoot = Split-Path $adminDir -Parent
$backendDir  = Join-Path $projectRoot "backend"
$flyersRoot  = Join-Path $projectRoot "flyers"

# Region label for display only
$region = "NE"

# ------------------ Console helpers -----------------------

function Write-Info {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Red
}

function Write-Note {
    param([string]$Message)
    Write-Host $Message -ForegroundColor DarkGray
}

function Pause-ForKey {
    param([string]$Message = "Done. Press Enter...")
    Write-Host ""
    Write-Host $Message
    [void][System.Console]::ReadLine()
}

# ------------------ Week helpers --------------------------

function Get-CurrentIsoWeekNumber {
    $today    = Get-Date
    $calendar = [System.Globalization.CultureInfo]::InvariantCulture.Calendar
    $rule     = [System.Globalization.CalendarWeekRule]::FirstFourDayWeek
    $firstDay = [System.DayOfWeek]::Monday

    return $calendar.GetWeekOfYear($today, $rule, $firstDay)
}

function Normalize-WeekCode {
    param(
        [Parameter(Mandatory)]
        [string]$WeekInput
    )

    $w = $WeekInput.Trim()

    # Accept "51", "week51", "Week51"
    if ($w -match '^(week|Week)(\d{1,2})$') {
        $num = [int]$matches[2]
        return ("week{0:D2}" -f $num)
    }
    elseif ($w -match '^(\d{1,2})$') {
        $num = [int]$matches[1]
        return ("week{0:D2}" -f $num)
    }
    else {
        throw "Invalid week '$WeekInput'. Use e.g. 51 or week51."
    }
}

# ------------------ Shared: file-count helper --------------

function Get-RawFileCountForWeek {
    param(
        [Parameter(Mandatory)]
        [string]$StorePath,
        [Parameter(Mandatory)]
        [string]$WeekCode   # expects "weekNN"
    )

    $weekDir  = Join-Path $StorePath $WeekCode
    $rawPdf   = Join-Path $weekDir "raw_pdf"
    $rawPng   = Join-Path $weekDir "raw_png"

    $count = 0

    foreach ($dir in @($rawPdf, $rawPng)) {
        if (Test-Path $dir) {
            $count += (Get-ChildItem -Path $dir -File -Recurse -ErrorAction SilentlyContinue |
                       Measure-Object).Count
        }
    }

    return $count
}

# ------------------ Option 1: prep week folders ------------

function Invoke-PrepWeekFolders {
    Write-Info "Prep current+next flyer folders (Mode both)..."

    $scriptPath = Join-Path $backendDir "prep_week_flyer_folders.ps1"
    if (-not (Test-Path $scriptPath)) {
        Write-Warn "Script not found: $scriptPath"
        return
    }

    # Mode "both" => current+next
    & $scriptPath -Mode both
}

# ------------------ Option 2: ingest specific week ---------

function Invoke-IngestSpecificWeek {
    Write-Info "Running run_export_and_ocr_all.ps1 (specific week)..."

    $scriptPath = Join-Path $backendDir "run_export_and_ocr_all.ps1"
    if (-not (Test-Path $scriptPath)) {
        Write-Warn "Script not found: $scriptPath"
        return
    }

    $weekInput = Read-Host "Enter week code (e.g. 51 or week51)"
    if ([string]::IsNullOrWhiteSpace($weekInput)) {
        Write-Warn "No week entered. Aborting."
        return
    }

    $weekCode = Normalize-WeekCode -WeekInput $weekInput   # weekNN

    Write-Note "Using week folder: $weekCode"
    Write-Note "Flyers root:       $flyersRoot"
    Write-Host ""

    & $scriptPath -weekCode $weekCode -flyersRoot $flyersRoot
}

# ------------------ Option 3: ingest current week (auto) ---

function Invoke-IngestCurrentWeekAuto {
    Write-Info "Running auto ingest for current flyer week (latest week folders)..."

    $pyScript = Join-Path $backendDir "run_all_stores.py"
    if (-not (Test-Path $pyScript)) {
        Write-Warn "Python script not found: $pyScript"
        return
    }

    # Choose Python exe (same logic as Option 4)
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $pythonExe = $venvPython
        Write-Note "Using virtualenv Python: $pythonExe"
    }
    else {
        $pythonExe = "python"
        Write-Note "Using system Python on PATH"
    }

    # Try to detect the highest weekNN across all stores, just for display
    $latestWeekNum  = $null
    $latestWeekName = $null

    if (Test-Path $flyersRoot) {
        $stores = Get-ChildItem -Path $flyersRoot -Directory -ErrorAction SilentlyContinue
        foreach ($s in $stores) {
            $weekDirs = Get-ChildItem -Path $s.FullName -Directory -ErrorAction SilentlyContinue |
                        Where-Object { $_.Name -match '^week(\d{1,2})$' }

            foreach ($w in $weekDirs) {
                $m = [regex]::Match($w.Name, '^week(\d{1,2})$', 'IgnoreCase')
                if ($m.Success) {
                    $num = [int]$m.Groups[1].Value
                    if ($latestWeekNum -eq $null -or $num -gt $latestWeekNum) {
                        $latestWeekNum  = $num
                        $latestWeekName = $w.Name
                    }
                }
            }
        }
    }

    if ($latestWeekName) {
        Write-Note "Detected latest week folder across stores: $latestWeekName"
    }
    else {
        Write-Note "Could not detect any weekNN folders under flyers root; will still run with --latest."
    }

    Write-Note "Flyers root: $flyersRoot"
    Write-Host ""

    # Use --latest so each store uses its latest weekNN folder
    $args = @(
        $pyScript,
        "--flyers-root",  $flyersRoot
    )

    Write-Note "$pythonExe $($args -join ' ')"
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $args -NoNewWindow -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Ok "Python batch completed successfully (latest week per store)."
    }
    else {
        Write-Warn "Python batch exited with code $($proc.ExitCode)."
    }
}

# ------------------ Option 4: run_all_stores.py ------------

function Invoke-RunAllStoresBatch {
    Write-Info "Running run_all_stores.py (Python batch)..."

    $pyScript = Join-Path $backendDir "run_all_stores.py"
    if (-not (Test-Path $pyScript)) {
        Write-Warn "Python script not found: $pyScript"
        return
    }

    # Choose Python exe
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $pythonExe = $venvPython
        Write-Note "Using virtualenv Python: $pythonExe"
    }
    else {
        $pythonExe = "python"
        Write-Note "Using system Python on PATH"
    }

    # Ask whether to use specific week or latest per store
    $mode = Read-Host "Use [W]eek code or [L]atest week per store? (W/L, default=L)"
    if ($mode -match '^[Ww]') {
        $weekInput = Read-Host "Enter week code (e.g. 51 or week51)"
        if ([string]::IsNullOrWhiteSpace($weekInput)) {
            Write-Warn "No week entered. Aborting."
            return
        }
        $weekCode = Normalize-WeekCode -WeekInput $weekInput  # weekNN
        $args = @(
            $pyScript,
            "--root",  $flyersRoot,
            "--week",  $weekCode
        )
    }
    else {
        $args = @(
            $pyScript,
            "--root",   $flyersRoot,
            "--latest"
        )
    }

    Write-Note "$pythonExe $($args -join ' ')"
    $proc = Start-Process -FilePath $pythonExe -ArgumentList $args -NoNewWindow -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Ok "Python batch completed successfully."
    }
    else {
        Write-Warn "Python batch exited with code $($proc.ExitCode)."
    }
}

# ------------------ Option 5: week status (raw files) ------

function Invoke-WeekStatusCheck {
    Write-Info "Week status check (raw file counts)..."
    Write-Note "Flyers root: $flyersRoot"
    Write-Host ""

    if (-not (Test-Path $flyersRoot)) {
        Write-Warn "Flyers root not found: $flyersRoot"
        return
    }

    $weekInput = Read-Host "Enter week code (e.g. 51 or week51)"
    if ([string]::IsNullOrWhiteSpace($weekInput)) {
        Write-Warn "No week entered. Aborting."
        return
    }

    $weekCode = Normalize-WeekCode -WeekInput $weekInput  # weekNN

    $stores = Get-ChildItem -Path $flyersRoot -Directory -ErrorAction SilentlyContinue
    if (-not $stores) {
        Write-Warn "No store folders found under $flyersRoot"
        return
    }

    Write-Host ""
    Write-Host ("{0,-28} {1,10} {2,-20}" -f "Store", "RawFiles", "Status")
    Write-Host ("-" * 60)

    foreach ($s in $stores) {
        $rawCount = Get-RawFileCountForWeek -StorePath $s.FullName -WeekCode $weekCode
        $status   = if ($rawCount -gt 0) { "OK" } else { "EMPTY/NO WEEK" }

        Write-Host ("{0,-28} {1,10} {2,-20}" -f $s.Name, $rawCount, $status)
    }
}

# ------------------ Option 6: store settings (placeholder) -

function Invoke-StoreSettingsManager {
    Write-Info "Store Settings Manager (placeholder)..."
    Write-Host "This can be wired to a dedicated script later (e.g. store_settings_manager.ps1)." -ForegroundColor Yellow
}

# ------------------ Option 7: ingestion status (files only) -

function Invoke-IngestionStatusReport {
    Write-Info "Ingestion Status Report (files only)..."
    Write-Note "Flyers root: $flyersRoot"
    Write-Host ""

    if (-not (Test-Path $flyersRoot)) {
        Write-Warn "Flyers root not found: $flyersRoot"
        return
    }

    $weekInput = Read-Host "Enter week code (e.g. 51 or week51)"
    if ([string]::IsNullOrWhiteSpace($weekInput)) {
        Write-Warn "No week entered. Aborting."
        return
    }

    $weekCode = Normalize-WeekCode -WeekInput $weekInput  # weekNN

    $stores = Get-ChildItem -Path $flyersRoot -Directory -ErrorAction SilentlyContinue
    if (-not $stores) {
        Write-Warn "No store folders found under $flyersRoot"
        return
    }

    Write-Host ""
    Write-Host ("{0,-28} {1,10} {2,-18}" -f "Store", "RawFiles", "Status")
    Write-Host ("-" * 60)

    foreach ($s in $stores) {
        $rawCount = Get-RawFileCountForWeek -StorePath $s.FullName -WeekCode $weekCode

        if ($rawCount -gt 0) {
            $status = "FILES PRESENT"
        }
        else {
            $status = "NO FILES"
        }

        Write-Host ("{0,-28} {1,10} {2,-18}" -f $s.Name, $rawCount, $status)
    }
}

# ------------------ Main menu loop -------------------------

do {
    Clear-Host
    Write-Host "Deals-4Me Backend Admin Tool" -ForegroundColor White
    Write-Note  "Project: $projectRoot"
    Write-Note  "Backend: $backendDir"
    Write-Note  "Flyers:  $flyersRoot"
    Write-Note  "Region:  $region"
    Write-Host ""

    Write-Host "[1] Prep current+next flyer folders (Mode both)"
    Write-Host "[2] Ingest a specific week (prompt)"
    Write-Host "[3] Ingest current flyer week (auto)"
    Write-Host "[4] Run all stores batch (Python)"
    Write-Host "[5] Week status check (counts raw files)"
    Write-Host "[6] Store Settings Manager"
    Write-Host "[7] Ingestion Status Report (by week)"
    Write-Host "[0] Exit"
    Write-Host ""

    $choice = Read-Host "Select option"

    switch ($choice) {
        '1' { Invoke-PrepWeekFolders;        Pause-ForKey }
        '2' { Invoke-IngestSpecificWeek;     Pause-ForKey }
        '3' { Invoke-IngestCurrentWeekAuto;  Pause-ForKey }
        '4' { Invoke-RunAllStoresBatch;      Pause-ForKey }
        '5' { Invoke-WeekStatusCheck;        Pause-ForKey }
        '6' { Invoke-StoreSettingsManager;   Pause-ForKey }
        '7' { Invoke-IngestionStatusReport;  Pause-ForKey }
        '0' {
            Write-Note "Exiting Deals-4Me Backend Admin Tool..."
            break
        }
        default {
            Write-Warn "Invalid option: $choice"
            Pause-ForKey
        }
    }

} while ($true)
