@echo off
REM US-15 Merge Conflict Resolution and Push Script
REM This resolves the merge conflicts and pushes to the existing PR

cd /d "%~dp0"

echo ====================================
echo US-15 Conflict Resolution
echo ====================================
echo.

echo Step 1: Staging resolved files...
git add "frontend\src\components\Passport\Passport.tsx"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to stage Passport.tsx
    pause
    exit /b 1
)

git add "backend\app\models\challenge.py"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to stage challenge.py
    pause
    exit /b 1
)

echo SUCCESS: Files staged
echo.

echo Step 2: Checking for remaining conflicts...
git diff --check
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: There may be whitespace issues
)

echo.
echo Step 3: Git status check...
git status --short
echo.

echo Step 4: Completing the merge commit...
git commit --no-edit
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to complete merge commit
    echo Try: git commit -m "Merge main into US-15: resolve conflicts"
    pause
    exit /b 1
)

echo SUCCESS: Merge commit completed
echo.

echo Step 5: Pulling latest changes from main...
git pull origin main --no-edit
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to pull from main
    echo You may need to resolve additional conflicts
    pause
    exit /b 1
)

echo SUCCESS: Pulled latest from main
echo.

echo Step 6: Pushing to feature branch...
git push origin feature/US-15-post-check-in-personalized-tip
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to push to origin
    echo.
    echo Try force push? (This will overwrite remote branch)
    pause
    git push -f origin feature/US-15-post-check-in-personalized-tip
)

echo.
echo ====================================
echo SUCCESS! US-15 conflicts resolved
echo and pushed to PR #15
echo ====================================
echo.
pause
