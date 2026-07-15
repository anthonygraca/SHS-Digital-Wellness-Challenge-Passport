@echo off
echo Staging resolved files...
git add frontend\src\components\Passport\Passport.tsx
git add backend\app\models\challenge.py

echo.
echo Checking status...
git status --short

echo.
echo Completing merge...
git commit --no-edit

echo.
echo Pulling latest changes...
git pull origin main

echo.
echo Pushing to feature branch...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo Done!
pause
