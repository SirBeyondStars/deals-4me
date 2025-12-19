# prep_next_week.ps1
# Purpose: Convenience wrapper to seed NEXT week's folders (weekNN+1).

$ErrorActionPreference = "Stop"

# prep_week_flyer_folders.ps1 is in the same folder
$prepScript = Join-Path $PSScriptRoot "prep_week_flyer_folders.ps1"

Write-Host "Seeding NEXT week's flyer folders (weekNN+1)..." -ForegroundColor Cyan
pwsh -File $prepScript -Mode next
Write-Host "Done creating next week's folders." -ForegroundColor Green
