# files_to_run/admin/run_admin.ps1
# Deals-4Me Admin Tool (simple + reliable)
# Active options:
#   2) OCR Week (AUTO)  -> ensure structure, convert PDFs->PNGs if needed, OCR images, verify outputs
#   5) Verify Week      -> read-only check

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -------------------------
# Fallback console helpers (MUST EXIST EARLY)
# -------------------------
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

function Pause-AnyKey {
  Write-Host ""
  Read-Host "Press Enter to continue" | Out-Null
}

# -------------------------
# Resolve paths
# -------------------------
$AdminRoot   = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$FilesToRun  = (Resolve-Path -LiteralPath (Join-Path $AdminRoot "..")).Path          # files_to_run
$BackendRoot = (Resolve-Path -LiteralPath (Join-Path $FilesToRun "backend")).Path    # files_to_run/backend

# IMPORTANT: tell store_week_rules.ps1 where the real project root is (the folder that contains flyers/)
$script:D4M_PROJECT_ROOT = (Resolve-Path -LiteralPath (Join-Path $FilesToRun "..")).Path

$RulesFile = Join-Path $BackendRoot "store_week_rules.ps1"
$ThemeFile = Join-Path $AdminRoot "console_theme.ps1"  # optional

# -------------------------
# Load theme (optional) - can override Write-* helpers
# -------------------------
if (Test-Path -LiteralPath $ThemeFile) {
  . $ThemeFile
}

# -------------------------
# Poppler / pdftoppm (REQUIRED for PDF -> PNG)
# -------------------------
function Resolve-PdfToPpmExe {
  # 1) If it's already on PATH
  $cmd = Get-Command pdftoppm -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  # 2) Your known location
  $known = "C:\Users\jwein\OneDrive\Desktop\bin\pdftoppm.exe"
  if (Test-Path -LiteralPath $known) { return $known }

  # 3) Common backup locations
  $candidates = @(
    (Join-Path $env:USERPROFILE "Desktop\bin\pdftoppm.exe"),
    (Join-Path $env:USERPROFILE "bin\pdftoppm.exe")
  )

  foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c) { return $c }
  }

  throw "pdftoppm.exe not found. Put it in Desktop\bin or add Poppler to PATH."
}

$script:PDFTOPPM_EXE = Resolve-PdfToPpmExe
Write-Info "Using pdftoppm: $script:PDFTOPPM_EXE"

# -------------------------
# Load rules (REQUIRED)
# -------------------------
if (-not (Test-Path -LiteralPath $RulesFile)) { throw "Missing rules file: $RulesFile" }
. $RulesFile

# -------------------------
# Input helpers
# -------------------------
function Read-Region {
  Write-Host ""
  Write-Host "Region:"
  Write-Host "  1) NE"
  Write-Host "  2) MIDATL"
  $r = Read-Host "Choose region (default 1)"
  if ([string]::IsNullOrWhiteSpace($r)) { $r = "1" }
  return (Normalize-Region $r)
}

function Read-WeekCode {
  $default = Get-CurrentWeekCode
  Write-Host ""
  $w = Read-Host "Week code (wk_YYYYMMDD or YYYYMMDD) default [$default]"
  if ([string]::IsNullOrWhiteSpace($w)) { $w = $default }
  $wNorm = Normalize-WeekCode $w
  if (-not (Test-WeekCode $wNorm)) { throw "Invalid week code '$w' (expected wk_YYYYMMDD or YYYYMMDD)." }
  Assert-WeekCodeIsSundayStart -WeekCode $wNorm
  return $wNorm
}

function Resolve-StoresFromSelection {
  param(
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$SelectionText
  )

  $all = @(Get-CanonicalStores -Region $Region)
  if (-not $all -or $all.Count -eq 0) { throw "No stores defined for region '$Region'." }

  $t = [string]$SelectionText
  if ($null -eq $t) { $t = "" }
  $t = $t.Trim()

  if ([string]::IsNullOrWhiteSpace($t)) { return $all }
  if ($t -match '^(a|all)$') { return $all }

  if ($t -match '^\d+(\s*,\s*\d+)*$') {
    $idx = @($t.Split(",") | ForEach-Object { [int]($_.Trim()) })
    $picked = @()
    foreach ($i in $idx) {
      if ($i -lt 1 -or $i -gt $all.Count) { throw "Store index '$i' out of range (1..$($all.Count))." }
      $picked += $all[$i-1]
    }
    return $picked
  }

  $parts = @($t.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
  $picked2 = @()
  foreach ($p in $parts) {
    if ($all -notcontains $p) {
      throw "Unknown store slug '$p' for region '$Region'. Expected: $($all -join ', ')"
    }
    $picked2 += $p
  }
  return $picked2
}

function Read-Stores {
  param([Parameter(Mandatory=$true)][string]$Region)

  $stores = @(Get-CanonicalStores -Region $Region)

  Write-Host ""
  Write-Host "Stores for ${Region}:"
  for ($i=0; $i -lt $stores.Count; $i++) {
    "{0,2}) {1}" -f ($i+1), $stores[$i] | Write-Host
  }

  Write-Host ""
  Write-Host "Select stores:"
  Write-Host "  - a  (all, default)"
  Write-Host "  - 1,3,5  (numbers)"
  Write-Host "  - aldi,wegmans  (slugs)"
  $sel = Read-Host "Stores (default a)"
  if ([string]::IsNullOrWhiteSpace($sel)) { $sel = "a" }

  return (Resolve-StoresFromSelection -Region $Region -SelectionText $sel)
}

# -------------------------
# Ensure week + guts
# -------------------------
function Ensure-WeekReady {
  param(
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$WeekCode,
    [Parameter(Mandatory=$true)][string[]]$Stores
  )

  $proj = Get-ProjectRoot
  Test-StoreRootsExist -Region $Region -Stores $Stores -ProjectRoot $proj | Out-Null

  foreach ($s in $Stores) {
    $root = Get-StoreWeekRoot -Region $Region -Store $s -WeekCode $WeekCode -ProjectRoot $proj
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    Ensure-WeekGuts -StoreWeekRoot $root | Out-Null
  }

  Write-Ok "Week folders + guts ensured for selected stores."
}

# -------------------------
# Verify (read-only)
# -------------------------
function Verify-Week {
  param(
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$WeekCode,
    [Parameter(Mandatory=$true)][string[]]$Stores
  )

  $proj = Get-ProjectRoot
  $required = @(
    "raw_pdf",
    "raw_png",
    "manual_imports\excel",
    "manual_imports\csv",
    "ocr",
    "exports\csv",
    "exports\json",
    "logs"
  )

  $fails = @()

  foreach ($s in $Stores) {
    $root = Get-StoreWeekRoot -Region $Region -Store $s -WeekCode $WeekCode -ProjectRoot $proj
    if (-not (Test-Path -LiteralPath $root)) {
      $fails += "MISSING ROOT: $s -> $root"
      continue
    }

    foreach ($rel in $required) {
      $p = Join-Path $root $rel
      if (-not (Test-Path -LiteralPath $p)) {
        $fails += "MISSING: $s -> $rel"
      }
    }
  }

  if ($fails.Count -gt 0) {
    Write-Err "Verify failed:"
    $fails | ForEach-Object { Write-Host ("  - {0}" -f $_) }
    throw "Verify Week failed. Run Option 2 to repair."
  }

  Write-Ok "Verify passed: all selected stores have required week guts."
}

# -------------------------
# Convert PDFs -> PNGs if raw_png is empty
# RETURNS: $true if png inputs exist/created, $false if store has no inputs
# -------------------------
function Ensure-PngInputsFromPdf {
  param(
    [Parameter(Mandatory=$true)][string]$InPdfDir,
    [Parameter(Mandatory=$true)][string]$OutPngDir
  )

  New-Item -ItemType Directory -Force -Path $OutPngDir | Out-Null

  $existing = @(Get-ChildItem -LiteralPath $OutPngDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '^\.(png|jpg|jpeg|tif|tiff)$' })

  if ($existing.Count -gt 0) { return $true }

  $pdfs = @(Get-ChildItem -LiteralPath $InPdfDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -ieq ".pdf" })

  if ($pdfs.Count -eq 0) {
    return $false
  }

  foreach ($pdf in $pdfs) {
    $pdfPath   = $pdf.FullName
    $base      = [IO.Path]::GetFileNameWithoutExtension($pdf.Name)
    $outPrefix = Join-Path $OutPngDir $base

    Write-Info "Converting PDF -> PNG: $($pdf.Name)"
    & $script:PDFTOPPM_EXE -png -r 200 "$pdfPath" "$outPrefix"

    if ($LASTEXITCODE -ne 0) {
      throw "PDF->PNG failed for '$($pdf.Name)'. pdftoppm returned non-zero exit code."
    }
  }

  $after = @(Get-ChildItem -LiteralPath $OutPngDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '^\.(png|jpg|jpeg|tif|tiff)$' })

  if ($after.Count -eq 0) {
    throw "PDF->PNG ran but produced no images in: $OutPngDir"
  }

  return $true
}

# -------------------------
# OCR output check (any txt under ocr_text_auto)
# -------------------------
function Test-OcrOutputsExist {
  param([Parameter(Mandatory=$true)][string]$StoreWeekRoot)

  $t = Join-Path $StoreWeekRoot "ocr_text_auto"
  if (-not (Test-Path -LiteralPath $t)) { return $false }

  $files = @(Get-ChildItem -LiteralPath $t -File -Recurse -ErrorAction SilentlyContinue)
  return ($files.Count -gt 0)
}

# -------------------------
# OCR AUTO (PER STORE): Convert if needed, OCR raw_png, skip stores with no inputs
# -------------------------
function Invoke-OcrAuto {
  param(
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$WeekCode,
    [Parameter(Mandatory=$true)][string[]]$Stores
  )

  $proj = Get-ProjectRoot

  $pyRunner = Join-Path $BackendRoot "ocr_images_to_text.py"
  if (-not (Test-Path -LiteralPath $pyRunner)) {
    throw "Missing OCR runner: $pyRunner"
  }

  $pythonExe = Join-Path (Join-Path $proj ".venv\Scripts") "python.exe"
  $useVenv = Test-Path -LiteralPath $pythonExe

  $okStores = 0
  $skippedStores = 0

  foreach ($s in $Stores) {
    Write-Info "OCR AUTO store: $s"

    $weekRoot = Get-StoreWeekRoot -Region $Region -Store $s -WeekCode $WeekCode -ProjectRoot $proj

    $pdfDir = Join-Path $weekRoot "raw_pdf"
    $pngDir = Join-Path $weekRoot "raw_png"
    $outDir = Join-Path $weekRoot "ocr_text_auto"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null

    $hasInputs = Ensure-PngInputsFromPdf -InPdfDir $pdfDir -OutPngDir $pngDir
    if (-not $hasInputs) {
      Write-Warn "No inputs for '$s' (no PDFs in raw_pdf and no images in raw_png). Skipping."
      $skippedStores += 1
      continue
    }

    if ($useVenv) {
      Write-Info "Using venv python: $pythonExe"
      & $pythonExe $pyRunner --in-dir $pngDir --out-dir $outDir --lang eng
    } else {
      Write-Warn "Venv python not found at: $pythonExe"
      Write-Info "Using Windows launcher: py"
      & py $pyRunner --in-dir $pngDir --out-dir $outDir --lang eng
    }

    if ($LASTEXITCODE -ne 0) {
      throw "OCR AUTO failed for store '$s' (exit code $LASTEXITCODE)."
    }

    if (-not (Test-OcrOutputsExist -StoreWeekRoot $weekRoot)) {
      throw "OCR AUTO ran for '$s' but no OCR output was produced under: $outDir"
    }

    $okStores += 1
  }

  Write-Ok "OCR AUTO finished. ok=$okStores, skipped(no inputs)=$skippedStores"
}

# -------------------------
# Menu
# -------------------------
function Show-Menu {
  Write-Host ""
  Write-Host "Deals-4Me Admin Tool"
  Write-Host "--------------------"
  Write-Host "2) OCR Week (AUTO)   [default]"
  Write-Host "5) Verify Week / Folders (read-only)"
  Write-Host "Q) Quit"
}

# -------------------------
# Main loop
# -------------------------
while ($true) {
  try {
    Clear-Host
    Show-Menu

    $choice = Read-Host "Choose option (default 2)"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "2" }
    $choice = $choice.Trim().ToUpperInvariant()

    if ($choice -eq "Q") { break }

    if ($choice -ne "2" -and $choice -ne "5") {
      Write-Warn "For now only options 2 and 5 are active."
      Pause-AnyKey
      continue
    }

    $region   = Read-Region
    $weekCode = Read-WeekCode
    $stores   = Read-Stores -Region $region

    Write-Host ""
    Write-Info "Selection:"
    Write-Host ("  Region   : {0}" -f $region)
    Write-Host ("  WeekCode : {0}" -f $weekCode)
    Write-Host ("  Stores   : {0}" -f ($stores -join ", "))

    switch ($choice) {
      "2" {
        Write-Info "Option 2: OCR Week (AUTO)"
        Ensure-WeekReady -Region $region -WeekCode $weekCode -Stores $stores
        Invoke-OcrAuto -Region $region -WeekCode $weekCode -Stores $stores
        Write-Ok "Option 2 complete."
      }
      "5" {
        Write-Info "Option 5: Verify Week / Folders (read-only)"
        Verify-Week -Region $region -WeekCode $weekCode -Stores $stores
      }
    }

    Pause-AnyKey
  }
  catch {
    Write-Host ""
    Write-Err $_.Exception.Message
    Pause-AnyKey
  }
}
