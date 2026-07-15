@echo off
echo Adding all resolved files...
git add backend/app/config.py
git add backend/app/main.py
git add frontend/src/components/Passport/Passport.tsx
git add backend/app/models/challenge.py

echo.
echo Status after adding:
git status

echo.
echo Committing merge...
git commit --no-edit

echo.
echo Pulling latest from main...
git pull origin main --no-edit

echo.
echo Pushing to PR...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo Done!
pause
