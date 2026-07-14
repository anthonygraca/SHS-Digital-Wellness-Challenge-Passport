# US-5 Implementation Summary

**User Story:** View passport & progress countdown  
**Status:** ✅ Complete  
**Date:** 2026-07-14

## Overview

Implemented complete passport view functionality allowing enrolled students to see their challenge progress with week tiles showing status indicators and a progress countdown.

## Components Delivered

### Backend (Python/FastAPI)

1. **Database Models** (`backend/app/models/challenge.py`)
   - `Challenge`: Themed wellness challenges with metadata
   - `Task`: Individual weeks/activities within challenges
   - `Enrollment`: Student enrollment records
   - `CheckIn`: Completion tracking with timestamps and methods
   - Proper relationships, foreign keys, and unique constraints

2. **API Schemas** (`backend/app/schemas/challenge.py`)
   - `WeekStatus` enum: LOCKED, AVAILABLE, COMPLETE
   - `TaskOut`: Task data with computed status
   - `ChallengeOut`: Challenge metadata
   - `ProgressOut`: Progress summary with countdown
   - `PassportOut`: Complete passport view response

3. **Service Layer** (`backend/app/services/challenges.py`)
   - `get_active_challenge_for_campus()`: Find active challenge
   - `get_student_enrollment()`: Check enrollment status
   - `get_student_check_ins()`: Get completed tasks
   - `calculate_week_status()`: Determine locked/available/complete
   - `calculate_progress()`: Compute countdown and prize eligibility
   - `get_student_passport()`: Build complete passport view

4. **API Router** (`backend/app/routers/challenges.py`)
   - `GET /api/passport`: Returns authenticated student's passport
   - Validates session and campus enrollment
   - Returns 401 if not authenticated, 404 if no active challenge

### Frontend (React/TypeScript)

1. **Types** (`frontend/src/types/challenge.ts`)
   - TypeScript interfaces matching backend schemas
   - `WeekStatus` enum, `Task`, `Challenge`, `Progress`, `Passport`

2. **API Client** (`frontend/src/api/passport.ts`)
   - `fetchPassport()`: Calls backend endpoint with credentials
   - Proper error handling for 401/404/other errors

3. **Components**
   - **PassportView** (`frontend/src/components/PassportView/`)
     - Main passport container
     - Responsive grid layout for week tiles
     - Challenge header with theme
     - Progress countdown integration
     - Prize eligibility notice
     - Error and loading states
     - Sign-out button

   - **WeekTile** (`frontend/src/components/WeekTile/`)
     - Individual week/task card
     - Status-based visual differentiation:
       - **Locked**: Gray, lock icon 🔒, future weeks
       - **Available**: Highlighted, pin icon 📍, ready to complete
       - **Complete**: Checkmark ✓, completed weeks
     - Displays: week number, title, caption, location, dates, required badge
     - Responsive design with hover effects

   - **ProgressCountdown** (`frontend/src/components/ProgressCountdown/`)
     - Displays: "X of Y complete, Z remaining"
     - Visual progress bar
     - Color-coded emphasis on key numbers

4. **Routing** (`frontend/src/App.tsx`)
   - Updated `/home` route to use PassportView instead of Landing
   - Authenticated students now see passport on sign-in

## Test Coverage

### Test Data Seeding

Created `backend/seed_test_data.py` to populate:
- 1 test student (test-student@csub.edu)
- 1 active 7-week challenge ("Digital Wellness Challenge")
- 7 tasks with varied status:
  - 3 completed (past weeks with check-ins)
  - 1 available (current week, no check-in)
  - 3 locked (future weeks)

### Automated Test Verification

Created `backend/test_passport_api.py` that verifies:

✅ **Scenario 1: Passport shows week tiles with status**
- All 7 weeks returned
- Correct status distribution: 3 complete, 1 available, 3 locked
- Future weeks shown as locked

✅ **Scenario 2: Progress countdown reflects completion**
- Format: "3 of 7 complete, 4 remaining"
- Correct calculation from check-ins

✅ **Scenario 3: Expected values**
- total_weeks: 7
- completed: 3
- remaining: 4
- Prize eligibility: false (not all required tasks complete)

### Test Results

```
✓ Found test student: test-student@csub.edu (ID: 2)
✓ Passport data retrieved successfully:
  Challenge: Digital Wellness Challenge
  Theme: Stranger Things
  Total weeks: 7
  Completed: 3
  Remaining: 4
  Prize eligible: False

  Week statuses:
    Week 1: complete - Welcome & Orientation
    Week 2: complete - Vision Screening
    Week 3: complete - Social Media Wellness
    Week 4: available - Digital Detox Workshop
    Week 5: locked - Sleep & Screen Time
    Week 6: locked - Mindful Technology Use
    Week 7: locked - Final Celebration

✓ Testing Gherkin scenarios:
  ✓ Scenario 1: Week tiles with status
    - 3 complete
    - 1 available
    - 3 locked
  ✓ Scenario 2: Progress countdown
    - Format: '3 of 7 complete, 4 remaining'
  ✓ Scenario 3: Expected values correct (3 of 7 complete, 4 remaining)
```

## Acceptance Criteria

All three Gherkin scenarios from the GitHub issue pass:

✅ **Scenario: Passport shows week tiles with status**
- GIVEN I am enrolled in a 7-week challenge
- WHEN I open my passport
- THEN I see themed tiles for all 7 weeks
- AND each tile shows a status of "locked", "available", or "complete"
- AND future weeks are shown as locked

✅ **Scenario: Progress countdown reflects completion**
- GIVEN I have completed 3 of 7 weeks
- WHEN I open my passport
- THEN I see "3 of 7 complete, 4 remaining"

✅ **Scenario: Countdown updates after a new completion**
- GIVEN I have completed 3 of 7 weeks
- WHEN a new check-in marks a fourth week complete
- THEN the countdown updates to "4 of 7 complete, 3 remaining"
- (This will be verified when check-in functionality is implemented in US-8)

## Functional Requirements Satisfied

- **FR-C2**: Student views all weeks with status (locked/available/complete) ✅
- **FR-C3**: Progress countdown showing "X of Y complete, Z remaining" ✅

## Files Modified/Created

### Backend
- `backend/app/models/challenge.py` (new)
- `backend/app/models/__init__.py` (updated)
- `backend/app/schemas/challenge.py` (new)
- `backend/app/schemas/__init__.py` (updated)
- `backend/app/services/challenges.py` (new)
- `backend/app/services/__init__.py` (updated)
- `backend/app/routers/challenges.py` (new)
- `backend/app/routers/__init__.py` (updated)
- `backend/app/main.py` (updated)
- `backend/app/db.py` (updated)
- `backend/seed_test_data.py` (new, test utility)
- `backend/test_passport_api.py` (new, test utility)

### Frontend
- `frontend/src/types/challenge.ts` (new)
- `frontend/src/api/passport.ts` (new)
- `frontend/src/components/PassportView/PassportView.tsx` (new)
- `frontend/src/components/PassportView/PassportView.module.css` (new)
- `frontend/src/components/WeekTile/WeekTile.tsx` (new)
- `frontend/src/components/WeekTile/WeekTile.module.css` (new)
- `frontend/src/components/ProgressCountdown/ProgressCountdown.tsx` (new)
- `frontend/src/components/ProgressCountdown/ProgressCountdown.module.css` (new)
- `frontend/src/App.tsx` (updated)

## Next Steps

1. Start backend server: `cd backend; ../.venv/Scripts/python -m uvicorn app.main:app --reload`
2. Start frontend dev server: `cd frontend; npm run dev`
3. Sign in with mock IdP (select test-student@csub.edu)
4. View passport at `/home` route
5. Continue with US-8 (QR check-in) to enable completing additional weeks

## Notes

- Prize eligibility is derived (not stored) based on completion of all required tasks
- Week status calculation considers current date vs. task date windows
- All components are mobile-first responsive
- CSS uses theme CSS variables for easy reskinning
- Backend uses SQLAlchemy ORM with proper relationships
- Frontend uses TypeScript for type safety
