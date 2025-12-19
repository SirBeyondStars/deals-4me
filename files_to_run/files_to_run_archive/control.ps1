<# Deals-4Me Mini Control (snips only) #>

# Activate venv and cd to project root
$root = "C:\Users\jwein\OneDrive\Desktop\deals-4me"
Set-Location $root
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv; Write-Host "[env] .venv activated" -ForegroundColor Green }

function Ask($prompt, $default=$null) {
  if ($null -ne $default) {
    $v = Read-Host "$prompt [$default]"
    if ([string]::IsNullOrWhiteSpace($v)) { return $default } else { return $v }
  } else { return (Read-Host $prompt) }
}

while ($true) {
  Clear-Host
  Write-Host "=== Deals-4Me Mini ===" -ForegroundColor Cyan
  Write-Host "1) Process snips (OCR -> Supabase) for a store/week"
  Write-Host "0) Exit"
  $choice = Read-Host "Choose an option"
  switch ($choice) {
    "1" {
      $store = Ask "Store folder name (e.g., trucchis)"
      $week  = Ask "Week code (MMddyy)"
      & ".\Files to Run\go.ps1" -Stores @($store) -Week $week
      Pause
    }
    "0" { break }
    default { Write-Host "Unknown option" -ForegroundColor Yellow; Pause }
  }
}
