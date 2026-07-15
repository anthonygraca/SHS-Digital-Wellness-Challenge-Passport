# Fixing CI Failures

## Issues

### 1. Commit Messages Failing ❌
**Error:** `commit messages reference an issue (#N)`

**Cause:** Your commit messages don't reference issue #15

**Fix:** Add `(#15)` to commit messages

### 2. Backend Ruff + Pytest Failing ❌
**Error:** `backend (ruff + pytest)`

**Possible causes:**
- Ruff linting errors (code style)
- Pytest test failures
- Import errors

## Quick Fix

**Run this:**
```bash
./fix_ci_simple.bat
```

This will:
1. ✅ Run ruff to check and auto-fix linting issues
2. ✅ Run tests to verify they pass
3. ✅ Commit all fixes with proper issue reference `(#15)`
4. ✅ Push to PR

---

## Manual Fix

### Fix Linting Issues
```bash
cd backend
python -m ruff check app/ --fix
python -m ruff format app/
```

### Run Tests
```bash
cd backend
python -m pytest tests/test_checkins.py -v
```

### Commit with Issue Reference
```bash
git add -A
git commit -m "Fix US-15 implementation issues (#15)"
git push origin feature/US-15-post-check-in-personalized-tip
```

---

## Check Results

After pushing, check GitHub Actions:
- Go to your PR #15
- Click "Checks" tab
- Wait for CI to run
- Should see ✅ green checks

---

## Common Ruff Issues

### Import ordering
Ruff might complain about import order. It will auto-fix this.

### Line length
Lines over 90 characters need to be wrapped.

### Unused imports
Remove any imports that aren't being used.

---

## Common Test Failures

### Import errors
If tests fail with import errors, the app startup is also failing.

**Check:**
1. Is `app/services/ai_tips.py` valid Python?
2. Are all imports in `app/routers/checkins.py` correct?
3. Is boto3 installed? (optional, should fall back)

### Test assertion failures
If tests fail assertions, check:
1. API endpoint URLs are correct (`/api/checkins-v2/`)
2. Test data includes all required fields

---

## After Fixing

Once CI passes (all green ✅):
1. PR is ready for review
2. Can test locally with `make dev`
3. Backend should start without errors

---

## If Backend Still Won't Start

Check the actual error:
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Common errors:
- **Import error:** Missing file or wrong import path
- **Syntax error:** Check the file mentioned in error
- **Module not found:** Run `pip install -e ".[dev]"`
