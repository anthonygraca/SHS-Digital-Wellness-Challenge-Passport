@echo off
echo ========================================
echo Git Status Check
echo ========================================
echo.

echo Current branch:
git branch --show-current

echo.
echo Git status:
git status --short

echo.
echo Uncommitted files:
git diff --name-only

echo.
echo Staged files:
git diff --cached --name-only

echo.
echo ========================================
echo.

git status

pause
