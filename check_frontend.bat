@echo off
echo Checking frontend for errors...
cd frontend

echo.
echo [1/3] TypeScript compilation check...
call npx tsc --noEmit

echo.
echo [2/3] Checking for import errors...
call npx tsc --noEmit --listFilesOnly 2>&1 | findstr "error"

echo.
echo [3/3] Starting dev server (Ctrl+C to stop)...
npm run dev

pause
