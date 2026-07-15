@echo off
echo Checking Python syntax...
echo.

echo Checking ai_tips.py...
python -m py_compile backend/app/services/ai_tips.py
if %ERRORLEVEL% EQU 0 (
    echo ✓ ai_tips.py syntax OK
) else (
    echo ✗ ai_tips.py has syntax errors
)

echo.
echo Checking checkins.py...
python -m py_compile backend/app/routers/checkins.py
if %ERRORLEVEL% EQU 0 (
    echo ✓ checkins.py syntax OK
) else (
    echo ✗ checkins.py has syntax errors
)

echo.
echo Checking main.py...
python -m py_compile backend/app/main.py
if %ERRORLEVEL% EQU 0 (
    echo ✓ main.py syntax OK
) else (
    echo ✗ main.py has syntax errors
)

echo.
echo Trying to import app.main...
cd backend
python -c "from app.main import app; print('✓ App imports successfully!')"

pause
