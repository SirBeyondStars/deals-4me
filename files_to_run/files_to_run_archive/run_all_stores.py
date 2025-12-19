# C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\run_all_stores.ps1
$ErrorActionPreference = 'Stop'

function Run-Py {
    param([string[]]$Args)
    # Use Start-Process so we always wait and keep output in this window
    Start-Process -FilePath "python" -ArgumentList $Args -NoNewWindow -Wait
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n[!] Python exited with code $LASTEXITCODE" -ForegroundColor Red
    }
}

while ($true) {
    Clear-Host
    Write-Host "====================================="
    Write-Host "   Deals-4Me Mini-Admin Tool"
    Write-Host "====================================="
    Write-Host ""
    Write-Host "1) Run all store scrapers"
    Write-Host "2) OCR missing flyers"
    Write-Host "3) Cleanup old folders"
    Write-Host "4) Create next week folders"
    Write-Host "5) Run compression"
    Write-Host "6) Upload results"
    Write-Host "7) Check current week & auto-OCR new flyers"
    Write-Host "0) Exit"
    Write-Host ""

    $choice = Read-Host "Select an option (0–7)"

    switch ($choice) {
        "1" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\run_all_stores.py") }
        "2" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\run_ocr_missing.py") }
        "3" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\cleanup_old_folders.py") }
        "4" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\create_next_week_folders.py") }
        "5" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\run_compression.py") }
        "6" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\upload_results.py") }
        "7" { Run-Py @("C:\Users\jwein\OneDrive\Desktop\deals-4me\files_to_run\check_current_week_status.py", "--auto-ocr-new", "--window-hours", "6") }
        "0" { Write-Host "Exiting..."; break }
        default { Write-Host "Invalid option. Try again." }
    }

    Write-Host "`n-------------------------------------"
    Read-Host "Press Enter to return to the menu"
}
