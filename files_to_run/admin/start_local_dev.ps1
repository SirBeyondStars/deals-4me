# ==========================================================
# Deals-4Me Local Dev Launcher (Tool Kit)
# - Frees port 3002
# - Starts `vercel dev` in a new window
# - Opens the backend tester page
# ==========================================================

param(
  [int]$Port = 3002,
  [string]$ProjectDir = "C:\Users\jwein\OneDrive\Desktop\deals-4me",
  [string]$StartUrl   = "http://localhost:3002/site/backend-test.html"
)

Write-Host "`n=== Deals-4Me Local Dev (Port $Port) ===" -ForegroundColor Cyan

# 1) Free the port if something is listening
try {
  $pid = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess
  if ($pid) {
    Write-Host ("Stopping process using port {0} (PID: {1})..." -f $Port, $pid) -ForegroundColor Yellow
    Stop-Process -Id $pid -Force
    Start-Sleep -Seconds 1
    Write-Host "Port $Port is now free." -ForegroundColor Green
  } else {
    Write-Host "Port $Port was already free." -ForegroundColor Green
  }
}
catch {
  Write-Warning ("Could not query/stop processes on port {0}: {1}" -f $Port, $_.Exception.Message)
}

# 2) Launch `vercel dev` in a NEW PowerShell window so the menu doesn't block
$cmd = "Set-Location `"$ProjectDir`"; vercel dev --listen $Port"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-Command",$cmd

# 3) Give the server a moment, then open the test page
Start-Sleep -Seconds 2
Start-Process $StartUrl

Write-Host "`nLocal dev launching. A new PowerShell window should appear, and your browser should open to the tester page." -ForegroundColor Cyan
