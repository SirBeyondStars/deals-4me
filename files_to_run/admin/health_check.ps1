# ===== health_check.ps1 (calm palette, safe counters) =====
[CmdletBinding()]
param(
  [string]$Week = '',   # e.g. 110325 or Week45 (blank = latest per store)
  [string]$Root = '',   # optional project root
  [string]$Csv  = ''    # folder or full csv path (blank = no export)
)

# Load shared console theme from parent directory (files_to_run)
$ProjectRoot       = Split-Path $PSScriptRoot -Parent
$ConsoleThemePath  = Join-Path $ProjectRoot "console_theme.ps1"

if (-not (Test-Path $ConsoleThemePath)) {
    Write-Host "WARNING: console_theme.ps1 not found at $ConsoleThemePath" -ForegroundColor Yellow
} else {
    . $ConsoleThemePath
}

function Choose-ProjectRoot([string]$Override) {
  if ($Override -and (Test-Path $Override)) { return (Resolve-Path $Override).Path }
  $cDefault = (Split-Path -Parent $PSScriptRoot)
  $dLive    = "D:\deals-4me"
  $dArch    = "D:\deals-4me-archive"
  @($cDefault,$dLive,$dArch) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

# Repo root = parent of files_to_run (i.e., ...\deals-4me)
$FilesToRunRoot = Split-Path $PSScriptRoot -Parent
$RepoRoot       = Split-Path $FilesToRunRoot -Parent

# Flyers live directly under the repo root: ...\deals-4me\flyers
$FlyersRoot     = Join-Path $RepoRoot "flyers"

if (-not (Test-Path $FlyersRoot)) {
    throw "Flyers not found: $FlyersRoot"
}

$stores = @(
  'aldi','big_y','hannaford','market_basket','price_chopper_market_32','pricerite',
  'roche_bros','shaws','trucchis','wegmans','whole_foods',
  'stop_and_shop_ct','stop_and_shop_mari','stopandshop'
)

Write-Title "=== Deals-4Me Health Check ==="
Write-Info  ("Root:   {0}" -f $ProjectRoot)
Write-Info  ("Flyers: {0}" -f $FlyersRoot)
if ($Week) { Write-Info ("Week override: {0}" -f $Week) }

function Pick-WeekFolder([string]$storeRoot,[string]$override) {
  if ($override) {
    $cand = Join-Path $storeRoot $override
    if (Test-Path $cand) { return (Get-Item $cand) }
    return $null
  }
  Get-ChildItem $storeRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^(Week\d{2}|\d{6})$' } |
    Sort-Object Name -Descending |
    Select-Object -First 1
}

function Count-FilesSafe([string]$path,[string[]]$filters) {
  if (-not (Test-Path $path)) { return 0 }
  $n = 0
  foreach ($f in $filters) {
    $n += (Get-ChildItem $path -File -Filter $f -ErrorAction SilentlyContinue).Count
  }
  return $n
}

$ok=0;$pending=0;$neutral=0
$rows = New-Object System.Collections.Generic.List[object]

foreach ($store in $stores) {
  $root = Join-Path $FlyersRoot $store
  if (-not (Test-Path $root)) {
    $neutral++; Write-Note ("{0,-20} — store folder missing" -f $store)
    $rows.Add([PSCustomObject]@{Store=$store;Week='';Pdfs=0;Images=0;OCR=0;Ok='no';Status='store folder missing'})|Out-Null
    continue
  }

  $wkDir = Pick-WeekFolder $root $Week
  if (-not $wkDir) {
    $neutral++; Write-Note ("{0,-20} — no week folder" -f $store)
    $rows.Add([PSCustomObject]@{Store=$store;Week='';Pdfs=0;Images=0;OCR=0;Ok='no';Status='no week folder'})|Out-Null
    continue
  }

  $base = $wkDir.FullName
  $pdfDir = Join-Path $base 'pdf'
  $imgDir = Join-Path $base 'raw_images'
  $ocrDir = Join-Path $base 'ocr_txt'
  $expDir = Join-Path $base 'exports'

  $nPdf = Count-FilesSafe $pdfDir @('*.pdf')
  $nImg = Count-FilesSafe $imgDir @('*.png','*.jpg','*.jpeg')
  $nOcr = Count-FilesSafe $ocrDir @('*.txt')
  $okMk = @(Get-ChildItem $expDir -Filter '*.ok' -ErrorAction SilentlyContinue).Count -gt 0

  $line = "{0,-20} {1,-8} PDFs:{2,3} IMG:{3,3} OCR:{4,3} OK:{5}" -f $store,$wkDir.Name,$nPdf,$nImg,$nOcr,($(if($okMk){"yes"}else{"no"}))

  if (($nPdf + $nImg) -eq 0) {
    $neutral++; Write-Note ("⚪ {0} -> waiting for inputs" -f $line)
    $rows.Add([PSCustomObject]@{Store=$store;Week=$wkDir.Name;Pdfs=$nPdf;Images=$nImg;OCR=$nOcr;Ok='no';Status='waiting for inputs'})|Out-Null
  }
  elseif ($okMk) {
    $ok++; Write-Ok ("✅ {0}" -f $line)
    $rows.Add([PSCustomObject]@{Store=$store;Week=$wkDir.Name;Pdfs=$nPdf;Images=$nImg;OCR=$nOcr;Ok='yes';Status='OK'})|Out-Null
  }
  else {
    $pending++; Write-Warn ("🟡 {0} -> pending" -f $line)
    $rows.Add([PSCustomObject]@{Store=$store;Week=$wkDir.Name;Pdfs=$nPdf;Images=$nImg;OCR=$nOcr;Ok='no';Status='pending'})|Out-Null
  }
}

Write-Title ("Summary: ✅ {0}   🟡 {1}   ⚪ {2}" -f $ok,$pending,$neutral)

if ($Csv) {
  try {
    $out = $Csv
    $isDir = (Test-Path $Csv) -and ((Get-Item $Csv) -is [System.IO.DirectoryInfo])
    if ($isDir) {
      $out = Join-Path $Csv ("health_check_{0:yyyyMMdd_HHmmss}.csv" -f (Get-Date))
    } elseif (-not ($out -match '\.csv$')) {
      New-Item -ItemType Directory -Force -Path $out | Out-Null
      $out = Join-Path $out ("health_check_{0:yyyyMMdd_HHmmss}.csv" -f (Get-Date))
    }
    $rows | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $out
    Write-Info ("CSV written: {0}" -f $out)
  } catch {
    Write-Err ("CSV write failed: {0}" -f $_.Exception.Message)
  }
}
# ===== end =====
