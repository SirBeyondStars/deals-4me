# run_verify_and_archive.ps1 — fixed version
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$logDir  = Join-Path $project "logs\tasks"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("verify_archive_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

Start-Transcript -Path $logFile -Append | Out-Null
Set-Location $project

# === MAIN CALL (no pwsh nesting) ===
& "$PSScriptRoot\verify_and_archive_weeks.ps1" -KeepNewest 2 -ArchiveRoot "D:\deals-4me-archive"
# or use this line instead if you prefer specifying weeks manually:
# & "$PSScriptRoot\verify_and_archive_weeks.ps1" -Weeks 110125,110225 -ArchiveRoot "D:\deals-4me-archive"

Stop-Transcript | Out-Null

# Keep the window open if run via double-click
if (-not $env:WT_SESSION -and -not $env:TERM_PROGRAM) {
    Read-Host "`nDone. Press Enter to close"
}
