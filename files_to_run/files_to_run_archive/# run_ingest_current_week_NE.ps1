# run_ingest_current_week_NE.ps1 (v3)

param([string]$WeekOverride)  # e.g. "Week46" or "111625"
$ErrorActionPreference = "Stop"

# --- Paths ---
$ProjectRoot = "C:\Users\jwein\OneDrive\Desktop\deals-4me"
$VenvPy      = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python      = (Test-Path $VenvPy) ? $VenvPy : "py"
Set-Location $ProjectRoot

# --- Console helpers ---
function Write-Ok   ($m){ Write-Host $m -ForegroundColor Green }
function Write-Info ($m){ Write-Host $m -ForegroundColor Cyan }
function Write-Warn ($m){ Write-Host $m -ForegroundColor Yellow }
function Write-Err  ($m){ Write-Host $m -ForegroundColor Red }

function Find-FirstExistingFolder { param([string]$Base,[string[]]$Candidates)
  foreach ($c in $Candidates) { $p = Join-Path $Base $c; if (Test-Path $p) { return $p } }; return $null
}
function Get-LatestWeekFolder { param([string]$StoreRoot)
  if ($WeekOverride) { $wo = Join-Path $StoreRoot $WeekOverride; if (Test-Path $wo) { return Split-Path $wo -Leaf } }
  $weekStyle = Get-ChildItem $StoreRoot -Directory -Filter "Week*" -ErrorAction SilentlyContinue | Sort-Object { $_.Name -replace '\D','' } -Descending
  if ($weekStyle) { return $weekStyle[0].Name }
  $dateStyle = Get-ChildItem $StoreRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{6}$' } | Sort-Object Name -Descending
  if ($dateStyle) { return $dateStyle[0].Name }
  return $null
}

# --- Auto-detect stores ---
$FlyersRoot = Join-Path $ProjectRoot "flyers"
$stores = Get-ChildItem $FlyersRoot -Directory -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -notmatch '(^_|logs$|run$)' } |
          Select-Object -ExpandProperty Name
if (-not $stores) { Write-Err "No store folders under $FlyersRoot"; exit 1 }

Write-Info "Ingest: stores → $($stores -join ', ')"
if ($WeekOverride) { Write-Info "Week override: $WeekOverride" }

foreach ($store in $stores) {
  $storeRoot  = Join-Path $FlyersRoot $store
  $weekFolder = Get-LatestWeekFolder -StoreRoot $storeRoot
  if (-not $weekFolder) { Write-Warn "Skip $store: no WeekNN/MMDDYY folder"; continue }

  $base   = Join-Path $storeRoot $weekFolder
  $imgDir = Find-FirstExistingFolder -Base $base -Candidates @("raw_images","images","pages_png")
  $pdfDir = Find-FirstExistingFolder -Base $base -Candidates @("pdf","raw_pdfs")

  $imgs = if ($imgDir) { Get-ChildItem $imgDir -File -Include *.png,*.jpg,*.jpeg,*.webp -ErrorAction SilentlyContinue } else { @() }
  $pdfs = if ($pdfDir) { Get-ChildItem $pdfDir -File -Filter *.pdf -ErrorAction SilentlyContinue } else { @() }

  Write-Host ""; Write-Info ("→ Processing {0} ({1})" -f $store, $weekFolder)
  Write-Host ("    Paths → pdf: {0} | images: {1}" -f ($pdfDir ?? "<none>"), ($imgDir ?? "<none>")) -ForegroundColor DarkGray
  Write-Host ("    Found  {0} PDF(s), {1} image(s)" -f $pdfs.Count, $imgs.Count) -ForegroundColor DarkGray

  if ($imgs.Count -eq 0) {
    if ($pdfs.Count -gt 0) { Write-Warn "    PDFs exist but no images; run export/OCR first: files_to_run\run_export_and_ocr_all.ps1 -WeekOverride $weekFolder" }
    else { Write-Warn "    No inputs for $store ($weekFolder)" }
    continue
  }

  $runner = Join-Path $ProjectRoot "scripts\run_all_stores.py"
  if (-not (Test-Path $runner)) { Write-Err "Runner not found: $runner"; continue }

  $pyArgs = @("scripts\run_all_stores.py","--store",$store,"--images","--ingest","--week",$weekFolder)
  Write-Host ("    ▶  py {0}" -f ($pyArgs -join ' ')) -ForegroundColor DarkGray
  & $Python @pyArgs
  if ($LASTEXITCODE -ne 0) { Write-Err ("    ✗ ERROR ingesting {0} ({1})" -f $store,$weekFolder) }
  else { Write-Ok ("    ✓ Done {0} ({1})" -f $store,$weekFolder) }
}

Write-Host ""; Write-Ok "All done."
