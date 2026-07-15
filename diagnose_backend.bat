@echo off
echo ========================================
echo Backend Startup Diagnostic
echo ========================================
echo.

echo [1/5] Checking Python version...
python --version

echo.
echo [2/5] Checking if in correct directory...
cd

echo.
echo [3/5] Checking if dependencies installed...
cd backend
python -c "import fastapi; print('✓ FastAPI installed')" 2>NUL || echo "✗ FastAPI NOT installed"
python -c "import uvicorn; print('✓ Uvicorn installed')" 2>NUL || echo "✗ Uvicorn NOT installed"
python -c "import sqlalchemy; print('✓ SQLAlchemy installed')" 2>NUL || echo "✗ SQLAlchemy NOT installed"
python -c "import boto3; print('✓ boto3 installed (optional)')" 2>NUL || echo "! boto3 not installed (will use fallback tips)"

echo.
echo [4/5] Checking if app can import...
python -c "from app.main import app; print('✓ App imports successfully')" 2>&1

echo.
echo [5/5] Trying to start the app...
echo Press Ctrl+C to stop after checking startup
echo.

python -m uvicorn app.main:app --reload --port 8000

cd ..
