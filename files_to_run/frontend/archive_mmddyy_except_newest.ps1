# ===== archive_mmddyy_except_newest.ps1 =====
[CmdletBinding(SupportsShouldProcess)]
param(
  [int]$KeepNewest = 1,
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$ArchiveRoot = "D:\deals-4me-archive",
  [switch]$DoIt
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'console_theme.ps1')

$FlyersRoot = Join-Path $ProjectRoot 'flyers'
if (-not (Test-Path $FlyersRoot)) { throw "Flyers root not found: $FlyersRoot" }

$LogDir = Join-Path $ProjectRoot 'logs\tasks'
New-Item -ItemType Directory -Force -Path $LogDir,$ArchiveRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogFile = Join-Path $LogDir ("archive_mmddyy_except_newest_{0}.log" -f $stamp)
$CsvFile = Join-Path $LogDir ("archive_mmddyy_except_newest_{0}.csv" -f $stamp)
try { Start-Transcript -Path $LogFile -Append | Out-Null } catch {}

Write-Title ("Archive MMDDYY except newest (KeepNewest={0}, DoIt={1})" -f $KeepNewest,$DoIt.IsPresent)
Write-Info  ("Flyers:   {0}" -f $FlyersRoot)
Write-Info  ("Archive:  {0}" -f $ArchiveRoot)

function Parse-MmDdYy([string]$key){
  if ($key -notmatch '^\d{6}$') { return $null }
  $mm=[int]$key.Substring(0,2); $dd=[int]$key.Substring(2,2); $yy=[int]$key.Substring(4,2)
  try { [datetime]::new(2000+$yy,$mm,$dd) } catch { $null }
}

$results = New-Object System.Collections.Generic.List[object]
$moveCount=0;$skipCount=0

Get-ChildItem $FlyersRoot -Directory -EA SilentlyContinue | ForEach-Object {
  $store = $_.Name
  $mmFolders=@()
  Get-ChildItem $_.FullName -Directory -EA SilentlyContinue |
    Where-Object {$_.Name -match '^\d{6}$'} | ForEach-Object {
      $dt = Parse-MmDdYy $_.Name
      if ($null -ne $dt) { $mmFolders += [PSCustomObject]@{ Dir=$_.FullName; Store=$store; Folder=$_.Name; Date=$dt } }
    }
  if (-not $mmFolders -or $mmFolders.Count -le $KeepNewest) { $skipCount++; return }

  $sorted = $mmFolders | Sort-Object Date -Descending
  $keep   = $sorted | Select-Object -First $KeepNewest
  $keepSet=@{}; $keep | ForEach-Object { $keepSet[$_.Folder]=1 }
  $toMove = $sorted | Where-Object { -not $keepSet.ContainsKey($_.Folder) }

  foreach ($item in $toMove) {
    $dest = Join-Path (Join-Path $ArchiveRoot 'flyers') (Join-Path $store $item.Folder)
    New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
    if ($DoIt) {
      Write-Ok ("MOVE  {0}\{1}  ->  {2}" -f $store,$item.Folder,$dest)
      Move-Item -Path $item.Dir -Destination $dest -Force
      $results.Add([PSCustomObject]@{Store=$store;Folder=$item.Folder;Date=$item.Date.ToString('yyyy-MM-dd');Action='MOVED';Destination=$dest})|Out-Null
      $moveCount++
    } else {
      Write-Note ("[DryRun] would move  {0}\{1}  ->  {2}" -f $store,$item.Folder,$dest)
      $results.Add([PSCustomObject]@{Store=$store;Folder=$item.Folder;Date=$item.Date.ToString('yyyy-MM-dd');Action='DRYRUN';Destination=$dest})|Out-Null
    }
  }
}

$results | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $CsvFile
Write-Info ("Summary CSV: {0}" -f $CsvFile)
Write-Title ("Done. Stores skipped: {0}   Items {1}: {2}" -f $skipCount, ($(if($DoIt){'moved'}else{'to move'})),$moveCount)
try { Stop-Transcript | Out-Null } catch {}
# ===== end =====
