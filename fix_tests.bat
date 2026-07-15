@echo off
echo ========================================
echo Fixing TypeScript Test Errors
echo ========================================
echo.

echo Committing test fixes...
git add frontend/src/components/Passport/Passport.test.tsx
git add frontend/src/auth/SessionProvider.test.tsx
git add frontend/src/components/Landing/Landing.test.tsx
git add frontend/src/offline/snapshot.test.ts

git commit -m "Fix test files: add missing student_id and taskId fields"

echo.
echo Checking TypeScript...
cd frontend
call npx tsc --noEmit

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! All TypeScript errors fixed
    echo ========================================
    echo.
    echo Pushing to PR...
    cd ..
    git push origin feature/US-15-post-check-in-personalized-tip
    
    echo.
    echo Now run: make dev
) else (
    echo.
    echo Still have TypeScript errors - check output above
)

cd ..
pause
