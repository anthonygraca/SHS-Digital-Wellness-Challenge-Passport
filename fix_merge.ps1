#!/usr/bin/env pwsh
# Disable confirmation prompts
$ConfirmPreference = 'None'
$ErrorActionPreference = 'Continue'

# Add the resolved files
Write-Host "Adding resolved files..."
git add backend/app/main.py backend/app/models/challenge.py frontend/src/components/Passport/Passport.tsx .github/pull_request_template.md

# Commit the merge
Write-Host "Committing merge..."
git commit -m "Merge branch with US-15 changes and updated PR template"

# Push to remote
Write-Host "Pushing to remote..."
git push

Write-Host "Done! Merge conflict resolved and pushed."
