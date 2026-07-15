@echo off
echo ========================================
echo Testing Black Screen Fix
echo ========================================
echo.

echo [1/2] Running backend tests...
cd backend
python -m pytest tests/test_checkins.py::test_checkin_returns_personalized_tip -v
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: Backend tests not passing
    pause
    exit /b 1
)

echo.
echo [2/2] Checking frontend TypeScript...
cd ../frontend
call npx tsc --noEmit
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: TypeScript errors found
)

echo.
echo ========================================
echo Tests Complete!
echo ========================================
echo.
echo Now run: make dev
echo Then visit: http://localhost:5173
echo.
pause
