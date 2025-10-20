# run_ingest_current_week_NE.ps1 (v2)
# Runs your image->parse->ingest pipeline for the CURRENT week for a list of NE stores.
# It only runs a store if the current week's raw_images folder exists.

$ProjectRoot = "C:\Users\jwein\OneDrive\Desktop\deals-4me"
$VenvPy      = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python      = (Test-Path $VenvPy) ? $VenvPy : "py"

# Stores you expect to process next (edit any time)
$Stores = @(
  "aldi",          # Wed→Tue
  "shaws",         # Sun→Sat
  "marketbasket",  # Sun→Sat
  "hannaford",     # Sun→Sat
  "pricechopper",  # Sun→Sat (Market 32)
  "wegmans",       # Sun→Sat (treat as Sunday)
  "pricerite",     # Wed→Tue
  "stopandshop"    # Thu→Wed
)

# Start weekday per store (keep in sync with your folder creator)
$Schedule = @{
  "aldi"         = "Wednesday"
  "pricerite"    = "Wednesday"
  "stopandshop"  = "Thursday"
  "shaws"        = "Sunday"
  "marketbasket" = "Sunday"
  "hannaford"    = "Sunday"
  "pricechopper" = "Sunday"
  "wegmans"      = "Sunday"
}

function Get-CurrentWeekStamp([string]$weekday) {
  $tz  = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
  $now = [System.TimeZoneInfo]::ConvertTime([datetime]::UtcNow, $tz)

  # most recent occurrence of the start weekday (not next)
  $target = [System.DayOfWeek]::Parse([System.DayOfWeek], $weekday)
  $d = $now.Date
  while ($d.DayOfWeek -ne $target) { $d = $d.AddDays(-1) }
  $d.ToString("MMddyy")
}

Set-Location $ProjectRoot

foreach ($store in $Stores) {
  if (-not $Schedule.ContainsKey($store)) {
    Write-Host ("Skip {0}: no weekday defined in `$Schedule." -f $store) -ForegroundColor Yellow
    continue
  }

  $week = Get-CurrentWeekStamp $Schedule[$store]
  $imagesDir = Join-Path $ProjectRoot ("flyers\{0}\{1}\raw_images" -f $store, $week)

  if (-not (Test-Path $imagesDir)) {
    Write-Host ("Skip {0} ({1}): no raw_images for current week." -f $store, $week) -ForegroundColor DarkYellow
    continue
  }

  Write-Host ("Ingest {0} ({1})..." -f $store, $week) -ForegroundColor Cyan

  # Adjust flags here if your runner is different
  $pyArgs = @("scripts\run_all_stores.py", "--store", $store, "--images", "--ingest", "--week", $week)

  & $Python @pyArgs
  if ($LASTEXITCODE -ne 0) {
    Write-Host ("ERROR ingesting {0} ({1}). Check logs." -f $store, $week) -ForegroundColor Red
  } else {
    Write-Host ("Done {0} ({1})." -f $store, $week) -ForegroundColor Green
  }
}

Write-Host "All done."
