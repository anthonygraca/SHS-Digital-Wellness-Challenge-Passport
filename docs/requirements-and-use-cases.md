# Requirements & Use Cases
## SHS Digital Wellness Passport — CSUB Student Health Services (DxHub 2026)

Companion to `architecture-plan.md`. This is an **initial** set — a working draft to confirm with SHS
(Erika, Lauren) and ITS (Brian, Dominique). Each requirement has a stable ID for traceability; each
use case maps back to the requirements it satisfies.

Priority: **M** = MVP / must-have for the camp demo · **S** = should-have · **C** = could-have / stretch.

---

## 1. Actors

| Actor | Description |
|---|---|
| **Student** | CSU student who opts into a wellness challenge; primary end user. |
| **SHS Staff (Admin)** | Health Services staff who author challenges, run events, and report. Erika (Director), Lauren (Health Ed Coordinator). |
| **Event Attendant** | Staff/volunteer stationed at an event who displays/scans QR codes (may be the same person as Admin). |
| **Campus IdP** | SAML identity provider that authenticates users and asserts current-student attributes. |
| **AI Wellness Guide** | System actor: Claude-backed assistant for education, conversation, and scoring. |
| **Reporting Consumer** | SHS leadership / CSU stakeholders who read participation & outcome reports. |

---

## 2. Functional Requirements

### 2.1 Identity & Access (FR-A)
| ID | Requirement | Pri |
|---|---|---|
| FR-A1 | Users authenticate via campus **SAML SSO**; no manual ID/9-digit entry. | M |
| FR-A2 | System stores only an opaque SSO subject + affiliation attributes (no PHI, no password). | M |
| FR-A3 | Participation may be gated on **current-student** attributes from the SAML assertion. | S |
| FR-A4 | Admin access is role-restricted (student role cannot reach builder/reports). | M |
| FR-A5 | Every record is scoped by `campus_id` to support multi-campus (CSU-wide) deployment. | S |

### 2.2 Challenge Authoring (FR-B) — Admin
| ID | Requirement | Pri |
|---|---|---|
| FR-B1 | Admin creates a challenge with name, semester, start/end, and an ordered list of weekly tasks. | M |
| FR-B2 | Each task has: title, caption, activity type, location, date window, prize, required flag. | M |
| FR-B3 | Admin attaches assessment items (MCQ and/or reflection) to a task, each tagged to a learning outcome. | S |
| FR-B4 | Admin selects/edits a **theme** (palette, logo, hero art, copy tone) applied to the student app. | S |
| FR-B5 | Admin can **AI-import** a source document (Word/PDF) to auto-draft weeks, tasks, captions, and quiz items for editing. | S |
| FR-B6 | Admin can duplicate a prior challenge as a starting point. | C |

### 2.3 Enrollment & Passport (FR-C) — Student
| ID | Requirement | Pri |
|---|---|---|
| FR-C1 | Student enrolls in the active challenge for their campus. | M |
| FR-C2 | Student views all weeks/tasks with status (locked / available / complete). | M |
| FR-C3 | Student sees a **progress countdown** ("3 of 7 complete, 4 remaining"). | M |
| FR-C4 | App is **mobile-first / installable (PWA)** and usable offline for viewing progress. | M |
| FR-C5 | Student sees prize eligibility status derived from required-task completion. | S |

### 2.4 Check-In (FR-D)
| ID | Requirement | Pri |
|---|---|---|
| FR-D1 | Student marks a task complete by **scanning an event QR** in-app. | M |
| FR-D2 | Backend validates the scan (task active, student eligible, not duplicate) before recording. | M |
| FR-D3 | Alternative: **Event Attendant scans the student's** passport QR for higher-assurance events. | S |
| FR-D4 | Each check-in records student, task, timestamp, and method (`event_qr` / `staff` / `manual`). | M |
| FR-D5 | Production: event QR is a **signed, short-lived rotating token** to prevent off-site sharing. | C |
| FR-D6 | Admin can manually add/override a completion with an audit trail. | S |

### 2.5 AI Education, Guide & Assessment (FR-E)
| ID | Requirement | Pri |
|---|---|---|
| FR-E1 | On check-in, the student receives a **personalized tip/resource** grounded in SHS content. | M |
| FR-E2 | Student can converse with a **themed AI wellness guide** grounded in SHS content. | M |
| FR-E3 | Guide has guardrails: educational only, no diagnosis, **crisis routing** to real resources. | M |
| FR-E4 | MCQ knowledge checks are **auto-scored** instantly. | S |
| FR-E5 | Free-text reflections are **AI-scored against a rubric** with feedback; human override allowed. | S |
| FR-E6 | All model calls are server-side (Bedrock); no PHI sent; conversations minimally logged. | M |

### 2.6 Reporting (FR-F) — Admin
| ID | Requirement | Pri |
|---|---|---|
| FR-F1 | Report on participation and per-week completion funnel. | M |
| FR-F2 | Report auto-captured vs. manual attendance counts. | S |
| FR-F3 | Report engagement (content views, guide usage). | S |
| FR-F4 | Report aggregated learning-outcome scores by outcome tag. | S |
| FR-F5 | Export prize-eligible students (CSV) for the drawing. | M |
| FR-F6 | Reports are aggregated/privacy-aware; optionally surfaced in QuickSight. | C |

---

## 3. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Privacy:** no PHI; FERPA-aware handling of participation records; minimal identity. |
| NFR-2 | **Security:** SAML SSO, role-based access, encryption at rest (S3/RDS) and in transit (TLS). |
| NFR-3 | **Supportability:** production stack is **C# / ASP.NET Core + Microsoft SQL Server** for CSU teams. |
| NFR-4 | **Portability / multi-tenant:** single codebase deploys per CSU campus via campus↔IdP mapping. |
| NFR-5 | **Usability:** mobile-first, low-friction; QR scan-to-complete in a few taps. |
| NFR-6 | **Themeability:** semester re-skin is a config change, not a code change. |
| NFR-7 | **Availability/scale:** handle event-time bursts for ~hundreds of concurrent students; low steady load. |
| NFR-8 | **AI safety:** grounded responses, refusal on out-of-scope, hard-coded crisis escalation. |
| NFR-9 | **Standalone:** no dependency on the EHR ("Point and Click"); no external clinical integration. |
| NFR-10 | **Observability:** check-ins, scores, and errors are logged for reporting and audit. |

---

## 4. Use Cases

### UC-1 — Student authenticates and enrolls
- **Actor:** Student · **Pri:** M · **Satisfies:** FR-A1, FR-A2, FR-A3, FR-C1
- **Precondition:** An active challenge exists for the student's campus.
- **Main flow:**
  1. Student opens the PWA and taps "Sign in with campus SSO."
  2. System redirects to the campus IdP; student authenticates.
  3. IdP returns an assertion with subject + current-student attributes.
  4. System provisions/loads the student record (SSO subject only) and confirms eligibility.
  5. Student taps "Join the [Theme] Challenge"; enrollment is created.
- **Alt / exceptions:** Not a current student → enrollment blocked with a friendly message (FR-A3).
  First-time login → student record created on the fly.

### UC-2 — Student views passport & progress
- **Actor:** Student · **Pri:** M · **Satisfies:** FR-C2, FR-C3, FR-C4, FR-C5
- **Main flow:** Student opens passport → sees themed week tiles with status, a progress countdown,
  and prize-eligibility indicator. Available weeks are highlighted; future weeks are locked.
- **Alt:** Offline → last-synced progress is shown from cache (FR-C4).

### UC-3 — Student checks in at an event via QR  *(core loop)*
- **Actor:** Student, Event Attendant · **Pri:** M · **Satisfies:** FR-D1, FR-D2, FR-D4, FR-E1
- **Precondition:** Student authenticated & enrolled; the task's event is active.
- **Main flow:**
  1. Attendant displays the event QR (per-event code; rotating token in production).
  2. Student taps "Scan" → app opens camera → captures the QR.
  3. App posts `{token, student, task}` to the API.
  4. API validates: task active, student eligible, no duplicate check-in.
  5. API records the check-in; the week flips to **complete** and the countdown updates.
  6. Student is shown a **personalized tip/resource** for that task (UC-6).
- **Alt / exceptions:**
  - Duplicate scan → "Already completed this week" (no double count).
  - Expired/invalid token → "This code is no longer valid, ask the attendant" (FR-D5).
  - Wrong week/date window → rejected with reason (FR-D2).

### UC-4 — Staff verifies a student directly  *(high-assurance option)*
- **Actor:** Event Attendant · **Pri:** S · **Satisfies:** FR-D3, FR-D4
- **Main flow:** Attendant opens staff mode → scans the student's personal passport QR → confirms
  the task → check-in recorded with `method = staff`.

### UC-5 — Admin builds/edits a challenge
- **Actor:** SHS Staff (Admin) · **Pri:** M · **Satisfies:** FR-B1, FR-B2, FR-B3, FR-B4
- **Main flow:** Admin creates a challenge, adds ordered weekly tasks (title, caption, dates,
  location, prize, required flag), attaches assessment items with outcome tags, and selects a theme.
- **Alt:** Duplicate a prior challenge as a template (FR-B6).

### UC-6 — Student receives personalized health education
- **Actor:** Student, AI Wellness Guide · **Pri:** M · **Satisfies:** FR-E1, FR-E6
- **Trigger:** A successful check-in (UC-3), or opening a week.
- **Main flow:** System requests a tailored tip from the guide (personalized by task, progress, and
  interests), grounded in SHS content, and displays it with a resource/short video and next step.

### UC-7 — Student consults the AI wellness guide
- **Actor:** Student, AI Wellness Guide · **Pri:** M · **Satisfies:** FR-E2, FR-E3, FR-E6
- **Main flow:** Student opens the themed guide chat and asks a wellness question; the guide answers
  from SHS-grounded content, nudges the next task, and links campus resources.
- **Alt / exceptions:**
  - Out-of-scope / medical-advice request → guide declines and redirects to SHS/clinician (FR-E3).
  - **Crisis signal detected** → guide immediately surfaces crisis resources (988/campus counseling)
    and SHS contact (FR-E3, NFR-8).

### UC-8 — Student completes an assessment (knowledge check / reflection)
- **Actor:** Student, AI Wellness Guide · **Pri:** S · **Satisfies:** FR-E4, FR-E5
- **Main flow:** Student answers MCQs (auto-scored) and/or writes a reflection (AI-scored vs. rubric
  with feedback). Scores are stored against the learning-outcome tag.
- **Alt:** Admin reviews/overrides an AI score (`scored_by = human`, FR-E5).

### UC-9 — Admin AI-imports a challenge from a document  *(sleeper feature)*
- **Actor:** SHS Staff (Admin), AI Wellness Guide · **Pri:** S · **Satisfies:** FR-B5
- **Main flow:** Admin uploads the challenge Word/PDF (e.g. `Stranger Things Challenge.docx`); the AI
  drafts structured weeks, tasks, date windows, prizes, themed captions, and starter quiz items;
  admin reviews and edits before publishing.

### UC-10 — Admin runs reports & exports prize list
- **Actor:** SHS Staff (Admin), Reporting Consumer · **Pri:** M · **Satisfies:** FR-F1, FR-F2, FR-F3, FR-F4, FR-F5
- **Main flow:** Admin opens the dashboard → views participation, per-week completion funnel,
  attendance auto-vs-manual, engagement, and learning-outcome aggregates → exports prize-eligible
  students to CSV for the drawing.

### UC-11 — Admin manages a live event
- **Actor:** SHS Staff (Admin), Event Attendant · **Pri:** S · **Satisfies:** FR-D4, FR-D6
- **Main flow:** Admin generates the event QR, watches real-time check-in counts, and manually
  adds/overrides completions with an audit trail where needed.

### UC-12 — Deploy to another CSU campus  *(stretch)*
- **Actor:** ITS · **Pri:** C · **Satisfies:** FR-A5, NFR-4
- **Main flow:** ITS registers the campus IdP (SAML), sets `campus_id` mapping, and deploys the same
  codebase; the campus authors its own challenges with no code change.

---

## 5. Traceability (use case → requirements)

| Use case | Requirements |
|---|---|
| UC-1 Auth & enroll | FR-A1, FR-A2, FR-A3, FR-C1 |
| UC-2 View passport | FR-C2, FR-C3, FR-C4, FR-C5 |
| UC-3 QR check-in | FR-D1, FR-D2, FR-D4, FR-E1 |
| UC-4 Staff verify | FR-D3, FR-D4 |
| UC-5 Build challenge | FR-B1, FR-B2, FR-B3, FR-B4 |
| UC-6 Personalized education | FR-E1, FR-E6 |
| UC-7 Wellness guide | FR-E2, FR-E3, FR-E6 |
| UC-8 Assessment | FR-E4, FR-E5 |
| UC-9 AI doc import | FR-B5 |
| UC-10 Reporting/export | FR-F1–FR-F5 |
| UC-11 Live event | FR-D4, FR-D6 |
| UC-12 Multi-campus | FR-A5, NFR-4 |

---

## 6. Out of scope (confirmed by discovery call)

- EHR / "Point and Click" integration — proprietary, non-integrating (NFR-9).
- Storing or processing any PHI / clinical results.
- Native iOS/Android apps (PWA covers the need).
- Payment/prize fulfillment logistics (system only determines *eligibility*).

## 7. Assumptions to confirm with SHS / ITS

1. CSUB test IdP/SP available for the demo, or SAML mocked for Friday.
2. Amazon Bedrock (Claude) enabled in the account/region on the landing zone.
3. Which SHS wellness materials are cleared to ground the guide/tips (RAG corpus).
4. Exact crisis-routing resources (988, campus counseling, SHS front desk).
5. "Good faith" check-in is acceptable for MVP; rotating signed QR deferred to production.
6. Prototype stack confirmed as .NET/SQL Server (recommended) vs. Python.
