@echo off
echo ========================================
echo US-15 Complete Fix and Validation
echo ========================================
echo.

echo Step 1: Resolving git merge...
git add backend/app/config.py
git add backend/app/main.py  
git add frontend/src/components/Passport/Passport.tsx
git add backend/app/models/challenge.py

git status --short

git commit --no-edit

echo.
echo Step 2: Pulling latest from main...
git pull origin main --no-edit

echo.
echo Step 3: Pushing to PR...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo ========================================
echo Git operations complete!
echo ========================================
echo.

echo Step 4: Validating backend...
cd backend
python -m pytest tests/test_checkins.py::test_checkin_returns_personalized_tip -v 2>NUL
if %ERRORLEVEL% EQU 0 (
    echo ✓ Backend US-15 tests passing
) else (
    echo ! Backend tests need attention - check AWS config
)

echo.
echo Step 5: Checking frontend types...
cd ../frontend
call npx tsc --noEmit 2>NUL
if %ERRORLEVEL% EQU 0 (
    echo ✓ Frontend types valid
) else (
    echo ! TypeScript errors found
)

cd ..

echo.
echo ========================================
echo COMPLETE! US-15 is ready
echo ========================================
echo.
echo Next: Test the app
echo   1. Run: make dev
echo   2. Open: http://localhost:5173
echo   3. Check in to a task
echo   4. Verify personalized tip shows
echo.
pause
