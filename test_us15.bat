@echo off
echo ========================================
echo Testing US-15 Implementation
echo ========================================
echo.

cd backend

echo [1/4] Testing backend with pytest...
python -m pytest tests/test_checkins.py -v
if %ERRORLEVEL% NEQ 0 (
    echo FAILED: Backend tests failed
    pause
    exit /b 1
)

echo.
echo [2/4] Testing AI tips service...
python -m pytest tests/test_checkins.py::test_ai_tips_service_no_phi_in_prompt -v
python -m pytest tests/test_checkins.py::test_ai_tips_fallback_when_bedrock_unavailable -v

echo.
echo [3/4] Checking for missing dependencies...
python -c "import boto3; print('✓ boto3 installed')" 2>NUL || echo "✗ boto3 NOT installed - run: pip install boto3"

cd ..

echo.
echo [4/4] Checking frontend types...
cd frontend
npx tsc --noEmit 2>&1 | findstr /C:"error TS"
if %ERRORLEVEL% EQU 0 (
    echo WARNING: TypeScript errors found
) else (
    echo ✓ No TypeScript errors
)

cd ..

echo.
echo ========================================
echo US-15 Test Complete
echo ========================================
pause
