# === Config ===
$Root = "C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers"

# Map each store to its sale-week START weekday
$Schedule = [ordered]@{
  "aldi"         = "Wednesday"
  "pricerite"    = "Wednesday"
  "stopandshop"  = "Thursday"
  "shaws"        = "Sunday"
  "marketbasket" = "Sunday"
  "hannaford"    = "Sunday"
}

# ---- Helpers ----
function Get-EasternNow {
  $tz = [System.TimeZoneInfo]::FindSystemTimeZoneById("Eastern Standard Time")
  return [System.TimeZoneInfo]::ConvertTime([datetime]::UtcNow, $tz)
}

function Get-NextWeekday([datetime]$fromDate, [string]$targetName) {
  $target = [System.DayOfWeek]::Parse([System.Globalization.CultureInfo]::InvariantCulture, $targetName)
  $d = $fromDate.Date
  while ($d.DayOfWeek -ne $target) { $d = $d.AddDays(1) }
  return $d
}

# ---- Main ----
$nowET   = Get-EasternNow
$created = @()

foreach ($store in $Schedule.Keys) {
  $start = Get-NextWeekday -fromDate $nowET -targetName $Schedule[$store]
  $end   = $start.AddDays(6)
  $stamp = $start.ToString("MMddyy")

  $base     = Join-Path $Root "$store\$stamp"
  $rawPdfs  = Join-Path $base "raw_pdfs"
  $rawImgs  = Join-Path $base "raw_images"
  New-Item -ItemType Directory -Path $rawPdfs -Force | Out-Null
  New-Item -ItemType Directory -Path $rawImgs -Force | Out-Null

  $notesPath = Join-Path $base "notes.txt"
  if (-not (Test-Path $notesPath)) {
    $lines = @(
      "Store: $store"
      "Valid (ET): $($start.ToString('MM/dd/yy')) - $($end.ToString('MM/dd/yy'))"
      "Created: $($nowET.ToString('yyyy-MM-dd HH:mm'))"
      "Source URLs:"
      "- "
    )
    $lines -join "`r`n" | Out-File -FilePath $notesPath -Encoding UTF8
  }

  $created += "{0,-13} {1}" -f $store, $stamp
}

Write-Host "Folders created under $Root:`n" -ForegroundColor Green
$created | ForEach-Object { Write-Host "  $_" }
