param(
  [string]$Message = "Update"
)

Write-Host "[GIT] Checking status..." -ForegroundColor Cyan
git status

Write-Host ""
Write-Host "[GIT] Staging all changes..." -ForegroundColor Cyan
git add .

Write-Host "[GIT] Committing..." -ForegroundColor Cyan
git commit -m $Message

Write-Host "[GIT] Pushing to origin..." -ForegroundColor Cyan
git push

Write-Host "[OK] Done." -ForegroundColor Green
