## 📝 Summary of Changes

**Before:**
* Students could check in to tasks, but received no immediate feedback or guidance.
* Check-ins were recorded but provided no personalized wellness tips based on the specific activity completed.
* The `/api/checkins` endpoint returned only basic check-in confirmation without contextual support.
* No AI-driven tip generation existed to reinforce healthy habits or provide next steps.

**After:**
* Students receive personalized wellness tips immediately after each check-in, contextually relevant to the activity they completed.
* The check-in response includes a three-part tip structure: motivational message, SHS-approved resource link, and suggested next step.
* AI tip generation is grounded in SHS-approved content tags (configured per task by admins) to ensure age-appropriate, evidence-based guidance.
* A visual `TipNotification` component displays tips with smooth animations and accessibility support.
* Progress tracking shows completed/total tasks and prize eligibility status after each check-in.

---

## 🎟️ Related Issue / Ticket

Resolves: US-15 · Satisfies FR-D1, FR-D2, FR-E1 (`@source:UC-3, UC-8`)

---

## 💡 Motivation and Context

Students need immediate, personalized reinforcement when they complete wellness activities to help internalize healthy habits. This PR implements personalized tip generation (US-15) — delivering age-appropriate, evidence-based guidance at the moment of check-in to maximize engagement and learning outcomes. Tips are grounded in SHS-approved content to ensure safety and appropriateness for the college student population.

---

## 🛠️ How It Was Implemented

**Backend**

| Layer | File | What it does |
|---|---|---|
| Model | `backend/app/models/challenge.py` | Added `CheckInMethod` enum and `content_tags` field to `Task` for grounding AI tips |
| Schema | `backend/app/schemas/checkin.py` (new) | `CheckInRequest`, `PersonalizedTip`, `ProgressInfo`, `CheckInResponse` schemas |
| Service | `backend/app/services/ai_tips.py` (new) | AI tip generation using OpenAI, grounded in task's `content_tags` with fallback safety |
| Service | `backend/app/services/checkins.py` (new) | Check-in creation, enrollment verification, duplicate prevention, progress calculation |
| Router | `backend/app/routers/checkins.py` (new) | `POST /api/checkins` endpoint with tip generation and progress tracking |
| Wiring | `backend/app/main.py` | Checkins router registered |
| Config | `backend/app/config.py` | `OPENAI_API_KEY` environment variable support |

**Frontend**

| Layer | File | What it does |
|---|---|---|
| Types | `frontend/src/types/checkin.ts` (new) | TypeScript interfaces for check-in requests and responses with tips |
| API client | `frontend/src/api/checkins.ts` (new) | Typed `fetch` wrapper for check-in endpoint |
| UI Component | `frontend/src/components/TipNotification/` (new) | Animated tip card with accessibility support, auto-dismiss, and manual close |
| Passport | `frontend/src/components/Passport/Passport.tsx` | Integrated check-in flow with tip display and progress refresh |
| Styles | `frontend/src/components/TipNotification/TipNotification.module.css` | Slide-in animation, responsive layout, WCAG-compliant color contrast |

**Key design decisions**
- AI tip generation happens synchronously during check-in to provide immediate feedback. Timeout and error handling ensure the check-in succeeds even if tip generation fails.
- Content tags on tasks (set by admins) ground the AI prompt to ensure tips are contextually relevant and aligned with SHS-approved curriculum.
- The tip structure (message + resource + next_step) is enforced by the Pydantic schema and AI prompt template to maintain consistency.
- Progress calculation includes prize eligibility logic (all required tasks complete) to motivate students toward completion.
- Frontend optimistically shows tips while refreshing passport data in the background to keep UI responsive.

---

## 🔍 How to Review

1. **Data model** — `backend/app/models/challenge.py`: verify `CheckInMethod` enum values and `content_tags` field on `Task` model for AI grounding.
2. **Check-in flow** — `backend/app/services/checkins.py`: review enrollment verification, duplicate check-in prevention, and progress calculation logic.
3. **AI tip generation** — `backend/app/services/ai_tips.py`: examine prompt template, content tag integration, fallback handling, and timeout protection.
4. **API contract** — `backend/app/schemas/checkin.py`: confirm response schema includes tip structure (tip, resource, next_step) and progress info.
5. **Frontend integration** — `frontend/src/components/Passport/Passport.tsx`: trace check-in → tip display → progress refresh flow.
6. **UI component** — `frontend/src/components/TipNotification/TipNotification.tsx`: verify accessibility (aria-live, keyboard support), animation timing, and auto-dismiss behavior.
7. **Error handling** — Check that check-ins succeed even when tip generation fails (degraded experience, not broken flow).

---

## 🧪 How to Test

**Automated**
```bash
# Backend — check-in and tip generation tests
cd backend && .venv/bin/python -m pytest tests/test_checkins.py -v

# Frontend — typecheck + existing tests
cd frontend && npx tsc -b --noEmit && npm test
```

**Manual (dev servers running, OPENAI_API_KEY set)**
1. Open `http://localhost:5173/` → sign in as a Student.
2. Enroll in the active challenge if not already enrolled.
3. Navigate to your passport → find an available (unlocked) week.
4. Click on the week tile → in the detail sheet, click **Check in**.
5. Verify a tip notification slides in from the bottom with:
   - A personalized motivational message related to the activity
   - An SHS resource recommendation
   - A suggested next step
6. Wait 8 seconds → verify the tip auto-dismisses with a fade-out animation.
7. Click the × button on a tip → verify it dismisses immediately.
8. Complete another check-in → verify the progress counter updates correctly.
9. Complete all required tasks → verify `is_prize_eligible: true` in the response (check browser dev tools Network tab).
10. Try to check in to the same task again → verify a 409 error with "already checked in" message.

**Testing without OpenAI API key:**
- Unset `OPENAI_API_KEY` → verify check-ins still succeed but return a generic fallback tip message.

---

## 📸 Screenshots / Screen Recordings

| Before | After |
| ------ | ----- |
| Check-in succeeded with no feedback | Personalized tip notification slides in after check-in |
| No AI-driven guidance for students | Context-aware tips based on activity type and content tags |
| Progress data not surfaced to student | Check-in response includes completed/total and prize eligibility |

---

## ✅ Checklist

-   [x] I have included the associated stories JIRA ticket number in the branch name
-   [x] I have performed a self-review of my own code.
-   [x] Any non-obvious behavior has a comment explaining *why*.
-   [x] I have made corresponding changes to the documentation.
-   [x] My code is free of typos.
-   [x] My PR only has files I intended to change.
-   [x] My PR source branch is up to date with the target branch.
-   [x] My changes generate no new warnings.
-   [x] I have added tests that prove my fix is effective or that my feature works.
-   [ ] Acceptance criteria (Gherkin in `features/`) are bound by pytest-bdd step defs and pass at the appropriate tier (`make test-api` / `make test-e2e`). If E2E coverage is deferred, note which story picks it up.
-   [x] The Github pipeline is green (commit lint, codegen drift, typecheck, test-api).
-   [x] New and existing unit tests pass locally with my changes.
-   [x] Any dependent changes have been merged and published in downstream modules.
-   [x] The code introduces no new "code smells" or SOLID violations
-   [x] The code does not negatively impact system performance and any performance-specific criteria are met
-   [x] Any updates to the user interface meet accessibility standards ala WCAG
-   [ ] Any unavoidable tech debt is documented in a new story in the backlog with a tech debt label, reviewer with the technical lead and PO and linked to the story that generated the tech debt

---

## Additional Notes

**AI Safety & Grounding:** Tips are generated using task-specific `content_tags` (set by admins in the challenge builder) to ground responses in SHS-approved content. The prompt template explicitly instructs the AI to provide age-appropriate, evidence-based guidance suitable for college students. A fallback generic tip is returned if OpenAI is unavailable or times out.

**Performance:** Tip generation adds ~1-2s latency to check-in requests (OpenAI API call). This is acceptable for the current scale; if latency becomes an issue at scale, consider moving tip generation to a background job and displaying tips on next passport load.

**Gherkin / pytest-bdd note:** US-15 acceptance criteria are covered by plain pytest tests in `tests/test_checkins.py`. Formal `pytest-bdd` step-definition binding is deferred — a follow-up story should wire `features/checkins_with_tips.feature` to these steps so CI can run them from `.feature` files directly.
