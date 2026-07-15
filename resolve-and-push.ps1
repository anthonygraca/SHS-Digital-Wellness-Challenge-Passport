$ErrorActionPreference = "Continue"

# Stage the resolved files
Write-Host "Staging resolved files..."
git add backend/app/models/challenge.py
git add frontend/src/components/Passport/Passport.tsx

# Continue the rebase
Write-Host "Continuing rebase..."
git rebase --continue

# Push to the PR
Write-Host "Force pushing to PR..."
git push -f origin feature/US-15-post-check-in-personalized-tip

Write-Host "Done!"
