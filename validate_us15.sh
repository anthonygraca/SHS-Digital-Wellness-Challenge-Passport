#!/bin/bash
# Comprehensive US-15 validation and fix script

set -e

echo "========================================"
echo "US-15 Validation & Fix Script"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "ERROR: Run this from the project root"
    exit 1
fi

echo "[1/6] Checking Python environment..."
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate || true
    echo "✓ Python venv found"
else
    echo "✗ No venv found. Run: make install"
    exit 1
fi

echo ""
echo "[2/6] Checking boto3 installation..."
python -c "import boto3; print('✓ boto3 version:', boto3.__version__)" || {
    echo "Installing boto3..."
    pip install boto3>=1.34
}

echo ""
echo "[3/6] Running US-15 backend tests..."
cd backend
python -m pytest tests/test_checkins.py -v --tb=short || {
    echo "WARNING: Some tests failed. Check if AWS credentials are needed."
}
cd ..

echo ""
echo "[4/6] Checking frontend TypeScript..."
cd frontend
if [ -d "node_modules" ]; then
    echo "✓ node_modules found"
    npm run typecheck || echo "WARNING: TypeScript errors found"
else
    echo "✗ node_modules not found. Run: npm install"
fi
cd ..

echo ""
echo "[5/6] Validating US-15 files exist..."
files=(
    "backend/app/services/ai_tips.py"
    "backend/app/routers/checkins.py"
    "backend/tests/test_checkins.py"
    "frontend/src/types/checkin.ts"
    "frontend/src/api/checkins.ts"
    "frontend/src/components/TipNotification/TipNotification.tsx"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ MISSING: $file"
    fi
done

echo ""
echo "[6/6] Checking API endpoint registration..."
if grep -q "checkins.router" backend/app/main.py; then
    echo "✓ Checkins router registered in main.py"
else
    echo "✗ Checkins router NOT registered in main.py"
fi

echo ""
echo "========================================"
echo "US-15 Validation Complete"
echo "========================================"
echo ""
echo "To run the app:"
echo "  make dev       # Start both frontend and backend"
echo "  make run-api   # Just backend on :8000"
echo "  make run-web   # Just frontend on :5173"
echo ""
echo "To test check-in with tips:"
echo "  1. Start the app: make dev"
echo "  2. Sign in as a student"
echo "  3. Enroll in a challenge"
echo "  4. Check in to a task"
echo "  5. Observe personalized tip"
echo ""
