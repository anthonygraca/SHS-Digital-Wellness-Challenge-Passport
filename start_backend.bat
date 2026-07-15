@echo off
echo ========================================
echo Starting Backend Server
echo ========================================
echo.

cd backend

echo Checking if uvicorn is installed...
python -c "import uvicorn" 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo uvicorn not found. Installing dependencies...
    python -m pip install -e ".[dev]"
    echo.
)

echo.
echo Starting backend on http://localhost:8000
echo Press Ctrl+C to stop
echo.
echo API docs: http://localhost:8000/docs
echo Health check: http://localhost:8000/healthz
echo.

python -m uvicorn app.main:app --reload --port 8000
