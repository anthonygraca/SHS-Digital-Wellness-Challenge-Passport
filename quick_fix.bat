@echo off
cd /d "%~dp0"
git add frontend\src\components\Passport\Passport.tsx
git add backend\app\models\challenge.py
git commit --no-edit
git pull origin main --no-edit
git push origin feature/US-15-post-check-in-personalized-tip
pause
