# ===================== Deals-4Me Front-End Manager (safe bootstrap) =====================

[CmdletBinding()]
param(
  [string]$SiteRoot   # optional; auto-resolved if not provided
)

$ErrorActionPreference = 'Stop'

# --- Resolve paths robustly (simple, no special characters) ---
$ScriptPath = $MyInvocation.MyCommand.Path
if ($ScriptPath) {
  $ScriptRoot = Split-Path -Parent $ScriptPath
} else {
  $ScriptRoot = (Get-Location).Path
}
$ProjectRoot = Split-Path -Parent $ScriptRoot

if (-not $SiteRoot -or -not (Test-Path $SiteRoot)) {
  $SiteRoot = Join-Path $ProjectRoot 'site'
}

# --- Load console theme if present, else define fallbacks ---
$ThemePath = Join-Path $ScriptRoot 'console_theme.ps1'
if (Test-Path $ThemePath) {
  try { . $ThemePath } catch {}
}
if (-not (Get-Command Write-Ok    -ErrorAction SilentlyContinue)) { function Write-Ok   ($m){Write-Host $m -ForegroundColor Green} }
if (-not (Get-Command Write-Info  -ErrorAction SilentlyContinue)) { function Write-Info ($m){Write-Host $m -ForegroundColor Cyan} }
if (-not (Get-Command Write-Note  -ErrorAction SilentlyContinue)) { function Write-Note ($m){Write-Host $m -ForegroundColor DarkGray} }
if (-not (Get-Command Write-Warn  -ErrorAction SilentlyContinue)) { function Write-Warn ($m){Write-Host $m -ForegroundColor Yellow} }
if (-not (Get-Command Write-Err   -ErrorAction SilentlyContinue)) { function Write-Err  ($m){Write-Host $m -ForegroundColor Red} }
if (-not (Get-Command Write-Title -ErrorAction SilentlyContinue)) { function Write-Title($m){Write-Host $m -ForegroundColor Cyan} }

# ===================== Helpers =====================
function Show-Header {
  Clear-Host
  Write-Title "Deals-4Me Front-End Manager"
  Write-Info  ("Project: {0}" -f $ProjectRoot)
  Write-Info  ("Site:    {0}" -f $SiteRoot)
  if (-not (Test-Path $SiteRoot)) { Write-Err "Site root not found." }
}

function HTML-Files {
  if (-not (Test-Path $SiteRoot)) { return @() }
  Get-ChildItem $SiteRoot -Recurse -Filter *.html | Where-Object {
    $_.FullName -notmatch '\\(components|partials)\\' -and $_.Name -notmatch '\.bak$'
  }
}

function Backup-File($path) { try { Copy-Item $path "$path.bak" -Force } catch {} }

function Ensure-HeadPieces([string]$html,[string[]]$lines) {
  $out = $html
  foreach ($line in $lines) {
    $t = $line.Trim()
    if ($t -and $out -notmatch [regex]::Escape($t)) {
      $out = [regex]::Replace($out,'(?is)</head>',"$t`r`n</head>")
    }
  }
  return $out
}

# Defaults
$HeaderPathDefault = Join-Path $SiteRoot 'components\header.html'
$FooterPathDefault = Join-Path $SiteRoot 'components\footer.html'
$SnippetDir        = Join-Path $SiteRoot 'snippets'
New-Item -ItemType Directory -Force -Path $SnippetDir | Out-Null

# ===================== Actions =====================
function Apply-Layout {
  Write-Title "Apply shared layout"
  $headerPath = if (Test-Path $HeaderPathDefault) { $HeaderPathDefault } else { Read-Host "Path to header.html" }
  $footerPath = if (Test-Path $FooterPathDefault) { $FooterPathDefault } else { Read-Host "Path to footer.html" }
  if (-not (Test-Path $headerPath)) { Write-Err "Missing header: $headerPath"; return }
  if (-not (Test-Path $footerPath)) { Write-Err "Missing footer: $footerPath"; return }

  $header = Get-Content -Raw $headerPath
  $footer = Get-Content -Raw $footerPath

  $stdHead = @(
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<link rel="stylesheet" href="/site/styles/theme.css">',
    '<link rel="stylesheet" href="/site/styles/toolbarTheme.css">'
  )

  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    $orig = $html
    Backup-File $f.FullName

    if ($html -match '<header[\s\S]*?</header>') {
      $html = [regex]::Replace($html,'<header[\s\S]*?</header>',$header,'Singleline')
    } elseif ($html -match '(?is)<body[^>]*>') {
      $html = [regex]::Replace($html,'(?is)(<body[^>]*>)',"$1`r`n$header",1)
    }

    if ($html -match '<footer[\s\S]*?</footer>') {
      $html = [regex]::Replace($html,'<footer[\s\S]*?</footer>',$footer,'Singleline')
    } else {
      $html = [regex]::Replace($html,'(?is)</body>',"$footer`r`n</body>")
    }

    if ($html -notmatch '(?is)<head[^>]*>') {
      $html = [regex]::Replace($html,'(?is)<html[^>]*>','$0' + "`r`n<head>`r`n" + ($stdHead -join "`r`n") + "`r`n</head>`r`n",1)
    } else {
      $html = Ensure-HeadPieces $html $stdHead
    }

    if ($html -notmatch 'site-init\.js') {
      $html = [regex]::Replace($html,'(?is)</body>','<script src="/site/scripts/site-init.js"></script>' + "`r`n</body>",1)
    }

    if ($html -ne $orig) {
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("Updated -> {0}" -f $f.Name)
    } else {
      Write-Note ("No change -> {0}" -f $f.Name)
    }
  }
  Write-Ok "Layout applied."
}

function Apply-Favicon {
  Write-Title "Apply favicon/meta bundle"
  $pieces = @(
    '<link rel="icon" type="image/x-icon" href="/site/favicon.ico">',
    '<link rel="icon" type="image/png" sizes="32x32" href="/site/favicon-32x32.png">',
    '<link rel="icon" type="image/png" sizes="192x192" href="/site/favicon-192x192.png">',
    '<link rel="apple-touch-icon" href="/site/apple-touch-icon.png">',
    '<meta name="theme-color" content="#009688">'
  )
  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    if ($html -notmatch '(?is)<head[^>]*>') { Write-Warn ("No <head> in {0}" -f $f.Name); continue }
    $orig = $html
    $html = Ensure-HeadPieces $html $pieces
    if ($html -ne $orig) {
      Backup-File $f.FullName
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("Favicons/meta -> {0}" -f $f.Name)
    } else {
      Write-Note ("Already OK -> {0}" -f $f.Name)
    }
  }
  Write-Ok "Favicon/meta applied."
}

function Replace-Header {
  Write-Title "Replace HEADER from snippet"
  Write-Info  ("Put snippet .html in: {0}" -f $SnippetDir)
  $snippet = Read-Host "Snippet path (blank = list)"
  if (-not $snippet) {
    $cands = Get-ChildItem $SnippetDir -Filter *.html -ErrorAction SilentlyContinue
    if (-not $cands) { Write-Err "No snippets found in $SnippetDir"; return }
    $i=0; $cands | ForEach-Object { Write-Host ("[{0}] {1}" -f $i,$_.Name); $i++ }
    $pick = Read-Host "Choose index"
    if ($pick -notmatch '^\d+$' -or [int]$pick -ge $cands.Count) { Write-Err "Invalid selection"; return }
    $snippet = $cands[[int]$pick].FullName
  }
  if (-not (Test-Path $snippet)) { Write-Err "Not found: $snippet"; return }
  $block = Get-Content -Raw $snippet

  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    if ($html -match '<header[\s\S]*?</header>') {
      Backup-File $f.FullName
      $html = [regex]::Replace($html,'<header[\s\S]*?</header>',$block,'Singleline')
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("HEADER -> {0}" -f $f.Name)
    } else { Write-Warn ("No <header> in {0}" -f $f.Name) }
  }
}

function Replace-Footer {
  Write-Title "Replace FOOTER from snippet"
  Write-Info  ("Put snippet .html in: {0}" -f $SnippetDir)
  $snippet = Read-Host "Snippet path (blank = list)"
  if (-not $snippet) {
    $cands = Get-ChildItem $SnippetDir -Filter *.html -ErrorAction SilentlyContinue
    if (-not $cands) { Write-Err "No snippets found in $SnippetDir"; return }
    $i=0; $cands | ForEach-Object { Write-Host ("[{0}] {1}" -f $i,$_.Name); $i++ }
    $pick = Read-Host "Choose index"
    if ($pick -notmatch '^\d+$' -or [int]$pick -ge $cands.Count) { Write-Err "Invalid selection"; return }
    $snippet = $cands[[int]$pick].FullName
  }
  if (-not (Test-Path $snippet)) { Write-Err "Not found: $snippet"; return }
  $block = Get-Content -Raw $snippet

  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    if ($html -match '<footer[\s\S]*?</footer>') {
      Backup-File $f.FullName
      $html = [regex]::Replace($html,'<footer[\s\S]*?</footer>',$block,'Singleline')
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("FOOTER -> {0}" -f $f.Name)
    } else { Write-Warn ("No <footer> in {0}" -f $f.Name) }
  }
}

function Inject-Breadcrumb {
  Write-Title "Inject breadcrumb + H1"
  $block = @'
<div class="section" id="page-head">
  <nav class="crumbs"><a href="/site/index.html">Home</a> › <span id="crumb-here"></span></nav>
  <h1 id="page-title"></h1>
</div>
'@
  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    if ($html -match 'id="page-head"') { Write-Note ("Skip -> {0}" -f $f.Name); continue }
    if ($html -match '</header>') {
      Backup-File $f.FullName
      $html = $html -replace '</header>', "</header>`r`n$block"
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("Breadcrumb -> {0}" -f $f.Name)
    } else { Write-Warn ("No </header> in {0}" -f $f.Name) }
  }
}

function Set-Titles {
  Write-Title "Set page titles from titles.json"
  $mapPath = Join-Path $SnippetDir 'titles.json'
  if (-not (Test-Path $mapPath)) {
    @'
{
  "index.html":   "Deals-4Me – Home",
  "flyers.html":  "Deals-4Me – Weekly Flyers",
  "pricing.html": "Deals-4Me – Pricing",
  "gamesHub.html":"Deals-4Me – Games Hub",
  "account.html": "Deals-4Me – Account",
  "privacy.html": "Deals-4Me – Privacy",
  "tos.html":     "Deals-4Me – Terms"
}
'@ | Set-Content -Path $mapPath -Encoding UTF8
    Write-Note ("Seeded: {0}" -f $mapPath)
  }
  $map = Get-Content -Raw $mapPath | ConvertFrom-Json
  foreach ($f in (HTML-Files)) {
    $name = $f.Name
    $title = $map.$name
    if (-not $title) { continue }
    $html = Get-Content -Raw $f.FullName
    Backup-File $f.FullName
    if ($html -match '(?is)<title>.*?</title>') {
      $html = [regex]::Replace($html,'(?is)<title>.*?</title>',"<title>$title</title>")
    } elseif ($html -match '(?is)<head[^>]*>') {
      $html = $html -replace '(<head[^>]*>)',"`$1`r`n<title>$title</title>"
    } else {
      $html = $html -replace '(<html[^>]*>)',"`$1`r`n<head><title>$title</title></head>"
    }
    Set-Content -Path $f.FullName -Value $html -Encoding UTF8
    Write-Ok ("Title set -> {0}" -f $name)
  }
}

function Check-Links {
  Write-Title "Checking internal links"
  $missing = 0
  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    $matches = [regex]::Matches($html,'href="([^"#?]+?\.html)"')
    foreach ($m in $matches) {
      $href = $m.Groups[1].Value
      if ($href -match '^https?://') { continue }
      $target = Join-Path $SiteRoot ($href -replace '^/site/','')
      if (-not (Test-Path $target)) { $missing++; Write-Warn ("{0} -> missing: {1}" -f $f.Name,$href) }
    }
  }
  if ($missing -eq 0) { Write-Ok "All internal links resolved." } else { Write-Err ("Missing: {0}" -f $missing) }
}

function Restore-Backups {
  Write-Title "Restore from .bak"
  $choice = Read-Host "Type filename (e.g., pricing.html) or 'ALL'"

  if ($choice.ToUpper() -eq 'ALL') {
    Get-ChildItem $SiteRoot -Recurse -Filter *.bak | ForEach-Object {
      $orig = $_.FullName -replace '\.bak$',''
      Copy-Item $_.FullName $orig -Force
      Write-Ok ("Restored {0}" -f (Split-Path $orig -Leaf))
    }
  }
  else {
    $matches = Get-ChildItem $SiteRoot -Recurse -Filter "$choice.bak"
    if (-not $matches) { Write-Warn "No .bak for $choice"; return }

    foreach ($b in $matches) {
      $orig = $b.FullName -replace '\.bak$',''
      Copy-Item $b.FullName $orig -Force
      Write-Ok ("Restored {0}" -f (Split-Path $orig -Leaf))
    }
  }
}

# [10] Global find/replace (literal OR regex) across all HTML pages
function GlobalReplace {
  Write-Title "Global Find/Replace"
  Write-Info  "Works on every .html under /site (backs up .bak first)."

  $mode = Read-Host "Mode: LITERAL or REGEX (default LITERAL)"
  if ([string]::IsNullOrWhiteSpace($mode)) { $mode = "LITERAL" }
  $mode = $mode.ToUpper()

  $find = Read-Host 'Find pattern (e.g., href="/site/styles/toolbarTheme.css")'
  if ([string]::IsNullOrWhiteSpace($find)) { Write-Err "Find pattern required."; return }
  $repl = Read-Host 'Replace with (e.g., href="/site/styles/theme_toolbar_v2.css")'

  $scope = Read-Host "Scope: HEAD, BODY, or ALL (default ALL)"
  if ([string]::IsNullOrWhiteSpace($scope)) { $scope = "ALL" }
  $scope = $scope.ToUpper()

  $changed = 0
  $scanned = 0

  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    $orig = $html
    $scanned++

    # Limit to head/body if requested
    if ($scope -eq 'HEAD') {
      if ($html -match '(?is)(<head[^>]*>)(.*?)(</head>)') {
        $pre  = $matches[1]
        $mid  = $matches[2]
        $post = $matches[3]
        $mid2 = if ($mode -eq 'REGEX') { [regex]::Replace($mid, $find, $repl) } else { $mid.Replace($find, $repl) }
        $html = $html -replace '(?is)<head[^>]*>.*?</head>', ($pre + $mid2 + $post)
      }
    }
    elseif ($scope -eq 'BODY') {
      if ($html -match '(?is)(<body[^>]*>)(.*?)(</body>)') {
        $pre  = $matches[1]
        $mid  = $matches[2]
        $post = $matches[3]
        $mid2 = if ($mode -eq 'REGEX') { [regex]::Replace($mid, $find, $repl) } else { $mid.Replace($find, $repl) }
        $html = $html -replace '(?is)<body[^>]*>.*?</body>', ($pre + $mid2 + $post)
      }
    }
    else {
      $html = if ($mode -eq 'REGEX') { [regex]::Replace($html, $find, $repl) } else { $html.Replace($find, $repl) }
    }

    if ($html -ne $orig) {
      Backup-File $f.FullName
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("Updated → {0}" -f $f.Name)
      $changed++
    }
    else {
      Write-Note ("No change → {0}" -f $f.Name)
    }
  }

  Write-Info ("Scanned: {0}  Changed: {1}" -f $scanned, $changed)
  if ($changed -gt 0) { Write-Ok "Global replace complete." } else { Write-Warn "Nothing matched." }
}

# [11] Insert or swap a block from snippet (by anchor)
function ReplaceOrInsertFromSnippet {
  Write-Title "Replace/Insert from snippet"
  Write-Info  ("Put .html/.css/.js snippets in: {0}" -f $SnippetDir)

  $snippet = Read-Host "Snippet path (blank = list)"
  if (-not $snippet) {
    $cands = Get-ChildItem $SnippetDir -File -ErrorAction SilentlyContinue |
             Where-Object { $_.Extension -in '.html','.css','.js','.txt' }

    if (-not $cands) { Write-Err "No snippets found in $SnippetDir"; return }

    $i = 0
    $cands | ForEach-Object { Write-Host ("[{0}] {1}" -f $i, $_.Name); $i++ }

    $pick = Read-Host "Choose index"
    if ($pick -notmatch '^\d+$' -or [int]$pick -ge $cands.Count) { Write-Err "Invalid selection"; return }

    $snippet = $cands[[int]$pick].FullName
  }

  if (-not (Test-Path $snippet)) { Write-Err "Snippet not found: $snippet"; return }
  $block = Get-Content -Raw $snippet

  $anchor = Read-Host "Anchor text/regex to replace (e.g., toolbarTheme.css). Leave blank to INSERT only"
  $mode   = Read-Host "Action: REPLACE or INSERT (default REPLACE)"
  if ([string]::IsNullOrWhiteSpace($mode)) { $mode = "REPLACE" }
  $mode = $mode.ToUpper()

  $where = Read-Host "INSERT target: HEAD or BODY (default HEAD)"
  if ([string]::IsNullOrWhiteSpace($where)) { $where = "HEAD" }
  $where = $where.ToUpper()

  $useRegex = Read-Host "Treat anchor as REGEX? (Y/N, default N)"
  $useRegex = ($useRegex -match '^[Yy]')

  $changed = 0

  foreach ($f in (HTML-Files)) {
    $html = Get-Content -Raw $f.FullName
    $orig = $html

    $didReplace = $false

    if ($anchor) {
      if ($useRegex) {
        if ($html -match $anchor) {
          $html = [regex]::Replace(
            $html,
            $anchor,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block }
          )
          $didReplace = $true
        }
      }
      else {
        if ($html.Contains($anchor)) {
          $html = $html.Replace($anchor, $block)
          $didReplace = $true
        }
      }
    }

    if (-not $didReplace -and $mode -eq 'INSERT') {
      if ($where -eq 'BODY') {
        if ($html -match '(?is)</body>') { $html = $html -replace '(?is)</body>', "$block`r`n</body>" }
        else { $html += "`r`n$block" }
      }
      else {
        if ($html -match '(?is)</head>') { $html = $html -replace '(?is)</head>', "$block`r`n</head>" }
        else { $html = "<head>`r`n$block`r`n</head>`r`n$html" }
      }
    }

    if ($html -ne $orig) {
      Backup-File $f.FullName
      Set-Content -Path $f.FullName -Value $html -Encoding UTF8
      Write-Ok ("Updated → {0}" -f $f.Name)
      $changed++
    }
    else {
      Write-Note ("No change → {0}" -f $f.Name)
    }
  }

  Write-Ok ("Done. Files changed: {0}" -f $changed)
}

# NEW: [12] Clean href/src path prefixes in /site
function Clean-PathPrefixes {
  Write-Title "Clean href/src path prefixes in /site"
  Write-Info  "Running frontend_fix_paths_only.js via Node..."

  Push-Location $ProjectRoot
  try {
    node ".\files_to_run\frontend\frontend_fix_paths_only.js"
  }
  finally {
    Pop-Location
  }

  Write-Ok "Done cleaning path prefixes."
}

function Preview {
  Write-Title "Open local preview"
  $index = Join-Path $SiteRoot 'index.html'
  if (Test-Path $index) {
    Start-Process $index | Out-Null
    Write-Ok "Opened index.html"
  }
  else {
    Write-Warn "site/index.html not found."
  }
}

# ===================== Menu =====================
do {
  try {
    Show-Header
    Write-Host "[1]  Apply shared layout (header/footer + theme + site-init)" -ForegroundColor White
    Write-Host "[2]  Insert favicon & meta bundle (teal theme-color)" -ForegroundColor White
    Write-Host "[3]  Replace HEADER from snippet (snippets/*.html)" -ForegroundColor White
    Write-Host "[4]  Replace FOOTER from snippet (snippets/*.html)" -ForegroundColor White
    Write-Host "[5]  Inject breadcrumb + H1 under header" -ForegroundColor White
    Write-Host "[6]  Set page titles from snippets/titles.json" -ForegroundColor White
    Write-Host "[7]  Check internal .html links" -ForegroundColor White
    Write-Host "[8]  Restore from .bak backups" -ForegroundColor White
    Write-Host "[9]  Open local preview (index.html)" -ForegroundColor White
    Write-Host "[10] Global find/replace (literal or regex)" -ForegroundColor White
    Write-Host "[11] Insert or swap a block from snippet" -ForegroundColor White
    Write-Host "[12] Clean href/src path prefixes in /site (frontend_fix_paths_only.js)" -ForegroundColor White

    Write-Host "[0]  Exit" -ForegroundColor Yellow

    $choice = Read-Host "`nSelect option"
    switch ($choice) {
      '1'  { Apply-Layout }
      '2'  { Apply-Favicon }
      '3'  { Replace-Header }
      '4'  { Replace-Footer }
      '5'  { Inject-Breadcrumb }
      '6'  { Set-Titles }
      '7'  { Check-Links }
      '8'  { Restore-Backups }
      '9'  { Preview }
      '10' { GlobalReplace }
      '11' { ReplaceOrInsertFromSnippet }
      '12' { Clean-PathPrefixes }
      '0'  { Write-Note "Exiting..." }
      default { Write-Warn "Invalid option."; Start-Sleep -Milliseconds 600 }
    }

    if ($choice -ne '0') {
      Write-Note "`nDone. Press Enter..."
      [void][Console]::ReadLine()
    }
  }
  catch {
    Write-Err "`n--- FRONT-END TOOL ERROR ---"
    Write-Err $_.Exception.Message
    if ($_.InvocationInfo.PositionMessage) { Write-Note "`n$($_.InvocationInfo.PositionMessage)" }
    Write-Note "`nPress Enter to continue..."
    [void][Console]::ReadLine()
  }
} while ($choice -ne '0')

# Pause if launched by double-click
if (-not $env:WT_SESSION -and -not $env:TERM_PROGRAM) {
  Read-Host "`nPress Enter to close"
}
# ===================== end =====================
