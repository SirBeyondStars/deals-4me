<#  auto_archive_old_weeks.ps1  (v2)
    Move flyer week folders older than a threshold to an archive drive,
    write a CSV summary, and prune empty folders.

    Layout:  <ProjectRoot>\flyers\<store>\<MMDDYY>\...
    Archive: <ArchiveRoot>\flyers\<store>\<MMDDYY>\...
#>

[CmdletBinding(SupportsShouldProcess)]
param(
  [int]$MinAgeDays = 14,  # 2+ weeks
  [string]$ProjectRoot = "C:\Users\jwein\OneDrive\Desktop\deals-4me",
  [string]$ArchiveRoot = "D:\deals-4me-archive",
  [switch]$RequireContent = $true,  # require PDFs/Images in raw_pdfs/raw_images
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# ----- Paths & logging -----
$FlyersRoot = Join-Path $ProjectRoot 'flyers'
$LogDir     = Join-Path $ProjectRoot 'logs\tasks'
New-Item -ItemType Directory -Force -Path $LogDir       | Out-Null
New-Item -ItemType Directory -Force -Path $ArchiveRoot   | Out-Null

$stamp     = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile   = Join-Path $LogDir ("auto_archive_" + $stamp + ".log")
$CsvFile   = Join-Path $LogDir ("archive_summary_" + $stamp + ".csv")
$MasterCsv = Join-Path $ArchiveRoot "archive_index.csv"

Start-Transcript -Path $LogFile -Append | Out-Null
Write-Host "Auto-archive starting (MinAgeDays=$MinAgeDays, RequireContent=$RequireContent, DryRun=$DryRun)" -ForegroundColor Cyan
Write-Host "Flyers:   $FlyersRoot" -ForegroundColor DarkCyan
Write-Host "Archive:  $ArchiveRoot" -ForegroundColor DarkCyan
Write-Host "Summary:  $CsvFile"     -ForegroundColor DarkCyan

if (-not (Test-Path $FlyersRoot)) { throw "Flyers root not found: $FlyersRoot" }

# ----- Helpers -----
function Parse-WeekKey([string]$key) {
  if ($key -notmatch '^\d{6}$') { return $null }  # MMddyy
  $mm = [int]$key.Substring(0,2); $dd = [int]$key.Substring(2,2); $yy = [int]$key.Substring(4,2)
  $yyyy = 2000 + $yy
  try { return [datetime]::new($yyyy, $mm, $dd) } catch { return $null }
}

function Get-CountAndSize($dir, $exts) {
  $count = 0; $bytes = 0L
  if (Test-Path $dir) {
    Get-ChildItem $dir -File -ErrorAction SilentlyContinue | ForEach-Object {
      if ($exts -contains $_.Extension.ToLower()) { $count++; $bytes += $_.Length }
    }
  }
  return @{ Count = $count; Bytes = $bytes }
}

function Has-AnySource($weekDir) {
  $exts = @('.pdf','.png','.jpg','.jpeg','.webp')
  $p1 = Get-CountAndSize (Join-Path $weekDir 'raw_pdfs')   $exts
  $p2 = Get-CountAndSize (Join-Path $weekDir 'raw_images') $exts
  return ($p1.Count + $p2.Count) -gt 0
}

function Get-WeekStats($weekDir) {
  $pdf   = Get-CountAndSize (Join-Path $weekDir 'raw_pdfs')   @('.pdf')
  $image = Get-CountAndSize (Join-Path $weekDir 'raw_images') @('.png','.jpg','.jpeg','.webp')
  $totalBytes = $pdf.Bytes + $image.Bytes
  return @{
    PdfCount   = $pdf.Count
    ImgCount   = $image.Count
    TotalBytes = $totalBytes
    TotalMB    = [Math]::Round($totalBytes / 1MB, 2)
  }
}

function Prune-EmptyParents($weekDir, $stopAt) {
  # Remove empty dirs upward until $stopAt (exclusive)
  $current = $weekDir
  while ($true) {
    $parent = Split-Path $current -Parent
    if (-not $parent -or ($parent -ieq $stopAt)) { break }
    $items = Get-ChildItem $parent -Force -ErrorAction SilentlyContinue
    if (-not $items) {
      try { Remove-Item $parent -Force -ErrorAction Stop } catch {}
      $current = $parent
    } else {
      break
    }
  }
}

# ----- Collect candidates -----
$now        = Get-Date
$cutoffDate = $now.AddDays(-1 * $MinAgeDays)
$skipStores = @('_inbox','logs','run','_week_template','_templates')

$candidates = @()
Get-ChildItem $FlyersRoot -Directory | Where-Object { $skipStores -notcontains $_.Name } | ForEach-Object {
  $store = $_.Name
  $weeks = Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match '^\d{6}$' }

  foreach ($w in $weeks) {
    $dt = Parse-WeekKey $w.Name
    if ($null -eq $dt) { continue }
    if ($dt -le $cutoffDate) {
      $candidates += [PSCustomObject]@{
        Store   = $store
        WeekKey = $w.Name
        Date    = $dt
        Path    = $w.FullName
      }
    }
  }
}

if (-not $candidates) {
  Write-Host "No weeks older than $MinAgeDays days to archive." -ForegroundColor Yellow
  Stop-Transcript | Out-Null
  return
}

$candidates = $candidates | Sort-Object Store, Date
$results = New-Object System.Collections.Generic.List[object]

# ----- Archive -----
$archived = 0; $skipped = 0
foreach ($c in $candidates) {
  $stats = Get-WeekStats $c.Path
  $hasContent = Has-AnySource $c.Path
  $reason = ""

  if ($RequireContent -and -not $hasContent) {
    $skipped++
    $reason = "No content in raw_pdfs/raw_images"
    Write-Host ("SKIP {0}\{1} — {2}" -f $c.Store, $c.WeekKey, $reason) -ForegroundColor DarkYellow

    $results.Add([PSCustomObject]@{
      ArchivedAt = $now
      Store      = $c.Store
      WeekKey    = $c.WeekKey
      WeekDate   = $c.Date.ToString('yyyy-MM-dd')
      PdfCount   = $stats.PdfCount
      ImgCount   = $stats.ImgCount
      SizeMB     = $stats.TotalMB
      Action     = "SKIPPED"
      Reason     = $reason
    }) | Out-Null
    continue
  }

  $dest = Join-Path (Join-Path $ArchiveRoot 'flyers') (Join-Path $c.Store $c.WeekKey)
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }

  $actionText = "Move {0}\{1}  ->  {2}" -f $c.Store, $c.WeekKey, $dest
  if ($DryRun) {
    Write-Host "[DryRun] $actionText" -ForegroundColor Gray
    $results.Add([PSCustomObject]@{
      ArchivedAt = $now
      Store      = $c.Store
      WeekKey    = $c.WeekKey
      WeekDate   = $c.Date.ToString('yyyy-MM-dd')
      PdfCount   = $stats.PdfCount
      ImgCount   = $stats.ImgCount
      SizeMB     = $stats.TotalMB
      Action     = "DRYRUN"
      Reason     = ""
    }) | Out-Null
  } else {
    Write-Host $actionText -ForegroundColor Green
    Move-Item -Path $c.Path -Destination $dest
    # prune empty leftovers up to the store folder
    Prune-EmptyParents $dest (Join-Path $FlyersRoot $c.Store)

    $archived++
    $results.Add([PSCustomObject]@{
      ArchivedAt = (Get-Date)
      Store      = $c.Store
      WeekKey    = $c.WeekKey
      WeekDate   = $c.Date.ToString('yyyy-MM-dd')
      PdfCount   = $stats.PdfCount
      ImgCount   = $stats.ImgCount
      SizeMB     = $stats.TotalMB
      Action     = "ARCHIVED"
      Reason     = ""
    }) | Out-Null
  }
}

# ----- Write summaries -----
$results | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $CsvFile
if (-not $DryRun) {
  if (Test-Path $MasterCsv) {
    $results | Export-Csv -NoTypeInformation -Encoding UTF8 -Append -Path $MasterCsv
  } else {
    $results | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $MasterCsv
  }
}

Write-Host ("Done. Archived: {0}   Skipped: {1}" -f $archived, $skipped) -ForegroundColor Cyan
Write-Host ("Run summary: {0}" -f $CsvFile) -ForegroundColor DarkCyan
Write-Host ("Master index: {0}" -f $MasterCsv) -ForegroundColor DarkCyan

Stop-Transcript | Out-Null

if (-not $env:WT_SESSION -and -not $env:TERM_PROGRAM) {
  Read-Host "`nPress Enter to close"
}
