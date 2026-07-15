@echo off
echo ========================================
echo Starting Frontend Server
echo ========================================
echo.

cd frontend

echo Checking if node_modules exists...
if not exist "node_modules" (
    echo.
    echo node_modules not found. Installing dependencies...
    npm install
    echo.
)

echo.
echo Starting frontend on http://localhost:5173
echo Press Ctrl+C to stop
echo.

npm run dev
