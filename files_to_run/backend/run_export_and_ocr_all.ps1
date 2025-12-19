<#
    run_export_and_ocr_all.ps1

    Wrapper to run the Python batch "run_all_stores.py"
    for a given week, across ALL stores.

    Expected usage (from run_admin.ps1):

        & "$backendDir\run_export_and_ocr_all.ps1" -weekCode "week51" -flyersRoot "C:\...\flyers"

    where:
      -weekCode   is a week folder name like "week51"
      -flyersRoot is the root flyers directory.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$weekCode,   # e.g. week51 or 51

    [Parameter(Mandatory = $true)]
    [string]$flyersRoot
)

$ErrorActionPreference = "Stop"

# Backend dir is where this script lives
$backendDir  = $PSScriptRoot
$projectRoot = Split-Path $backendDir -Parent

function Normalize-WeekCodeForPython {
    param(
        [Parameter(Mandatory)]
        [string]$Code
    )

    $c = $Code.Trim()

    if ($c -match '^(week|Week)(\d{1,2})$') {
        $num = [int]$matches[2]
        return ("week{0:D2}" -f $num)
    }
    elseif ($c -match '^(\d{1,2})$') {
        $num = [int]$matches[1]
        return ("week{0:D2}" -f $num)
    }
    else {
        throw "Invalid week code '$Code'. Use e.g. 51 or week51."
    }
}

$weekCodeNorm = Normalize-WeekCodeForPython -Code $weekCode

# Validate flyers root
if (-not (Test-Path $flyersRoot)) {
    Write-Host "ERROR: Flyers root not found: $flyersRoot" -ForegroundColor Red
    exit 1
}

# Locate Python batch script
$pyScript = Join-Path $backendDir "run_all_stores.py"
if (-not (Test-Path $pyScript)) {
    Write-Host "ERROR: run_all_stores.py not found in $backendDir" -ForegroundColor Red
    exit 1
}

# Choose Python executable
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
    Write-Host "Using virtualenv Python: $pythonExe" -ForegroundColor DarkGray
}
else {
    $pythonExe = "python"
    Write-Host "Using system Python on PATH" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "========================================="
Write-Host " Running export + OCR for week: $weekCodeNorm"
Write-Host " Flyers root: $flyersRoot"
Write-Host " Backend dir: $backendDir"
Write-Host "========================================="
Write-Host ""

# Build arguments for run_all_stores.py
$args = @(
    $pyScript,
    "--flyers-root", $flyersRoot,
    "--week", $weekCodeNorm
)

Write-Host "$pythonExe $($args -join ' ')" -ForegroundColor DarkGray

$proc = Start-Process -FilePath $pythonExe `
                      -ArgumentList $args `
                      -NoNewWindow `
                      -PassThru `
                      -Wait

if ($proc.ExitCode -eq 0) {
    Write-Host "All stores processed successfully for $weekCodeNorm." -ForegroundColor Green
}
else {
    Write-Host "Batch ingest FAILED with exit code $($proc.ExitCode)." -ForegroundColor Red
}

exit $proc.ExitCode
