param(
  [string]$Weeks = "",               # e.g. -Weeks 110125,110225  (optional)
  [int]$KeepNewest = 2,              # keep newest N weeks per store
  [string]$ArchiveRoot = "D:\deals-4me-archive"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FlyersRoot  = Join-Path $ProjectRoot "flyers"
$Skip = @('_inbox','logs','run','_week_template','_templates')

function Has-Files($path, $exts) {
  if (-not (Test-Path $path)) { return $false }
  $files = Get-ChildItem $path -File -ErrorAction SilentlyContinue |
           Where-Object { $exts -contains ($_.Extension.ToLower()) }
  return ($files | Measure-Object).Count -gt 0
}
function Has-GreenHeartbeat($exportsDir) {
  if (-not (Test-Path $exportsDir)) { return $false }
  $ok = Get-ChildItem $exportsDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^ingest_.*\.ok$' }
  return ($ok | Measure-Object).Count -gt 0
}
function Has-OCR($ocrDir) {
  if (-not (Test-Path $ocrDir)) { return $false }
  $txt = Get-ChildItem $ocrDir -File -ErrorAction SilentlyContinue |
         Where-Object { $_.Extension -ieq '.txt' -and $_.Length -gt 0 }
  return ($txt | Measure-Object).Count -gt 0
}

$Targets = @()
if ($Weeks) {
  $wkList = $Weeks.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d{6}$' }
  Get-ChildItem $FlyersRoot -Directory | Where-Object { $Skip -notcontains $_.Name } | ForEach-Object {
    foreach ($wk in $wkList) {
      $weekDir = Join-Path $_.FullName $wk
      if (Test-Path $weekDir) {
        $Targets += [PSCustomObject]@{ Store=$_.Name; Week=$wk; Path=$weekDir }
      }
    }
  }
} else {
  Get-ChildItem $FlyersRoot -Directory | Where-Object { $Skip -notcontains $_.Name } | ForEach-Object {
    $weeks = Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -match '^\d{6}$' } |
             Sort-Object Name -Descending
    $older = $weeks | Select-Object -Skip $KeepNewest
    foreach ($w in $older) {
      $Targets += [PSCustomObject]@{ Store=$_.Name; Week=$w.Name; Path=$w.FullName }
    }
  }
}

if (-not $Targets) { Write-Host "Nothing to verify/archive." -ForegroundColor Yellow; exit 0 }

$ArchiveFlyers = Join-Path $ArchiveRoot "flyers"
New-Item -ItemType Directory -Force -Path $ArchiveFlyers | Out-Null

$archived = 0; $skipped = 0
foreach ($t in $Targets) {
  $store   = $t.Store
  $week    = $t.Week
  $weekDir = $t.Path

  $pdfDir   = Join-Path $weekDir "pdf"
  $imgDir   = Join-Path $weekDir "raw_images"
  $ocrDir   = Join-Path $weekDir "ocr_txt"
  $exports  = Join-Path $weekDir "exports"

  $hasSource = (Has-Files $pdfDir '.pdf') -or (Has-Files $imgDir @('.png','.jpg','.jpeg','.webp'))
  $hasOCR    = Has-OCR $ocrDir
  $hasOK     = Has-GreenHeartbeat $exports

  if (-not ($hasSource -and $hasOCR -and $hasOK)) {
    $skipped++
    Write-Host ("SKIP {0}\{1} src={2} ocr={3} ok={4}" -f $store,$week,$hasSource,$hasOCR,$hasOK) -ForegroundColor DarkYellow
    continue
  }

  $dest = Join-Path (Join-Path $ArchiveFlyers $store) $week
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  Move-Item -Path $weekDir -Destination $dest

  $archived++
  Write-Host ("Archived {0}\{1} -> {2}" -f $store,$week,$dest) -ForegroundColor Green
}

Write-Host ("Done. Archived: {0}  Skipped: {1}" -f $archived,$skipped) -ForegroundColor Cyan
