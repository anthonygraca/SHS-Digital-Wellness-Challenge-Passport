# Fix: Black Screen Issue

## Problem
The frontend showed a black screen because of a **route conflict** in the backend.

### Root Cause
Two routers defined overlapping endpoints:

1. **passport.py**: `POST /api/checkins` (legacy endpoint, takes `{ weekNo }`)
2. **checkins.py**: `POST /api/checkins/` (new US-15 endpoint, takes `{ task_id, method }`)

Since `passport.router` was registered BEFORE `checkins.router` in `main.py`, FastAPI matched the passport route first, causing the checkins router to never be reached.

This caused frontend requests to fail silently or return unexpected responses, resulting in the black screen.

## Solution
Changed the checkins router prefix to avoid conflict:

### Backend Changes
**File: `backend/app/routers/checkins.py`**
```python
# OLD:
router = APIRouter(prefix="/api/checkins", tags=["checkins"])

# NEW:
router = APIRouter(prefix="/api/checkins-v2", tags=["checkins"])
```

### Frontend Changes
**File: `frontend/src/api/checkins.ts`**
```typescript
// OLD:
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/checkins";

// NEW:
const BASE = (import.meta.env.VITE_API_BASE ?? "") + "/api/checkins-v2";
```

### Test Changes
**File: `backend/tests/test_checkins.py`**
- Updated all references from `/api/checkins/` to `/api/checkins-v2/`

## API Endpoints Now

### Legacy Endpoints (passport.py)
- `GET /api/passport` - Get student's passport
- `POST /api/checkins` - Manual check-in (takes `{ weekNo }`)
- `POST /api/checkins/scan` - QR code check-in (takes `{ token }`)
- `POST /api/content-views` - Record content view

### US-15 Endpoints (checkins.py)
- `POST /api/checkins-v2/` - Check-in with personalized tips (takes `{ task_id, method }`)
- `GET /api/checkins-v2/progress/{challenge_id}` - Get progress

## Testing

### 1. Start the app:
```bash
make dev
```

### 2. Test frontend loads:
- Visit http://localhost:5173
- Should see sign-in page (not black screen)

### 3. Test US-15 check-in:
```bash
# Backend tests
cd backend
python -m pytest tests/test_checkins.py -v
```

### 4. Manual test:
1. Sign in as a student
2. Enroll in a challenge
3. Check in to a task
4. Verify personalized tip shows

## Files Changed
- ✅ `backend/app/routers/checkins.py` - Changed prefix to `/api/checkins-v2`
- ✅ `frontend/src/api/checkins.ts` - Updated BASE URL
- ✅ `backend/tests/test_checkins.py` - Updated test URLs

## Note
The legacy `/api/checkins` endpoint in passport.py is still used by the existing Passport component for manual check-ins. The new `/api/checkins-v2` endpoint is for US-15 personalized tips.

If you want to fully integrate US-15, you would need to migrate the Passport component to use the new endpoint structure.
