param(
  [string]$ProjectRoot = "$HOME\OneDrive\Desktop\deals-4me",
  # "Start" = rename to week start date; "End" = rename to week end date
  [ValidateSet("Start","End")]
  [string]$Mode = "Start",
  # Map per-store week start day; default Sunday. Example: @{ shaws = "Friday"; wegmans="Sunday" }
  [hashtable]$StoreWeekStart = @{ },
  # Preview only (no changes) unless -Apply is passed
  [switch]$Apply
)

function Get-WeekStart([datetime]$dt, [DayOfWeek]$startDay) {
  $delta = ($dt.DayOfWeek.value__ - $startDay.value__)
  if ($delta -lt 0) { $delta += 7 }
  return $dt.AddDays(-$delta)
}

function Get-WeekEnd([datetime]$dt, [DayOfWeek]$startDay) {
  $weekStart = Get-WeekStart -dt $dt -startDay $startDay
  return $weekStart.AddDays(6)
}

$flyersRoot = Join-Path $ProjectRoot "flyers"
if (-not (Test-Path $flyersRoot)) {
  Write-Error "Flyers root not found: $flyersRoot"
  exit 1
}

# default start day for stores not listed
$defaultStart = [System.DayOfWeek]::Sunday

# normalize hashtable values to DayOfWeek
$normalized = @{}
foreach ($k in $StoreWeekStart.Keys) {
  $dow = [System.DayOfWeek]::Parse([string]$StoreWeekStart[$k], $true)
  $normalized[$k.ToLower()] = $dow
}

$changes = New-Object System.Collections.Generic.List[Object]

Get-ChildItem -Path $flyersRoot -Directory | ForEach-Object {
  $storeName = $_.Name
  $storeKey = $storeName.ToLower()
  $startDay = $normalized.ContainsKey($storeKey) ? $normalized[$storeKey] : $defaultStart

  Get-ChildItem -Path $_.FullName -Directory | Where-Object { $_.Name -match '^\d{6}$' } | ForEach-Object {
    $oldName = $_.Name
    try {
      # parse MMddyy (assume 20yy)
      $dt = [datetime]::ParseExact($oldName, "MMddyy", $null)
      if ($dt.Year -lt 1970) { $dt = $dt.AddYears(2000) } # safety for yy->20yy
    } catch {
      $changes.Add([pscustomobject]@{
        Store=$storeName; Old=$oldName; New=$null; Action="Skip"; Reason="Invalid date"
      })
      return
    }

    $targetDate = if ($Mode -eq "Start") {
      Get-WeekStart -dt $dt -startDay $startDay
    } else {
      Get-WeekEnd -dt $dt -startDay $startDay
    }

    $newName = $targetDate.ToString("MMddyy")
    if ($newName -eq $oldName) {
      $changes.Add([pscustomobject]@{
        Store=$storeName; Old=$oldName; New=$newName; Action="NoChange"; Reason="Already aligned"
      })
      return
    }

    $oldPath = $_.FullName
    $newPath = Join-Path $_.Parent.FullName $newName

    if (Test-Path $newPath) {
      $changes.Add([pscustomobject]@{
        Store=$storeName; Old=$oldName; New=$newName; Action="Skip"; Reason="Destination exists"
      })
      return
    }

    if ($Apply) {
      Rename-Item -LiteralPath $oldPath -NewName $newName
      $changes.Add([pscustomobject]@{
        Store=$storeName; Old=$oldName; New=$newName; Action="Renamed"; Reason="OK"
      })
    } else {
      $changes.Add([pscustomobject]@{
        Store=$storeName; Old=$oldName; New=$newName; Action="Preview"; Reason="DryRun"
      })
    }
  }
}

# Write CSV log
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $ProjectRoot ("rename_log_"+$Mode+"_"+$stamp+".csv")
$changes | Export-Csv -Path $logPath -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "Mode: $Mode   Apply: $($Apply.IsPresent)"
Write-Host "Week starts (store overrides):"
if ($normalized.Count -gt 0) {
  $normalized.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host "  $($_.Name) -> $($_.Value)" }
} else {
  Write-Host "  (none; using default $defaultStart)"
}
Write-Host ""
Write-Host "Summary:"
$changes | Group-Object Action | ForEach-Object { "{0,-10} {1,5}" -f $_.Name, $_.Count } | Write-Host
Write-Host "Log: $logPath"
