<# 
 Archives verified weekly flyer folders to an external drive after checking Supabase.
 Folder layout expected: <LocalRoot>\Flyers\<StoreName>\<WeekFolder>

 Week folder name can be: YYYY-MM-DD, YYYYMMDD, MMDDYYYY, or MMDDYY (assumed 20YY).
 Writes: .\ArchiveMoves-<timestamp>.csv and .\ArchiveMoves-<timestamp>.log

 USAGE (example):
   pwsh -File .\Archive-Flyers.ps1

 Optional params:
   -KeepWeeks 2      # keep 2 most recent weeks locally
   -Store "Aldi"     # only process this store
   -DryRun           # show what would happen; do NOT move
#>

param(
  [int]$KeepWeeks = 1,
  [string]$Store = "",
  [switch]$DryRun
)

# ========== CONFIG ==========
# Local working root (current week(s) live here)
$LocalRoot   = "C:\Deals-4Me\flyers"         # <-- CHANGE ME
# External/archive root (your 1TB drive)
$ArchiveRoot = "E:\Deals4MeArchive\Flyers"   # <-- CHANGE ME

# Supabase REST (PostgREST) endpoint + anon key
$SupabaseUrl = "https://YOUR-PROJECT-REF.supabase.co"  # <-- CHANGE ME
$SupabaseKey = "YOUR_SUPABASE_ANON_KEY"                # <-- CHANGE ME

# Table/column names
$FlyersTable = "flyers"
$PricesTable = "store_prices"
$StoreCol    = "store_name"
$WeekCol     = "week_start_date"
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
  param([string]$Table, [string]$FilterQuery)
  $uri = "$SupabaseUrl/rest/v1/$Table?select=id&$FilterQuery"
  try {
    $null = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers -ResponseHeadersVariable rh -ErrorAction Stop
    $cr = $rh.'Content-Range'
    if (-not $cr) { return 0 }
    if ($cr -match "/(\d+)$") { return [int]$Matches[1] } else { return 0 }
  } catch {
    Write-Log "Supabase count failed for $Table ($FilterQuery): $($_.Exception.Message)" "WARN"
    return 0
  }
}

# ---- Date parsing helper
function Convert-ToIsoDate {
  param([string]$name)
  $n = $name.Trim()
  if ($n -match '^\d{4}-\d{2}-\d{2}$') { return $n }
  if ($n -match '^(?<y>\d{4})(?<m>\d{2})(?<d>\d{2})$') { return "$($Matches.y)-$($Matches.m)-$($Matches.d)" }
  if ($n -match '^(?<m>\d{2})(?<d>\d{2})(?<y>\d{4})$') { return "$($Matches.y)-$($Matches.m)-$($Matches.d)" }
  if ($n -match '^(?<m>\d{2})(?<d>\d{2})(?<y>\d{2})$') {
    $y = "20$($Matches.y)"
    return "$y-$($Matches.m)-$($Matches.d)"
  }
  try { ([datetime]::Parse($n)).ToString("yyyy-MM-dd") } catch { return $null }
}

# ---- Find all store/week folders
$flyersRoot = Join-Path $LocalRoot "Flyers"
if (-not (Test-Path $flyersRoot)) {
  Write-Log "Local Flyers root not found: $flyersRoot" "ERROR"
  throw "Local Flyers root missing."
}

$storeDirs = Get-ChildItem -Path $flyersRoot -Directory -ErrorAction SilentlyContinue |
  Where-Object { if ($Store) { $_.Name -ieq $Store } else { $true } }

if (-not $storeDirs) { Write-Log "No store folders found under $flyersRoot" "WARN" }

$items = @()
foreach ($sd in $storeDirs) {
  $weekDirs = Get-ChildItem -Path $sd.FullName -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notmatch 'raw\s*(pdfs?|images?)' -and $_.Name -notmatch '^raw$' }
  foreach ($wd in $weekDirs) {
    $iso = Convert-ToIsoDate $wd.Name
    if (-not $iso) { Write-Log "Skipping (cannot parse date): $($wd.FullName)" "WARN"; continue }
    $items += [pscustomobject]@{ Store=$sd.Name; WeekIso=$iso; FullPath=$wd.FullName }
  }
}

if (-not $items) { Write-Log "No week folders found."; return }

# Keep N most recent
$recentWeeks = $items.WeekIso | Sort-Object {[datetime]$_} -Descending | Select-Object -Unique -First $KeepWeeks
Write-Log "Keeping the most recent $KeepWeeks week(s): $(($recentWeeks -join ', '))"

$csv = [System.Collections.Generic.List[psobject]]::new()

foreach ($group in $items | Group-Object Store, WeekIso) {
  $store = $group.Group[0].Store
  $week  = $group.Group[0].WeekIso
  $paths = $group.Group.FullPath
  $keep  = $recentWeeks -contains $week

  $fFilter = "$StoreCol=eq.$([uri]::EscapeDataString($store))&$WeekCol=eq.$week"
  $pFilter = "$StoreCol=eq.$([uri]::EscapeDataString($store))&$WeekCol=eq.$week"

  $flyerCount  = Get-TableCount -Table $FlyersTable -FilterQuery $fFilter
  $pricesCount = Get-TableCount -Table $PricesTable -FilterQuery $pFilter
  $ok = ($flyerCount -ge 1 -and $pricesCount -ge 1)

  $dest = Join-Path (Join-Path $ArchiveRoot $store) $week

  foreach ($src in $paths | Select-Object -Unique) {
    $action = if ($keep) { "KEEP" } elseif ($ok) { "MOVE" } else { "BLOCKED" }
    $row = [pscustomobject]@{
      Timestamp=(Get-Date); Store=$store; Week=$week; SourcePath=$src; DestPath=$dest;
      FlyerRows=$flyerCount; PriceRows=$pricesCount; Action=$action; DryRun=[bool]$DryRun
    }
    $csv.Add($row) | Out-Null

    switch ($action) {
      "KEEP"    { Write-Log "KEEP local: $store / $week -> $src"; continue }
      "BLOCKED" { Write-Log "BLOCKED: $store / $week (no DB rows)" "WARN"; continue }
      "MOVE" {
        Write-Log "MOVE: $store / $week -> $dest"
        if ($DryRun) { continue }
        try {
          if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
          Move-Item -Path $src -Destination $dest -Force
        } catch { Write-Log "MOVE FAILED: $src -> $dest :: $($_.Exception.Message)" "ERROR" }
      }
    }
  }
}

$csv | Sort-Object Timestamp | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
Write-Log "Done. Summary CSV: $CsvPath"
