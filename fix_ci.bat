@echo off
echo ========================================
echo Fixing CI Issues
echo ========================================
echo.

echo [1/3] Amending last commit to reference #15...
git commit --amend -m "Fix route conflict and test files for US-15 (#15)"

echo.
echo [2/3] Running ruff to check for linting issues...
cd backend
python -m ruff check app/
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Fixing ruff issues automatically...
    python -m ruff check --fix app/
    python -m ruff format app/
    
    echo.
    echo Committing ruff fixes...
    cd ..
    git add backend/app/
    git commit -m "Fix ruff linting issues (#15)"
    cd backend
)

echo.
echo [3/3] Running backend tests...
python -m pytest tests/test_checkins.py -v

cd ..

echo.
echo ========================================
echo Now force push to update PR
echo ========================================
echo.
echo git push -f origin feature/US-15-post-check-in-personalized-tip
echo.
pause
