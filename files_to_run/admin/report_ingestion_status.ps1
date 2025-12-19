param(
  [Parameter(Mandatory)]
  [string]$Week,

  [Parameter(Mandatory)]
  [string]$FlyersRoot
)

# -----------------------------
# Helpers (disk)
# -----------------------------
function Test-WeekFolderExists {
  param([string]$StoreDir, [string]$Week)
  return (Test-Path -Path (Join-Path $StoreDir $Week) -PathType Container)
}

function Get-StoreRawFileCount {
  param([string]$StoreDir, [string]$Week)

  $weekPath = Join-Path $StoreDir $Week
  if (-not (Test-Path $weekPath)) { return 0 }

  $exts = @("*.pdf","*.png","*.jpg","*.jpeg","*.webp")
  $count = 0
  foreach ($ext in $exts) {
    $count += (Get-ChildItem -Path $weekPath -Recurse -File -Filter $ext -ErrorAction SilentlyContinue | Measure-Object).Count
  }
  return $count
}

# -----------------------------
# Helpers (DB)
# -----------------------------
function Get-SupabaseBaseUrl {
  $b = ($env:SUPABASE_URL ?? "").Trim()
  if ([string]::IsNullOrWhiteSpace($b)) { return "" }
  $b = $b.TrimEnd("/")
  # If someone pasted a REST URL, strip it back to the project base
  $b = $b -replace "/rest/v1.*$",""
  return $b.TrimEnd("/")
}

function Try-DbCount {
  param(
    [Parameter(Mandatory)][string]$Base,
    [Parameter(Mandatory)][hashtable]$Headers,
    [Parameter(Mandatory)][string]$Table,
    [Parameter(Mandatory)][string]$FilterCol,
    [Parameter(Mandatory)][string]$FilterVal,
    [Parameter(Mandatory)][string]$WeekCode
  )

  $tableName = "flyer_items"

  $v1 = [uri]::EscapeDataString($FilterVal)
  $v2 = [uri]::EscapeDataString($WeekCode)

  $url = "$Base/rest/v1/${tableName}?select=id&${FilterCol}=eq.$v1&week_code=eq.$v2"
  Write-Host "[DB DEBUG] $url" -ForegroundColor Yellow

  try {
    $Headers["Prefer"] = "count=exact,head=true"
    $Headers["Accept"] = "application/json"

    $resp = Invoke-WebRequest -Method Get -Uri $url -Headers $Headers -ErrorAction Stop
    $cr = $resp.Headers["Content-Range"]
    if (-not $cr) { return @{ ok=$true; count=0; err=$null } }

    if ($cr -is [System.Array]) { $cr = ($cr -join "") }

    if ($cr -match "/(\d+)\s*$") {
      return @{ ok=$true; count=([int]$Matches[1]); err=$null }
    }

    return @{ ok=$true; count=0; err=$null }
  }
  catch {
    $msg = $_.Exception.Message
    $detail = $null
    if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $detail = $_.ErrorDetails.Message }
    return @{ ok=$false; count=-1; err=("$msg" + ($(if($detail){"`n$detail"}else{""}))) }
  }
}

function Get-DbItemCount {
  param(
    [Parameter(Mandatory)][string]$StoreSlug,
    [Parameter(Mandatory)][string]$WeekCode
  )

  $base = Get-SupabaseBaseUrl
  $key  = ($env:SUPABASE_ANON_KEY ?? "").Trim()

  if ([string]::IsNullOrWhiteSpace($base) -or [string]::IsNullOrWhiteSpace($key)) {
    return @{ ok=$false; count=-1; err="Missing SUPABASE_URL or SUPABASE_ANON_KEY in this PowerShell session." }
  }

  $headers = @{
    "apikey"        = $key
    "Authorization" = "Bearer $key"
    "Prefer"        = "count=exact,head=true"
    "Accept"        = "application/json"
  }

  # Map folder slug -> flyer_items.brand (what your table actually contains)
  $brandMap = @{
    "aldi"                    = "Aldi"
    "big_y"                   = "Big Y"
    "hannaford"               = "Hannaford"
    "market_basket"           = "Market Basket"
    "price_chopper_market_32" = "Price Chopper / Market 32"
    "pricerite"               = "PriceRite"
    "roche_bros"              = "Roche Bros"
    "shaws"                   = "Shaw's"
    "stop_and_shop_ct"        = "Stop & Shop"
    "stop_and_shop_mari"      = "Stop & Shop"
    "trucchis"                = "Trucchi's"
    "wegmans"                 = "Wegmans"
    "whole_foods"             = "Whole Foods"
  }

  $brand = $brandMap[$StoreSlug]
  if ([string]::IsNullOrWhiteSpace($brand)) {
    return @{ ok=$false; count=-1; err="No brand mapping for store slug '$StoreSlug'." }
  }

  return Try-DbCount -Base $base -Headers $headers -Table "flyer_items" -FilterCol "brand" -FilterVal $brand -WeekCode $WeekCode
}

# -----------------------------
# Main
# -----------------------------
Write-Host ""
Write-Host "Ingestion Status Report" -ForegroundColor Cyan
Write-Host "FlyersRoot: $FlyersRoot"
Write-Host "Week:      $Week"
Write-Host ""

$storeDirs = Get-ChildItem -Path $FlyersRoot -Directory -ErrorAction Stop | Sort-Object Name

# Chunk 1: Disk only
Write-Host "Ingestion Status Report (Chunk 1: Disk counts only)" -ForegroundColor Cyan
Write-Host ("{0,-22} {1,8}  {2,-10}" -f "Store", "RawFiles", "WeekFolder")
Write-Host ("-" * 55)

foreach ($store in $storeDirs) {
  $storeName = $store.Name
  if ($storeName.StartsWith("_")) { continue }

  $rawCount = Get-StoreRawFileCount -StoreDir $store.FullName -Week $Week
  $hasWeek  = if (Test-WeekFolderExists -StoreDir $store.FullName -Week $Week) { "yes" } else { "no" }

  Write-Host ("{0,-22} {1,8}  {2,-10}" -f $storeName, $rawCount, $hasWeek)
}

Write-Host ""
Write-Host "Ingestion Status Report (Chunk 2: Disk + DB)" -ForegroundColor Cyan
Write-Host ("{0,-22} {1,8}  {2,8}  {3,-10}  {4}" -f "Store", "RawFiles", "DBItems", "WeekFolder", "Status")
Write-Host ("-" * 78)

$firstDbErr = $null

foreach ($store in $storeDirs) {
  $storeName = $store.Name
  if ($storeName.StartsWith("_")) { continue }

  $rawCount = Get-StoreRawFileCount -StoreDir $store.FullName -Week $Week
  $hasWeek  = Test-WeekFolderExists -StoreDir $store.FullName -Week $Week

  $db = Get-DbItemCount -StoreSlug $storeName -WeekCode $Week
  $dbCount = $db.count

  if ($dbCount -lt 0 -and -not $firstDbErr) { $firstDbErr = $db.err }

  $status =
    if ($dbCount -lt 0) { "DB_ERROR" }
    elseif ($rawCount -gt 0 -and $dbCount -gt 0) { "OK" }
    elseif ($rawCount -gt 0 -and $dbCount -eq 0) { "DISK_ONLY" }
    elseif ($rawCount -eq 0 -and $dbCount -gt 0) { "DB_ONLY" }
    else { "MISSING_BOTH" }

  $weekFolderLabel = if ($hasWeek) { "yes" } else { "no" }

  Write-Host ("{0,-22} {1,8}  {2,8}  {3,-10}  {4}" -f $storeName, $rawCount, $dbCount, $weekFolderLabel, $status)
}

Write-Host ""
Write-Host "Legend:" -ForegroundColor DarkGray
Write-Host "  OK           = Flyers on disk AND DB has rows for this store/week" -ForegroundColor DarkGray
Write-Host "  DISK_ONLY    = Flyers on disk but DB has 0 rows for this store/week" -ForegroundColor DarkGray
Write-Host "  MISSING_BOTH = No week folder on disk AND DB has 0 rows" -ForegroundColor DarkGray
Write-Host "  DB_ONLY      = No week folder on disk but DB has rows (old data / different disk path)" -ForegroundColor DarkGray
Write-Host "  DB_ERROR     = DB query failed (see error below)" -ForegroundColor DarkGray

if ($firstDbErr) {
  Write-Host ""
  Write-Host "[DB ERROR] First DB failure detail:" -ForegroundColor Red
  Write-Host $firstDbErr -ForegroundColor Red
  Write-Host ""
  Write-Host "[NOTE] Confirm these env vars in the SAME PowerShell session:" -ForegroundColor Yellow
  Write-Host "  `$env:SUPABASE_URL and `$env:SUPABASE_ANON_KEY (sb_publishable_...)" -ForegroundColor Yellow
}
