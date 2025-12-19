<# 
 Archives verified weekly flyer folders to an external drive after checking Supabase.
 Folder layout expected: <LocalRoot>\Flyers\<StoreName>\<WeekFolder>

 Week folder name can be: YYYY-MM-DD, YYYYMMDD, MMDDYYYY, or MMDDYY (assumed 20YY).
 Writes: .\ArchiveMoves-<timestamp>.csv and .\ArchiveMoves-<timestamp>.log

 USAGE (example):
   pwsh -File .\Archive-Flyers.ps1

 Optional params:
   -KeepWeeks 2            # keep 2 most recent weeks locally
   -Store "Aldi"          # only process this store
   -DryRun                # show what would happen; do NOT move
#>

param(
  [int]$KeepWeeks = 1,
  [string]$Store = "",
  [switch]$DryRun
)

# ========== CONFIG ==========
# Local working root (current week(s) live here)
$LocalRoot   = "C:\Deals-4Me\flyers"         # <-- CHANGE ME (parent of \Flyers\...)
# External/archive root (your 1TB drive)
$ArchiveRoot = "E:\Deals4MeArchive\Flyers"   # <-- CHANGE ME

# Supabase REST (PostgREST) — public anon key that can read your public tables
$SupabaseUrl = "https://YOUR-PROJECT-REF.supabase.co"  # <-- CHANGE ME
$SupabaseKey = "YOUR_SUPABASE_ANON_KEY"                # <-- CHANGE ME

# Table names/columns used for verification
$FlyersTable = "flyers"
$PricesTable = "store_prices"
$StoreCol    = "store_name"
$WeekCol     = "week_start_date"   # DATE in ISO (YYYY-MM-DD) in your DB
# ============================

# ---- Setup logging
$ts = (Get-Date).ToString("yyyyMMdd-HHmmss")
$LogPath = ".\ArchiveMoves-$ts.log"
$CsvPath = ".\ArchiveMoves-$ts.csv"

function Write-Log {
  param([string]$msg, [string]$level = "INFO")
  $line = "[{0}] {1} {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $level.PadRight(5), $msg
  $line | Tee-Object -FilePath $LogPath -Append
}

# ---- HTTP helpers (Supabase)
$Headers = @{
  "apikey"        = $SupabaseKey
  "Authorization" = "Bearer $SupabaseKey"
  "Accept-Profile"= "public"
  "Prefer"        = "count=exact"
}

function Get-TableCount {
  param(
    [string]$Table,
    [string]$FilterQuery # e.g., "store_name=eq.Aldi&week_start_date=eq.2025-10-27"
  )
  $uri = "$SupabaseUrl/rest/v1/$Table?select=id&$FilterQuery"
  try {
    $null = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers -ResponseHeadersVariable rh -ErrorAction Stop
    # PostgREST returns Content-Range: 0-0/COUNT (even if body empty)
    $cr = $rh.'Content-Range'
    if (-not $cr) { return 0 }
    # parse trailing /COUNT
    if ($cr -match "/(\d+)$") { return [int]$Matches[1] } else { return 0 }
  } catch {
    Write-Log "Supabase count failed for $Table ($FilterQuery): $($_.Exception.Message)" "WARN"
    return 0
  }
}

# ---- Date parsing (handles multiple folder styles)
function Convert-ToIsoDate {
  param([string]$name)
  $n = $name.Trim()

  # Already ISO
  if ($n -match '^\d{4}-\d{2}-\d{2}$') { return $n }

  # YYYYMMDD
  if ($n -match '^(?<y>\d{4})(?<m>\d{2})(?<d>\d{2})$') {
    $y=$Matches.y; $m=$Matches.m; $d=$Matches.d
    return "{0}-{1}-{2}" -f $y, $m, $d
  }

  # MMDDYYYY
  if ($n -match '^(?<m>\d{2})(?<d>\d{2})(?<y>\d{4})$') {
    $y=$Matches.y; $m=$Matches.m; $d=$Matches.d
    return "{0}-{1}-{2}" -f $y, $m, $d
  }

  # MMDDYY -> assume 20YY
  if ($n -match '^(?<m>\d{2})(?<d>\d{2})(?<y>\d{2})$') {
    $yy=[int]$Matches.y; $y = "{0}{1:00}" -f "20", $yy
    $m=$Matches.m; $d=$Matches.d
    return "{0}-{1}-{2}" -f $y, $m, $d
  }

  # Try to parse liberally (last resort)
  try {
    $dt = [datetime]::Parse($n)
    return $dt.ToString("yyyy-MM-dd")
  } catch { return $null }
}

# ---- Find all <Store>\<WeekFolder> paths
$flyersRoot = Join-Path $LocalRoot "Flyers"
if (-not (Test-Path $flyersRoot)) {
  Write-Log "Local Flyers root not found: $flyersRoot" "ERROR"
  throw "Local Flyers root missing."
}

$storeDirs = Get-ChildItem -Path $flyersRoot -Directory -ErrorAction SilentlyContinue |
  Where-Object { 
    if ($Store) { $_.Name -ieq $Store } else { $true }
  }

if (-not $storeDirs) {
  Write-Log "No store folders found under $flyersRoot (filter Store='$Store')" "WARN"
}

# Build list of (Store, WeekISO, FullPath)
$items = @()
foreach ($sd in $storeDirs) {
  $weekDirs = Get-ChildItem -Path $sd.FullName -Directory -ErrorAction SilentlyContinue |
    Where-Object {
      # Skip “raw” buckets
      $_.Name -notmatch 'raw\s*(pdfs?|images?)' -and $_.Name -notmatch '^raw$'
    }

  foreach ($wd in $weekDirs) {
    $iso = Convert-ToIsoDate $wd.Name
    if (-not $iso) {
      Write-Log "Skipping (cannot parse date): $($wd.FullName)" "WARN"
      continue
    }
    $items += [pscustomobject]@{
      Store      = $sd.Name
      WeekIso    = $iso
      FullPath   = $wd.FullName
      WeekFolder = $wd.Name
    }
  }
}

if (-not $items) {
  Write-Log "No week folders discovered to evaluate." "WARN"
  "" | Out-File -FilePath $CsvPath # create empty CSV
  return
}

# Determine most recent weeks across ALL stores to keep
$recentWeeks =
  $items.WeekIso |
  Sort-Object {[datetime]$_} -Descending |
  Select-Object -Unique |
  Select-Object -First $KeepWeeks

Write-Log "Keeping the most recent $KeepWeeks week(s) locally: $(($recentWeeks -join ', '))"

# Prepare CSV
$csv = [System.Collections.Generic.List[psobject]]::new()

# Process each store/week
foreach ($group in $items | Group-Object Store, WeekIso | Sort-Object { [datetime]$_.Group[0].WeekIso } ) {
  $store  = $group.Group[0].Store
  $week   = $group.Group[0].WeekIso
  $paths  = $group.Group.FullPath

  $keepLocal = $recentWeeks -contains $week

  # Verify in Supabase (both tables must have >=1 row, tweak if you only need one)
  $fFilter = "$StoreCol=eq.$([uri]::EscapeDataString($store))&$WeekCol=eq.$week"
  $pFilter = "$StoreCol=eq.$([uri]::EscapeDataString($store))&$WeekCol=eq.$week"

  $flyerCount  = Get-TableCount -Table $FlyersTable -FilterQuery $fFilter
  $pricesCount = Get-TableCount -Table $PricesTable -FilterQuery $pFilter

  $ok = ($flyerCount -ge 1 -and $pricesCount -ge 1)

  $dest = Join-Path (Join-Path $ArchiveRoot $store) $week

  foreach ($src in $paths | Select-Object -Unique) {
    $action = if ($keepLocal) { "KEEP" } elseif ($ok) { "MOVE" } else { "BLOCKED" }

    # Log CSV row
    $row = [pscustomobject]@{
      Timestamp    = (Get-Date)
      Store        = $store
      Week         = $week
      SourcePath   = $src
      DestPath     = $dest
      FlyerRows    = $flyerCount
      PriceRows    = $pricesCount
      Action       = $action
      DryRun       = [bool]$DryRun
    }
    $csv.Add($row) | Out-Null

    switch ($action) {
      "KEEP"    { Write-Log "KEEP local: $store / $week -> $src (recent week)"; continue }
      "BLOCKED" { Write-Log "BLOCKED (no DB rows): $store / $week -> $src (flyers=$flyerCount, prices=$pricesCount)" "WARN"; continue }
      "MOVE" {
        Write-Log "MOVE: $store / $week -> $dest"

        if ($DryRun) { continue }

        try {
          if (-not (Test-Path $dest)) {
            New-Item -ItemType Directory -Path $dest -Force | Out-Null
          }

          # If destination already exists, merge contents (robust for re-runs)
          $basename = Split-Path $src -Leaf
          $target   = Join-Path $dest $basename

          if (-not (Test-Path $target)) {
            Move-Item -Path $src -Destination $dest -Force
          } else {
            # Merge: copy then remove original
            Copy-Item -Path (Join-Path $src "*") -Destination $target -Recurse -Force
            Remove-Item -Path $src -Recurse -Force
          }
        } catch {
          Write-Log "MOVE FAILED: $src -> $dest :: $($_.Exception.Message)" "ERROR"
        }
      }
    }
  }
}

# Write CSV
$csv | Sort-Object Timestamp | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
Write-Log "Done. Summary CSV: $CsvPath"
