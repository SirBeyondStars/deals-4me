# files_to_run/backend/cleanup_week_folders.ps1
# Deletes non-canonical folders inside wk_YYYYMMDD
# DRY RUN by default

param(
  [switch]$Apply   # only deletes when -Apply is passed
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---- Canonical folders (relative to week root)
$CANONICAL = @(
  "raw_pdf",
  "raw_png",
  "manual_imports",
  "manual_imports\excel",
  "manual_imports\csv",
  "ocr",
  "exports",
  "exports\csv",
  "exports\json",
  "logs"
)

# Normalize for comparison
$CANONICAL_NORM = $CANONICAL | ForEach-Object {
  ($_ -replace '\\','/').TrimEnd('/')
}

# Load canonical rules (required)
$BackendRoot = Resolve-Path -LiteralPath $PSScriptRoot
$RulesFile   = Join-Path $BackendRoot "store_week_rules.ps1"

if (-not (Test-Path -LiteralPath $RulesFile)) {
  throw "Missing rules file: $RulesFile"
}

. $RulesFile


$projectRoot = Get-ProjectRoot
$flyersRoot  = Join-Path $projectRoot "flyers"

Write-Host ""
Write-Host "Cleanup mode: " -NoNewline
if ($Apply) { Write-Host "APPLY (DELETES ENABLED)" -ForegroundColor Red }
else        { Write-Host "DRY RUN (no deletes)" -ForegroundColor Yellow }

Get-ChildItem -Path $flyersRoot -Directory | ForEach-Object {      # Region
  Get-ChildItem -Path $_.FullName -Directory | ForEach-Object {    # Store
    Get-ChildItem -Path $_.FullName -Directory -Filter "wk_*" | ForEach-Object {  # Week
      $weekRoot = $_.FullName
      Write-Host ""
      Write-Host "Checking: $weekRoot" -ForegroundColor Cyan

      Get-ChildItem -Path $weekRoot -Directory -Recurse | ForEach-Object {
        $rel = $_.FullName.Substring($weekRoot.Length + 1) -replace '\\','/'
        $keep = $false

        foreach ($c in $CANONICAL_NORM) {
          if ($rel -eq $c -or $rel.StartsWith("$c/")) {
            $keep = $true
            break
          }
        }

        if (-not $keep) {
          if ($Apply) {
            Write-Host "  DELETE: $rel" -ForegroundColor Red
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
          } else {
            Write-Host "  WOULD DELETE: $rel" -ForegroundColor Yellow
          }
        }
      }
    }
  }
}

Write-Host ""
Write-Host "Cleanup complete."
