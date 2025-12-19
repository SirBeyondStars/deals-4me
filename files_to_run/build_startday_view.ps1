# ===== build_startday_view.ps1 =====
[CmdletBinding()]
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$ViewRoot    = (Join-Path (Split-Path -Parent $PSScriptRoot) 'flyers\_by_startday'),
  [string]$Week        = ''   # optional MMDDYY or Week##
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'console_theme.ps1')

$StoreWeekday = @{
  aldi='Wednesday'; pricerite='Wednesday';
  stopandshop='Thursday'; 'stop_and_shop'='Thursday'; 'stop_and_shop_ct'='Thursday'; 'stop_and_shop_mari'='Thursday';
  shaws='Sunday'; market_basket='Sunday'; hannaford='Sunday'; price_chopper_market_32='Sunday';
  wegmans='Sunday'; roche_bros='Sunday'; big_y='Sunday'; trucchis='Sunday'; whole_foods='Sunday'
}

$FlyersRoot = Join-Path $ProjectRoot 'flyers'
if (-not (Test-Path $FlyersRoot)) { throw "Flyers root not found: $FlyersRoot" }

New-Item -ItemType Directory -Force -Path $ViewRoot | Out-Null
'Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday' |
  ForEach-Object { New-Item -ItemType Directory -Force -Path (Join-Path $ViewRoot $_) | Out-Null }

function Get-LatestWeek([string]$storeRoot) {
  (Get-ChildItem $storeRoot -Directory -EA SilentlyContinue |
   Where-Object {$_.Name -match '^(Week\d{2}|\d{6})$'} |
   Sort-Object Name -Descending | Select-Object -First 1)?.Name
}
function Make-JunctionOrShortcut([string]$linkPath, [string]$targetPath) {
  try {
    if (Test-Path $linkPath) { Remove-Item $linkPath -Force -EA SilentlyContinue }
    New-Item -ItemType Junction -Path $linkPath -Target $targetPath -EA Stop | Out-Null
  } catch {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut("$linkPath.lnk")
    $lnk.TargetPath = $targetPath
    $lnk.WorkingDirectory = (Split-Path $targetPath)
    $lnk.Save()
  }
}

Write-Title ("Building weekday view at: {0}" -f $ViewRoot)

Get-ChildItem $FlyersRoot -Directory | ForEach-Object {
  $store = $_.Name
  $weekday = $StoreWeekday[$store]; if (-not $weekday) { $weekday = 'Sunday' }
  $weekKey = if ($Week){$Week}else{ Get-LatestWeek $_.FullName }
  if (-not $weekKey) { Write-Note ("Skip {0}: no week folders yet." -f $store); return }
  $target = Join-Path $_.FullName $weekKey; if (-not (Test-Path $target)) { return }
  $link = Join-Path (Join-Path $ViewRoot $weekday) $store
  Make-JunctionOrShortcut -linkPath $link -targetPath $target
  Write-Info ("Link {0}\{1} -> {2}" -f $weekday,$store,$weekKey)
}
Write-Ok ("Done. Browse: {0}" -f $ViewRoot)
# ===== end =====
