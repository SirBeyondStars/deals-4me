# ==========================================================
# Deals-4Me Local Dev Launcher
# Kills anything on port 3002, then starts Vercel dev cleanly
# ==========================================================

Write-Host "`n=== Starting Deals-4Me Local Dev (Port 3002) ===" -ForegroundColor Cyan

# 1️⃣  Kill anything already on port 3002
$port = 3002
$p = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($p) {
    Write-Host "Stopping process using port $port (PID: $p)..." -ForegroundColor Yellow
    Stop-Process -Id $p -Force
    Start-Sleep -Seconds 1
    Write-Host "Port $port is now free." -ForegroundColor Green
} else {
    Write-Host "Port $port was already free." -ForegroundColor Green
}

# 2️⃣  Navigate to your project directory
Set-Location "C:\Users\jwein\OneDrive\Desktop\deals-4me"

# 3️⃣  Start Vercel dev
Write-Host "`nLaunching local server..." -ForegroundColor Cyan
vercel dev --listen 3002

# 4️⃣  Keep console open if launched by double-click
Write-Host "`nServer closed or crashed. Press Enter to exit." -ForegroundColor Red
[void][System.Console]::ReadLine()
