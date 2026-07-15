# Debug Check-In Tip Modal Not Showing

## Quick Checks

### 1. Check Browser Console (F12)

Open DevTools and look for errors when you click "Check in":
- Any **red errors** in Console tab?
- Any **failed network requests** in Network tab?

### 2. Check Network Request

In Network tab:
1. Filter by "checkins"
2. Click "Check in" button
3. Look at the request details

**What you should see:**
```
POST /api/checkins
Status: 200 OK
Response: {
  "checkin_id": 1,
  "task_title": "...",
  "personalized_tip": { ... },
  "progress": { ... }
}
```

### 3. Verify Frontend Dev Server is Running

Make sure you have TWO terminals running:
- Terminal 1: `uvicorn app.main:app --reload --port 8000` (backend)
- Terminal 2: `npm run dev` (frontend)

The frontend should show:
```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

### 4. Hard Refresh Browser

Sometimes the browser caches old code:
1. Press **Ctrl + Shift + R** (hard refresh)
2. Or **Ctrl + F5**
3. Try check-in again

---

## Common Issues

### Issue 1: Import Error

**Check Console for:** `Cannot find module` or `Failed to fetch module`

**Fix:** Restart the frontend dev server:
```bash
# Stop frontend (Ctrl+C)
cd frontend
npm run dev
```

### Issue 2: API Error

**Check Console for:** `POST /api/checkins 400` or `500`

**Fix:** Check backend terminal for errors

### Issue 3: Wrong Endpoint

**Check Network tab:** Is it calling `/api/checkins` (old) or `/api/checkins/` (new)?

**Should be:** `POST http://localhost:8000/api/checkins/` (with trailing slash)

### Issue 4: Component Not Rendered

**Check in Console:**
```javascript
// Type this in Console tab:
document.querySelector('[role="dialog"]')
```

If it returns `null`, the modal isn't rendering.

---

## Manual Test in Console

Paste this in the browser Console to test the API directly:

```javascript
// Test check-in API
fetch('/api/checkins/', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ task_id: 1, method: 'manual' })
})
  .then(r => r.json())
  .then(data => {
    console.log('✅ Check-in success!', data);
    console.log('Tip:', data.personalized_tip.tip);
  })
  .catch(err => console.error('❌ Error:', err));
```

**Expected result:** Should log the tip data

---

## Check If Files Exist

Open these files in VS Code to verify they exist:

1. `frontend/src/api/checkins.ts` ✓
2. `frontend/src/types/checkin.ts` ✓
3. `frontend/src/components/TipModal/TipModal.tsx` ✓
4. `frontend/src/components/TipModal/TipModal.module.css` ✓

If any are missing, the files weren't created properly.

---

## Restart Everything

If nothing works, restart from scratch:

**Terminal 1 (Backend):**
```bash
cd backend
source .venv/Scripts/activate  # or source .venv/bin/activate on Mac/Linux
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
```

**Terminal 3 (Check API):**
```bash
curl http://localhost:8000/healthz
# Should return: {"status":"ok"}
```

---

## Report Back

Please share:
1. **Console errors** (screenshot or copy-paste)
2. **Network tab** - what does the `/api/checkins` request show?
3. **Are both servers running?** (backend on 8000, frontend on 5173)
4. **What happens when you click "Check in"?** (Nothing? Error? Task completes but no modal?)

This will help me identify the exact issue!
