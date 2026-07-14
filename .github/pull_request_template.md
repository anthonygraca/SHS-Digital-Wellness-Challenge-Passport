## 📝 Summary of Changes

**Before:**
* No challenge or task data model existed. Admin users had no way to create or manage challenges.
* The `/api/*` namespace was empty — only `/auth/*` routes existed.
* The frontend had no admin surface; all authenticated users landed on the same page regardless of role.
* The mock IdP login page offered no quick-fill presets, making it awkward to test different roles.

**After:**
* Admins can create draft challenges (name, semester, start/end dates) scoped to their campus, add an ordered list of weekly tasks with all required attributes (title, caption, activity type, location, date window, prize, required flag), reorder tasks via drag-and-drop, and publish a challenge.
* A full `/api/challenges` REST API is live, gated behind a new `require_admin` dependency (returns 401 / 403 for non-admin callers).
* Staff/admin users see a "Challenge Builder →" link on the landing page and are routed to `/admin`, which is protected by a client-side `AdminRoute` guard.
* The mock IdP login page now has "Student" and "Staff (admin)" preset buttons for fast role switching in development.

---

## 🎟️ Related Issue / Ticket

Resolves: US-11 · Satisfies FR-B1, FR-B2 (`@source:UC-5`)

---

## 💡 Motivation and Context

SHS staff need to author and manage wellness challenges each semester without engineering involvement. This PR implements the challenge builder (UC-5, US-11) — the foundational admin capability that all downstream features (enrollment, check-in, reporting) depend on. Challenges are pure data/config; no code changes are needed to set up a new semester.

---

## 🛠️ How It Was Implemented

**Backend**

| Layer | File | What it does |
|---|---|---|
| Model | `backend/app/models/challenge.py` | `Challenge` (campus-scoped, draft/published status) + `Task` (ordered by `position`, cascade-delete) |
| Auth | `backend/app/auth/deps.py` | New `require_admin` dependency — 401 if no session, 403 if affiliation is not `staff`/`admin` |
| Schema | `backend/app/schemas/challenge.py` | `ChallengeCreate/Update/Out/Summary`, `TaskCreate/Update/Out`, `TaskReorder` with duplicate-ID validation |
| Service | `backend/app/services/challenges.py` | Full CRUD + gap-closing delete + reorder (validates exact task-ID set) |
| Router | `backend/app/routers/challenges.py` | 9 endpoints under `/api/challenges`, all `require_admin`-gated |
| Wiring | `backend/app/main.py`, `backend/app/db.py` | Challenge router registered; challenge model imported in `init_db()` |

**Frontend**

| Layer | File | What it does |
|---|---|---|
| Types | `frontend/src/types/challenge.ts` | TypeScript interfaces mirroring all backend schemas |
| API client | `frontend/src/api/challenges.ts` | Typed `fetch` wrappers for all challenge + task endpoints; `ApiError` class |
| Builder UI | `frontend/src/components/admin/ChallengeBuilder/` | List → detail navigation, task list with HTML5 drag-to-reorder, challenge and task modals |
| Route guard | `frontend/src/App.tsx` | `AdminRoute` checks `session.affiliation`; adds `/admin` route |
| Landing | `frontend/src/components/Landing/Landing.tsx` | Shows "Challenge Builder →" link for staff/admin sessions |
| Mock IdP | `backend/app/routers/auth.py` | Preset buttons for Student and Staff (admin) roles |

**Key design decisions**
- Reordering is a `PUT /api/challenges/{id}/tasks/order` that accepts the full ordered ID list and re-assigns gapless 1-based positions in one transaction. The service validates that the incoming set exactly matches the challenge's tasks to prevent partial or cross-challenge reorders.
- Campus isolation is enforced at the service layer — every query filters by `campus_id` from the admin's JWT claims. A 404 is returned rather than a 403 to avoid leaking the existence of other campuses' challenges.
- The `require_admin` dependency is intentionally affiliation-string-based (contains `admin` or `staff`) to match the existing mock IdP pattern and require zero schema changes for the student model.

---

## 🔍 How to Review

1. **Data model** — `backend/app/models/challenge.py`: verify `position` ordering, cascade delete, and the campus-scoping UniqueConstraint.
2. **Auth enforcement** — `backend/app/auth/deps.py` (`require_admin`) + `backend/app/routers/challenges.py`: confirm every endpoint depends on it and that campus isolation is applied to every DB query in `backend/app/services/challenges.py`.
3. **Reorder logic** — `services/challenges.py::reorder_tasks`: check the exact-ID-set validation and the single-transaction position assignment.
4. **Frontend builder** — `frontend/src/components/admin/ChallengeBuilder/ChallengeBuilder.tsx`: review the drag-and-drop optimistic update, the `AdminRoute` guard in `App.tsx`, and the `ApiError` propagation pattern in `api/challenges.ts`.
5. **Tests** — `backend/tests/test_challenges.py`: all four Gherkin scenarios (create, add tasks, reorder, publish) are covered including the 403/401 RBAC cases.

---

## 🧪 How to Test

**Automated**
```bash
# Backend — 27 tests, all pass
cd backend && .venv/bin/python -m pytest tests/ -v

# Frontend — typecheck + existing tests
cd frontend && npx tsc -b --noEmit && npm test
```

**Manual (dev servers running)**
1. Open the mock IdP at `http://localhost:5173/` → click "Sign in with campus SSO".
2. On the mock IdP page, click **Staff (admin)** to prefill the affiliation, then click "Authenticate".
3. On the landing page, click **Challenge Builder →**.
4. Create a challenge (name, semester, start/end dates) → verify it appears in the list with "draft" status.
5. Open the challenge → click **+ Add task** → fill in all fields including date window, prize, and required flag → save.
6. Add at least 3 more tasks, then drag-and-drop to reorder — verify positions update correctly after drop.
7. Click **Edit** on a task, change the caption, save — verify the change persists on re-fetch.
8. Click **Delete** on the middle task — verify the remaining tasks close the position gap.
9. Click **Publish** — verify the badge changes to "published" and the button disappears.
10. Sign out, sign back in as **Student**, navigate to `http://localhost:5173/admin` directly — verify redirect back to `/home`.

---

## 📸 Screenshots / Screen Recordings

| Before | After |
| ------ | ----- |
| No admin surface; all users see the same landing card | Staff users see "Challenge Builder →" link on landing |
| Mock IdP has a single free-text affiliation field | Mock IdP has Student / Staff (admin) quick-fill buttons |
| No `/api/challenges` routes | Full challenge + task CRUD available under `/api/challenges` |

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

**Gherkin / pytest-bdd note:** The four US-11 Gherkin scenarios are covered by plain pytest tests in `tests/test_challenges.py` (matching the scenario titles 1-to-1). Formal `pytest-bdd` step-definition binding is deferred — a follow-up tech-debt story should wire `features/create_challenge.feature` to these steps so the CI `make test-api` target can run them from the `.feature` files directly.

**`tsconfig.tsbuildinfo`** is included in the diff as a build artifact — it can be added to `.gitignore` if the team prefers not to track it.
