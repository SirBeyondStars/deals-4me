# fix_site_paths.ps1
# Purpose: In the /site folder, remove "/site/" from href/src/redirects
# so paths become relative (because /site is the web root).

$projectRoot = "C:\Users\jwein\OneDrive\Desktop\deals-4me"
$siteRoot    = Join-Path $projectRoot "site"

Write-Host "Fixing /site/ prefixes under: $siteRoot" -ForegroundColor Cyan

# Look only in .html, .js, .css files under /site, excluding /site/archive
Get-ChildItem -Path $siteRoot -Recurse -File -Include *.html,*.js,*.css |
    Where-Object { $_.FullName -notlike "*\archive\*" } |
    ForEach-Object {
        $filePath = $_.FullName
        $text = Get-Content -Path $filePath -Raw

        if ($text -match "/site/") {
            Write-Host "  Updating $filePath" -ForegroundColor Yellow
            $fixed = $text -replace "/site/", ""
            Set-Content -Path $filePath -Value $fixed -Encoding UTF8
        }
    }

Write-Host "Done fixing paths." -ForegroundColor Green
