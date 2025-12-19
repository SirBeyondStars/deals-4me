# ===== auto_archive_old_weeks_by_week.ps1 =====
[CmdletBinding()]
param([int]$KeepWeeks=2, [string]$ProjectRoot=(Split-Path -Parent $PSScriptRoot), [string]$ArchiveRoot="D:\deals-4me-archive")

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'console_theme.ps1')
. (Join-Path $PSScriptRoot 'store_week_rules.ps1')

$FlyersRoot = Join-Path $ProjectRoot 'flyers'
New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null

function Parse-MmDdYy([string]$key){
  if ($key -notmatch '^\d{6}$') { return $null }
  $mm=[int]$key.Substring(0,2); $dd=[int]$key.Substring(2,2); $yy=[int]$key.Substring(4,2)
  try { [datetime]::new(2000+$yy,$mm,$dd) } catch { $null }
}

Write-Title ("Auto-archive by week (KeepWeeks={0})" -f $KeepWeeks)
Get-ChildItem $FlyersRoot -Directory | ForEach-Object {
  $store = $_.Name
  $list=@()
  Get-ChildItem $_.FullName -Directory -EA SilentlyContinue |
    Where-Object {$_.Name -match '^\d{6}$'} | ForEach-Object {
      $d = Parse-MmDdYy $_.Name; if ($null -eq $d){return}
      $anchor = Get-StartOfStoreWeek $d $store
      $wkInfo = [System.Globalization.ISOWeek]::GetWeekOfYear($anchor)
      $yyww   = [int]("{0:yy}{1:00}" -f $anchor.Year,$wkInfo)
      $list  += [PSCustomObject]@{Dir=$_.FullName; Store=$store; Folder=$_.Name; YYWW=$yyww}
    }
  if (-not $list) { return }

  $sorted=$list | Sort-Object YYWW -Descending
  $keep=$sorted | Select-Object -First $KeepWeeks
  $keepSet=@{}; $keep | ForEach-Object { $keepSet[$_.Folder]=1 }
  $toMove = $sorted | Where-Object { -not $keepSet.ContainsKey($_.Folder) }

  foreach ($item in $toMove) {
    $dest = Join-Path (Join-Path $ArchiveRoot 'flyers') (Join-Path $store $item.Folder)
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    Write-Ok ("ARCHIVE {0}\{1} (YYWW {2}) -> {3}" -f $store,$item.Folder,$item.YYWW,$dest)
    Move-Item -Path $item.Dir -Destination $dest -Force
  }
}
Write-Ok "Done. Archived older weeks."
# ===== end =====
