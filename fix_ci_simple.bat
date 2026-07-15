@echo off
echo ========================================
echo Fixing CI Failures
echo ========================================
echo.

echo Step 1: Running ruff check and fix...
cd backend
python -m ruff check app/ --fix
python -m ruff format app/

echo.
echo Step 2: Running tests to see what fails...
python -m pytest tests/test_checkins.py -v --tb=short

cd ..

echo.
echo Step 3: Staging all fixes...
git add -A

echo.
echo Step 4: Committing with proper issue reference...
git commit -m "Fix US-15 route conflict, tests, and linting issues (#15)"

echo.
echo Step 5: Pushing to PR...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo ========================================
echo Done! Check CI on GitHub
echo ========================================
pause
