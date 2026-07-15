@echo off
echo ========================================
echo Fixing Backend Bug
echo ========================================
echo.

echo Option 1: Update database schema
python fix_database.py

echo.
echo ========================================
echo.

echo Option 2 (if above failed): Delete databases and recreate
echo.
choice /C YN /M "Delete old databases and start fresh?"
if %ERRORLEVEL% EQU 1 (
    echo Deleting old databases...
    del /Q backend\*.db 2>NUL
    echo ✓ Databases deleted
    echo.
    echo The backend will create fresh databases on startup.
)

echo.
echo ========================================
echo Starting backend...
echo ========================================
echo.

cd backend
python -m uvicorn app.main:app --reload --port 8000
