# US-15 Component Architecture Diagram

## Component Hierarchy

```
App.tsx
  └─ SessionProvider
      └─ ThemeProvider
          └─ BrowserRouter
              └─ Routes
                  └─ Route: /passport
                      └─ Passport.tsx ◄━━━ MODIFIED FOR US-15
                          │
                          ├─ PassportView
                          │   │
                          │   ├─ Header Section
                          │   │   ├─ Challenge Name
                          │   │   ├─ Progress Countdown
                          │   │   └─ Progress Bar
                          │   │
                          │   ├─ Week Tiles Grid
                          │   │   └─ Week Tile (button)
                          │   │       ├─ Week Number
                          │   │       ├─ Status Icon
                          │   │       ├─ Title
                          │   │       ├─ Activity Type
                          │   │       └─ Caption
                          │   │
                          │   └─ Detail Sheet Modal (when tile clicked)
                          │       ├─ Week Info
                          │       ├─ Metadata (where, when, prize)
                          │       └─ Check In Button ◄━━━ TRIGGERS US-15 FLOW
                          │
                          ├─ TipModal ◄━━━━━━━━━━━━━━━━ NEW COMPONENT (US-15)
                          │   │
                          │   ├─ Backdrop (click to close)
                          │   │
                          │   └─ Modal Dialog
                          │       │
                          │       ├─ Close Button (×)
                          │       │
                          │       ├─ Header Section
                          │       │   ├─ Success Icon (✓ in green circle)
                          │       │   ├─ Title: "Nice work!"
                          │       │   └─ Subtitle: "You checked in to {task}"
                          │       │
                          │       ├─ Personalized Tip Section
                          │       │   ├─ Icon (⚡) + Heading
                          │       │   └─ Tip Text (yellow gradient bg)
                          │       │
                          │       ├─ Campus Resource Section
                          │       │   ├─ Label
                          │       │   └─ Resource Text (blue accent)
                          │       │
                          │       ├─ Next Step Section
                          │       │   ├─ Label
                          │       │   └─ Next Step Text (purple accent)
                          │       │
                          │       ├─ Progress Section
                          │       │   ├─ Progress Header
                          │       │   ├─ Visual Progress Bar
                          │       │   └─ Prize Eligibility Status
                          │       │
                          │       └─ Continue Button
                          │
                          └─ Sign Out Bar
                              └─ Sign Out Button
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interaction                         │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                    Clicks "Check in" button
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Passport Component                           │
│  handleCheckIn(taskId: number)                                  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                      Calls API client function
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                     API Client Layer                             │
│  checkins.ts                                                     │
│  checkIn({ task_id, method: "manual" })                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
              POST /api/checkins/ (HTTP Request)
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Backend API                                 │
│  checkins.py router                                             │
│  - Validates enrollment                                         │
│  - Validates date window                                        │
│  - Creates check-in record                                      │
│  - Calculates progress                                          │
│  - Calls AI Tips Service                                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                        AI Tips Service
                                  │
                                  ↓
                        AWS Bedrock (Claude)
                                  │
                                  ↓
              Generates personalized tip (no PHI)
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CheckInResponse                               │
│  {                                                              │
│    checkin_id, task_title, checked_in_at,                      │
│    personalized_tip: { tip, resource, next_step },            │
│    progress: { completed, total, eligible }                    │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
          Returns to API client (Promise resolves)
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Passport Component                           │
│  setCheckInResponse(response)                                   │
│  Refreshes passport data                                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
              checkInResponse state is not null
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                      TipModal Renders                            │
│  Displays:                                                      │
│  - Success message                                              │
│  - Personalized tip                                             │
│  - Campus resource                                              │
│  - Next step                                                    │
│  - Progress visualization                                       │
│  - Prize eligibility                                            │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                     User reads tip and clicks
                              "Continue"
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                      TipModal Component                          │
│  onClose() callback                                             │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Passport Component                           │
│  handleCloseTipModal()                                          │
│  setCheckInResponse(null)                                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                 TipModal unmounts (conditional render)
                                  │
                                  ↓
         Passport view shows updated task status (complete)
```

---

## State Management

```
Passport Component State
├─ passport: PassportData | null
│   ├─ challengeName: string
│   ├─ theme: string
│   ├─ totalWeeks: number
│   ├─ completedWeeks: number
│   ├─ remainingWeeks: number
│   └─ weeks: PassportWeek[]
│       ├─ weekNo: number
│       ├─ taskId: number ◄━━━ ADDED FOR US-15
│       ├─ title: string
│       ├─ caption: string
│       ├─ activityType: string
│       ├─ location: string
│       ├─ dateStart: string | null
│       ├─ dateEnd: string | null
│       ├─ prize: string
│       ├─ required: boolean
│       └─ status: "locked" | "available" | "complete"
│
├─ dataLoading: boolean
│
├─ checkInResponse: CheckInResponse | null ◄━━━ NEW STATE (US-15)
│   ├─ checkin_id: number
│   ├─ task_title: string
│   ├─ checked_in_at: string
│   ├─ personalized_tip: PersonalizedTip
│   │   ├─ tip: string
│   │   ├─ resource: string
│   │   └─ next_step: string
│   └─ progress: CheckInProgress
│       ├─ completed_tasks: number
│       ├─ total_tasks: number
│       ├─ required_tasks: number
│       ├─ remaining_required_tasks: number
│       └─ is_prize_eligible: boolean
│
└─ (from useSession)
    ├─ session: Session | null
    │   ├─ subject: string
    │   ├─ affiliation: string
    │   ├─ isCurrentStudent: boolean
    │   └─ student_id: number ◄━━━ UPDATED FOR US-15
    ├─ loading: boolean
    └─ signOut: () => Promise<void>

PassportView Component State (presentational)
├─ selectedWeekNo: number | null
└─ submitting: boolean

TipModal Component State
└─ (no internal state, controlled by parent)
```

---

## API Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend API Clients                         │
└─────────────────────────────────────────────────────────────────┘

1. passport.ts (existing)
   ├─ fetchPassport(): Promise<Passport | null>
   │  └─ GET /api/passport
   │     Returns: Passport data with taskId ◄━━━ UPDATED FOR US-15
   │
   └─ checkIn(weekNo): Promise<Passport | null> ◄━━━ DEPRECATED
      └─ POST /api/checkins (old demo endpoint)

2. checkins.ts ◄━━━━━━━━━━━━━━━━━━━━━━━━ NEW FILE (US-15)
   ├─ checkIn(data): Promise<CheckInResponse>
   │  └─ POST /api/checkins/
   │     Body: { task_id: number, method: string }
   │     Returns: CheckInResponse with tip
   │
   └─ getProgress(challengeId): Promise<CheckInProgress>
      └─ GET /api/checkins/progress/{challengeId}
         Returns: Progress metrics

┌─────────────────────────────────────────────────────────────────┐
│                      Backend Endpoints                           │
└─────────────────────────────────────────────────────────────────┘

Existing:
├─ GET /api/passport
│  Returns passport with updated schema (includes taskId)
│
└─ POST /api/checkins (old demo endpoint)
   Uses weekNo, returns updated Passport

New (US-15):
├─ POST /api/checkins/ ◄━━━━━━━━━━━━━━━━ PRIMARY US-15 ENDPOINT
│  Body: { task_id, method }
│  Returns: CheckInResponse with personalized tip
│
└─ GET /api/checkins/progress/{challenge_id}
   Returns: CheckInProgress metrics
```

---

## Type System

```
┌─────────────────────────────────────────────────────────────────┐
│                      TypeScript Types                            │
└─────────────────────────────────────────────────────────────────┘

passport.ts (updated)
├─ WeekStatus = "locked" | "available" | "complete"
└─ PassportWeek
    └─ taskId: number ◄━━━ ADDED

session.ts (updated)
└─ Session
    └─ student_id: number ◄━━━ ADDED

checkin.ts ◄━━━━━━━━━━━━━━━━━━━━━━━━━━━━ NEW FILE
├─ CheckInMethod = "event_qr" | "staff" | "manual"
├─ CheckInRequest { task_id, method? }
├─ PersonalizedTip { tip, resource, next_step }
├─ CheckInProgress { completed_tasks, total_tasks, ... }
└─ CheckInResponse { checkin_id, task_title, ... }
```

---

## File Organization

```
frontend/src/
├── api/
│   ├── challenges.ts (existing)
│   ├── enrollment.ts (existing)
│   └── checkins.ts ◄━━━━━━━━━━━━━━━━━━━━ NEW
│
├── auth/ (existing)
│
├── components/
│   ├── Passport/
│   │   ├── Passport.tsx ◄━━━━━━━━━━━━━━ MODIFIED
│   │   └── Passport.module.css (existing)
│   │
│   ├── TipModal/ ◄━━━━━━━━━━━━━━━━━━━━━ NEW DIRECTORY
│   │   ├── TipModal.tsx ◄━━━━━━━━━━━━━━ NEW
│   │   ├── TipModal.module.css ◄━━━━━━━ NEW
│   │   └── TipModal.test.tsx ◄━━━━━━━━━ NEW
│   │
│   └── (other components)
│
├── passport/ (existing)
│
├── styles/ (existing)
│
├── theme/ (existing)
│
└── types/
    ├── challenge.ts (existing)
    ├── enrollment.ts (existing)
    ├── passport.ts ◄━━━━━━━━━━━━━━━━━━━━ MODIFIED
    ├── session.ts ◄━━━━━━━━━━━━━━━━━━━━━ MODIFIED
    └── checkin.ts ◄━━━━━━━━━━━━━━━━━━━━━ NEW
```

---

## Event Flow

```
User Actions → Component Events → State Updates → Re-renders

1. PAGE LOAD
   User visits /passport
   ↓
   Passport mounts
   ↓
   useEffect fetches passport data
   ↓
   PassportView renders with weeks

2. CLICK WEEK TILE
   User clicks week tile
   ↓
   setSelectedWeekNo(weekNo)
   ↓
   Detail sheet modal shows

3. CLICK CHECK IN ◄━━━━━━━━━━━━━━━━━━━━━ US-15 FLOW STARTS HERE
   User clicks "Check in" button
   ↓
   handleCheckIn(selectedWeek.taskId) called
   ↓
   setSubmitting(true)
   ↓
   API call: checkInApi({ task_id, method })
   ↓
   Backend processes check-in
   ↓
   Backend generates AI tip
   ↓
   Response returns with CheckInResponse
   ↓
   setCheckInResponse(response)
   ↓
   fetchPassport() to refresh data
   ↓
   setPassport(updatedPassport)
   ↓
   setSubmitting(false)
   ↓
   TipModal renders (conditional)
   ↓
   Detail sheet closes automatically
   ↓
   User sees TipModal ◄━━━━━━━━━━━━━━━━━━ US-15 SUCCESS STATE

4. VIEW TIP
   User reads personalized tip
   User sees progress
   User sees prize eligibility

5. CLOSE MODAL
   User clicks "Continue" or "×" or backdrop
   ↓
   onClose() callback
   ↓
   handleCloseTipModal() called
   ↓
   setCheckInResponse(null)
   ↓
   TipModal unmounts
   ↓
   PassportView shows updated status ◄━━━━ US-15 FLOW COMPLETE
```

---

## Error Handling

```
Try-Catch Flow in handleCheckIn()

try {
  const response = await checkInApi(...)
  ↓
  setCheckInResponse(response)
  ↓
  const updated = await fetchData()
  ↓
  setPassport(updated)
}
catch (error) {
  ↓
  console.error("Check-in failed:", error)
  ↓
  // TODO: Show error message to user
  ↓
  (Modal does not show on error)
}
finally {
  ↓
  (not currently used)
}

Possible Errors:
- 401 Unauthorized (not signed in)
- 403 Forbidden (not enrolled)
- 400 Bad Request (date window)
- 404 Not Found (task doesn't exist)
- 500 Server Error (backend issue)
- Network Error (offline, timeout)
```

---

## Accessibility Tree

```
TipModal Accessibility Structure

<div class="backdrop"> (click target)
  └─ <div class="modal" role="dialog" aria-modal="true" 
           aria-labelledby="tip-modal-title">
      │
      ├─ <button aria-label="Close"> × </button>
      │
      ├─ <div class="header">
      │   ├─ <div class="iconWrapper" aria-hidden="true">
      │   │   └─ CheckCircleIcon
      │   ├─ <h2 id="tip-modal-title"> Nice work! </h2>
      │   └─ <p class="subtitle"> You checked in to... </p>
      │
      ├─ <section class="tipSection">
      │   ├─ <div class="sectionHeader">
      │   │   ├─ BoltIcon
      │   │   └─ <h3> Your Personalized Tip </h3>
      │   └─ <p class="tip"> {tip text} </p>
      │
      ├─ <section class="resourceSection">
      │   ├─ <h4 class="sectionLabel"> Campus Resource </h4>
      │   └─ <p class="resource"> {resource text} </p>
      │
      ├─ <section class="nextStepSection">
      │   ├─ <h4 class="sectionLabel"> Next Step </h4>
      │   └─ <p class="nextStep"> {next step text} </p>
      │
      ├─ <section class="progressSection">
      │   ├─ <div class="progressBar">
      │   │   ├─ <span class="progressLabel"> Your Progress </span>
      │   │   ├─ <span class="progressCount"> X of Y tasks </span>
      │   │   └─ <div role="progressbar" 
      │   │          aria-valuenow="X" 
      │   │          aria-valuemin="0" 
      │   │          aria-valuemax="Y"
      │   │          aria-label="Challenge progress">
      │   │       └─ <div class="progressFill" style="width: X%">
      │   └─ <div class="prizeEligible"> or <p class="remainingTasks">
      │
      └─ <button class="continueBtn"> Continue </button>

Screen Reader Announces:
1. "Dialog, Nice work!"
2. "Your Personalized Tip, heading level 3"
3. "{tip text}"
4. "Campus Resource, heading level 4"
5. "{resource text}"
6. etc.
```

---

This diagram provides a comprehensive view of how the US-15 frontend implementation integrates with the existing codebase and how data flows through the system.
