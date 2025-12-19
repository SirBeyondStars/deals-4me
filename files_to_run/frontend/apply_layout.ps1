<#
  apply_layout.ps1
  Injects shared header, footer, and site-init.js into every page under /site.
  Skips partials and creates .bak backups before changes.
#>

[CmdletBinding()]
param(
  [string]$SiteRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'site')
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'console_theme.ps1')

Write-Title "Applying shared layout to HTML pages…"

# Shared fragments
$header = Get-Content (Join-Path $SiteRoot 'components\header.html') -Raw
$footer = Get-Content (Join-Path $SiteRoot 'components\footer.html') -Raw

$files = Get-ChildItem $SiteRoot -Recurse -Filter *.html | Where-Object {
  $_.FullName -notmatch '\\partials\\' -and $_.Name -notmatch '\.bak$'
}

foreach ($f in $files) {
  $html = Get-Content -Raw $f.FullName

  # Backup
  Copy-Item $f.FullName "$($f.FullName).bak" -Force

  # Replace existing header/footer if found, else insert
  if ($html -match '<header[\s\S]*?</header>') {
    $html = [regex]::Replace($html, '<header[\s\S]*?</header>', $header, 'Singleline')
  } else {
    $html = $html -replace '(?i)(<body[^>]*>)', "`$1`n$header"
  }

  if ($html -match '<footer[\s\S]*?</footer>') {
    $html = [regex]::Replace($html, '<footer[\s\S]*?</footer>', $footer, 'Singleline')
  } else {
    $html = $html -replace '(?i)(</body>)', "$footer`n$1"
  }

  # Ensure theme + site-init.js linked
  if ($html -notmatch 'theme\.css') {
    $html = $html -replace '(?i)(</head>)', "<link rel='stylesheet' href='./styles/theme.css'>`n<link rel='stylesheet' href='./styles/toolbarTheme.css'>`n$1"
  }
  if ($html -notmatch 'site-init\.js') {
    $html = $html -replace '(?i)(</body>)', "<script src='./scripts/site-init.js'></script>`n$1"
  }

  Set-Content -Path $f.FullName -Value $html -Encoding UTF8
  Write-Ok ("Updated layout → {0}" -f $f.Name)
}

Write-Note "All pages processed. Backups (.bak) created beside originals."
