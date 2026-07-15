@echo off
echo ========================================
echo COMPLETE FIX - Commit Everything and Start
echo ========================================
echo.

echo Step 1: Checking git status...
git status --short

echo.
echo Step 2: Adding ALL changes...
git add -A

echo.
echo Step 3: Committing with issue reference...
git commit -m "Complete US-15: fix route conflict, tests, database migration, and all merge issues (#15)"

echo.
echo Step 4: Pushing to PR...
git push origin feature/US-15-post-check-in-personalized-tip

echo.
echo Step 5: Running database migration...
python migrate_database.py

echo.
echo Step 6: Starting backend...
echo.
echo ========================================
echo Backend starting on http://localhost:8000
echo Press Ctrl+C to stop
echo ========================================
echo.

cd backend
python -m uvicorn app.main:app --reload --port 8000
