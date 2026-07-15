@echo off
cls
echo ========================================
echo   US-15 Complete Fix ^& Start
echo ========================================
echo.
echo This will:
echo   1. Commit and push all fixes
echo   2. Test the backend
echo   3. Start the app
echo.
pause

echo.
echo [1/4] Committing fixes...
git add backend/app/routers/checkins.py
git add frontend/src/api/checkins.ts
git add backend/tests/test_checkins.py
git status --short

git commit -m "Fix route conflict: rename US-15 endpoint to /api/checkins-v2"

echo.
echo [2/4] Pushing to PR...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo [3/4] Quick backend test...
cd backend
python -m pytest tests/test_checkins.py::test_checkin_returns_personalized_tip -q
cd ..

echo.
echo [4/4] Starting the app...
echo.
echo ========================================
echo   App starting on http://localhost:5173
echo ========================================
echo.
echo Press Ctrl+C to stop
echo.

make dev
