#!/usr/bin/env pwsh
# Resolve merge conflicts for US-15

Write-Host "Staging resolved files..." -ForegroundColor Green
git add "frontend/src/components/Passport/Passport.tsx"
git add "backend/app/models/challenge.py"

Write-Host "`nChecking git status..." -ForegroundColor Green
git status

Write-Host "`nCompleting the merge..." -ForegroundColor Green
git commit --no-edit

Write-Host "`nPulling latest from main..." -ForegroundColor Green
git pull origin main

Write-Host "`nPushing to US-15 branch..." -ForegroundColor Green
git push origin feature/US-15-post-check-in-personalized-tip

Write-Host "`nDone! Conflicts resolved and pushed to PR." -ForegroundColor Green
