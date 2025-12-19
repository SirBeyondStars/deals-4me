# ================== prune_empty_folders.ps1 ==================
[CmdletBinding()]
param(
  # Default to flyers under the project root (one level above files_to_run)
  [string]$Root = (Join-Path (Split-Path -Parent $PSScriptRoot) 'flyers'),
  [switch]$DoIt  # omit = DRY-RUN; add -DoIt to actually delete
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Root)) { Write-Host "Root not found: $Root" -ForegroundColor Red; exit 1 }

# Folders to skip entirely
$skip = @('_inbox','logs','run','_week_template','_templates')

function Test-DirEmpty([string]$dir) {
  $items = Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue
  return -not $items
}

Write-Host "=== Prune Empty Folders ===" -ForegroundColor Cyan
Write-Host "Root: $Root" -ForegroundColor DarkCyan
Write-Host ($(if($DoIt){"Mode: LIVE delete"}else{"Mode: DRY-RUN (use -DoIt to apply)"})) -ForegroundColor Yellow
Write-Host ""

# Deepest-first so parents can become empty after children go
$dirs = Get-ChildItem -LiteralPath $Root -Directory -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending

[int]$count = 0
foreach ($d in $dirs) {
  if ($skip -contains $d.Name) { continue }
  if (Test-DirEmpty $d.FullName) {
    $count++
    if ($DoIt) {
      Write-Host ("🧹 Delete: {0}" -f $d.FullName) -ForegroundColor Yellow
      Remove-Item -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue
    } else {
      Write-Host ("DRY-RUN: would delete -> {0}" -f $d.FullName) -ForegroundColor Gray
    }
  }
}

Write-Host ""
Write-Host ("Done. {0} {1} empty folder(s)." -f $count, ($(if($DoIt){"deleted"}else{"found"}))) -ForegroundColor Cyan
# ================== end ======================================
