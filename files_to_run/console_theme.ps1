# ===== console_theme.ps1 =====
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Write-Ok    ($msg) { Write-Host $msg -ForegroundColor Green }
function Write-Warn  ($msg) { Write-Host $msg -ForegroundColor Yellow }
function Write-Note  ($msg) { Write-Host $msg -ForegroundColor Gray }
function Write-Info  ($msg) { Write-Host $msg -ForegroundColor DarkCyan }
function Write-Title ($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Err   ($msg) { Write-Host $msg -ForegroundColor Red }
# ===== end =====
