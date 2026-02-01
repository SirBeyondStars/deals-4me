<#
  site/files_to_run/backend/run_export_and_ocr_all.ps1

  Wrapper to run the Python batch "run_all_stores.py"
  for a given REGION + week, across ALL stores.

  New canonical week format:
    wk_YYYYMMDD  (Sunday start date)

  New folder layout:
    flyers/<REGION>/<store_slug>/<wk_YYYYMMDD>/...

  Expected usage (from run_admin.ps1):
    & "$backendDir\run_export_and_ocr_all.ps1" -Region NE -WeekCode "wk_20251228"

  Optional:
    -ProjectRoot override if needed
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidateNotNullOrEmpty()]
  [string]$Region,   # e.g. NE

  [Parameter(Mandatory = $true)]
  [ValidateNotNullOrEmpty()]
  [string]$WeekCode, # e.g. wk_20251228

  [Parameter(Mandatory = $false)]
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,

  [Parameter(Mandatory = $false)]
  [string]$FlyersRootOverride
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Write-Info { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Write-Note { param([string]$m) Write-Host $m -ForegroundColor Gray }
function Write-Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }

function ConvertTo-RegionCode {
  param([string]$R)
  if ([string]::IsNullOrWhiteSpace($R)) { return "NE" }
  return $R.Trim().ToUpperInvariant()
}

function Test-WeekCode {
  param([string]$W)
  return ($W -match '^wk_\d{8}$')
}

$Region   = ConvertTo-RegionCode -R $Region
$WeekCode = $WeekCode.Trim()

if (-not (Test-WeekCode -W $WeekCode)) {
  throw "Invalid WeekCode '$WeekCode'. Expected format: wk_YYYYMMDD (e.g. wk_20251228)."
}

$backendDir = $PSScriptRoot

# Flyers root
$flyersRoot = if ($FlyersRootOverride) { $FlyersRootOverride } else { (Join-Path $ProjectRoot "flyers") }
if (-not (Test-Path $flyersRoot)) {
  throw "Flyers root not found: $flyersRoot"
}

# Python batch script
$pyScript = Join-Path $backendDir "run_all_stores.py"
if (-not (Test-Path $pyScript)) {
  throw "run_all_stores.py not found in: $backendDir"
}

# Python executable
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
  $pythonExe = $venvPython
  Write-Note "Using virtualenv Python: $pythonExe"
} else {
  $pythonExe = "python"
  Write-Note "Using system Python on PATH"
}

Write-Host ""
Write-Host "========================================="
Write-Host " Export + OCR (ALL stores)"
Write-Host " Region     : $Region"
Write-Host " Week       : $WeekCode"
Write-Host " FlyersRoot : $flyersRoot"
Write-Host " BackendDir : $backendDir"
Write-Host "========================================="
Write-Host ""

$pyArgs = @(
  $pyScript,
  "--flyers-root", $flyersRoot,
  "--region", $Region,
  "--week", $WeekCode
)

Write-Host "$pythonExe $($args -join ' ')" -ForegroundColor DarkGray

$proc = Start-Process -FilePath $pythonExe `
                      A-ArgumentList $pyargs `
                      -NoNewWindow `
                      -PassThru `
                      -Wait

if ($proc.ExitCode -eq 0) {
  Write-Ok "All stores processed successfully for $Region $WeekCode."
} else {
  Write-Host "Batch export/OCR FAILED with exit code $($proc.ExitCode)." -ForegroundColor Red
}

exit $proc.ExitCode
