param(
  [string]$Root = "C:\Users\jwein\OneDrive\Desktop\deals-4me\flyers",
  [int]$KeepWeeks = 2      # keep snips for this many full weeks
)

$ErrorActionPreference = 'Stop'
$now = Get-Date
$cutoff = $now.AddDays(-7*$KeepWeeks)

$skip = @('_inbox','logs','raw_images','raw_pdfs','run','notes','_week_template','_templates','_archive')
$stores = Get-ChildItem $Root -Directory | Where-Object { $skip -notcontains $_.Name }

foreach ($s in $stores) {
  Get-ChildItem $s.FullName -Directory | Where-Object { $_.Name -match '^\d{6}$' } | ForEach-Object {
    $week = $_.Name
    $weekPath = $_.FullName
    $ingested = Test-Path (Join-Path $weekPath 'INGESTED.ok')

    # Only delete snips if the week is ingested and older than cutoff
    if ($ingested -and $_.LastWriteTime -lt $cutoff) {
      $snips = Join-Path $weekPath 'snips'
      if (Test-Path $snips) {
        Remove-Item -Path $snips -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $snips | Out-Null  # keep empty folder for structure
        Write-Host "Purged snips for $($s.Name)\$week"
      }
    }
  }
}
Write-Host "Snip cleanup complete. Kept OCR and other files."
