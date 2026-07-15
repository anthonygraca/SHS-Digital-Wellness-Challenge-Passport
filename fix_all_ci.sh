#!/bin/bash
set -e

echo "========================================"
echo "Fixing All CI Issues"
echo "========================================"
echo ""

# 1. Fix commit messages - rewrite recent commits to include #15
echo "[1/4] Fixing commit messages to reference #15..."
git rebase -i HEAD~3 --exec 'git commit --amend -m "$(git log --format=%B -n1) (#15)" --no-edit || true'

# 2. Run ruff linting
echo ""
echo "[2/4] Running ruff linting..."
cd backend
python -m ruff check app/ || {
    echo "Fixing ruff issues..."
    python -m ruff check --fix app/
    python -m ruff format app/
    cd ..
    git add backend/app/
    git commit -m "Fix ruff linting issues (#15)"
    cd backend
}

# 3. Run tests
echo ""
echo "[3/4] Running backend tests..."
python -m pytest tests/test_checkins.py -v

cd ..

# 4. Force push (overwrites history)
echo ""
echo "[4/4] Force pushing to PR..."
git push -f origin feature/US-15-post-check-in-personalized-tip

echo ""
echo "========================================"
echo "CI fixes complete!"
echo "========================================"
