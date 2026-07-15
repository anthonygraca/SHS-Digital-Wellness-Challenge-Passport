@echo off
echo ========================================
echo Safe Backend Startup (No Data Loss)
echo ========================================
echo.

echo Step 1: Running safe database migration...
python migrate_database.py

echo.
echo ========================================
echo.

echo Step 2: Starting backend server...
echo.
echo Backend will start on: http://localhost:8000
echo API docs available at: http://localhost:8000/docs
echo Press Ctrl+C to stop
echo.

cd backend
python -m uvicorn app.main:app --reload --port 8000
