# Features, User Stories & Acceptance Criteria
## SHS Digital Wellness Passport — CSUB Student Health Services (DxHub 2026)

Companion to `requirements-and-use-cases.md` and `architecture-plan.md`.

**Hierarchy.** Each **use case is a Feature** — a cohesive capability that delivers user value.
Under each feature sit one or more **user stories** (`As a… I want… so that…`), each an
independently shippable, independently testable slice. Each story's **acceptance criteria** are
written as Gherkin (`Given / When / Then`) scenarios. Story tags (`@FR-xx`, `@source:UC-n`) preserve
traceability to the requirements.

```
Feature (Use Case)  ──▶  User Story  ──▶  Acceptance Criteria (Gherkin scenarios)
```

Priority: **M** = MVP / must-have · **S** = should-have · **C** = could-have / stretch.

**MVP stories** (Phase 1–2 of the build plan): US-1, US-3, US-4, US-5, US-6, US-8, US-15, US-16,
US-17, US-21, US-26.

---

## Story index

| Story | Title | Feature (UC) | Satisfies | Pri |
|---|---|---|---|---|
| [US-1](#us-1--campus-sso-sign-in) | Campus SSO sign-in | UC-1 | FR-A1, A2 | M |
| [US-2](#us-2--current-student-eligibility-gate) | Current-student eligibility gate | UC-1 | FR-A3 | S |
| [US-3](#us-3--challenge-enrollment) | Challenge enrollment | UC-1 | FR-C1 | M |
| [US-4](#us-4--role-based-access-control) | Role-based access control | UC-1 | FR-A4 | M |
| [US-5](#us-5--view-passport--progress-countdown) | View passport & progress countdown | UC-2 | FR-C2, C3 | M |
| [US-6](#us-6--offline--installable-pwa-viewing) | Offline / installable PWA viewing | UC-2 | FR-C4 | M |
| [US-7](#us-7--prize-eligibility-indicator) | Prize-eligibility indicator | UC-2 | FR-C5 | S |
| [US-8](#us-8--student-qr-self-check-in) | Student QR self-check-in | UC-3 | FR-D1, D2, D4, E1 | M |
| [US-9](#us-9--rotating-signed-qr-token) | Rotating signed QR token | UC-3 | FR-D5 | C |
| [US-10](#us-10--staff-scans-student-verification) | Staff-scans-student verification | UC-4 | FR-D3, D4 | S |
| [US-11](#us-11--create--edit-challenge-with-weekly-tasks) | Create/edit challenge with weekly tasks | UC-5 | FR-B1, B2 | M |
| [US-12](#us-12--attach-assessment-items-with-outcome-tags) | Attach assessment items with outcome tags | UC-5 | FR-B3 | S |
| [US-13](#us-13--theme-selection--re-skin) | Theme selection / re-skin | UC-5 | FR-B4 | S |
| [US-14](#us-14--duplicate-prior-challenge) | Duplicate prior challenge | UC-5 | FR-B6 | C |
| [US-15](#us-15--post-check-in-personalized-tip) | Post-check-in personalized tip | UC-6 | FR-E1, E6 | M |
| [US-16](#us-16--conversational-wellness-guide) | Conversational wellness guide | UC-7 | FR-E2, E6 | M |
| [US-17](#us-17--guide-guardrails--crisis-routing) | Guide guardrails + crisis routing | UC-7 | FR-E3, NFR-8 | M |
| [US-18](#us-18--mcq-auto-scoring) | MCQ auto-scoring | UC-8 | FR-E4 | S |
| [US-19](#us-19--ai-reflection-scoring--human-override) | AI reflection scoring + human override | UC-8 | FR-E5 | S |
| [US-20](#us-20--ai-document-import-to-draft-challenge) | AI document import to draft challenge | UC-9 | FR-B5 | S |
| [US-21](#us-21--participation--completion-funnel-report) | Participation & completion funnel report | UC-10 | FR-F1 | M |
| [US-22](#us-22--auto-vs-manual-attendance-report) | Auto-vs-manual attendance report | UC-10 | FR-F2 | S |
| [US-23](#us-23--engagement-report) | Engagement report | UC-10 | FR-F3 | S |
| [US-24](#us-24--learning-outcome-aggregate-report) | Learning-outcome aggregate report | UC-10 | FR-F4 | S |
| [US-25](#us-25--reporting-privacy--aggregation) | Reporting privacy / aggregation | UC-10 | FR-F6, NFR-1 | C |
| [US-26](#us-26--prize-eligible-csv-export) | Prize-eligible CSV export | UC-10 | FR-F5 | M |
| [US-27](#us-27--manual-completion-override--audit) | Manual completion override + audit | UC-11 | FR-D6 | S |
| [US-28](#us-28--live-event-dashboard) | Live event dashboard | UC-11 | FR-D4 | S |
| [US-29](#us-29--campus-idp-registration--tenancy) | Campus IdP registration & tenancy | UC-12 | FR-A5, NFR-4 | C |

---

## Feature UC-1 — Student authenticates and enrolls
**Pri:** M · **Satisfies:** FR-A1, A2, A3, C1 · **Actor:** Student

A student signs in through campus SSO and joins the active challenge, with access and eligibility
enforced. Stories: US-1, US-2, US-3, US-4.

### US-1 — Campus SSO sign-in
**Pri:** M · **Satisfies:** FR-A1, FR-A2

**Description.** Students authenticate exclusively through the campus SAML identity provider. The
system never asks for a manually entered 9-digit ID or a password, and stores only an opaque SSO
subject plus affiliation attributes — no PHI, no credentials.

**User story.** As a CSU student, I want to sign in with my campus SSO so that I never type a
9-digit ID and no password is stored about me.

```gherkin
@FR-A1 @FR-A2 @security @source:UC-1
Feature: Campus SSO sign-in

  Scenario: First-time student authenticates via campus IdP
    Given I am not signed in
    And no student record exists for my SSO subject
    When I tap "Sign in with campus SSO"
    And the campus IdP returns a valid assertion for subject "abc@csub.edu"
    Then a student record is created storing only the SSO subject and affiliation
    And no password, name, or 9-digit ID is stored

  Scenario: Returning student is loaded, not duplicated
    Given a student record exists for SSO subject "abc@csub.edu"
    When I sign in with campus SSO
    Then my existing record is loaded
    And no duplicate student record is created

  Scenario: Failed authentication does not create a record
    When the campus IdP returns a failed or invalid assertion
    Then I am not signed in
    And no student record is created
    And I see a retry prompt
```

### US-2 — Current-student eligibility gate
**Pri:** S · **Satisfies:** FR-A3

**Description.** Participation can be gated on current-student attributes asserted by the IdP, so
past students or non-students are blocked from enrolling with a friendly message.

**User story.** As Student Health Services, I want participation gated on current-student status so
that only eligible students can join a challenge.

```gherkin
@FR-A3 @source:UC-1
Feature: Current-student eligibility gate

  Scenario: Current student passes the eligibility gate
    Given the campus IdP asserts I am a current student
    When I attempt to enroll in the active challenge
    Then I am allowed to proceed

  Scenario: Non-current student is blocked with a friendly message
    Given the campus IdP does not assert current-student status
    When I attempt to enroll in the active challenge
    Then enrollment is blocked
    And I see a friendly message explaining eligibility
```

### US-3 — Challenge enrollment
**Pri:** M · **Satisfies:** FR-C1

**Description.** An authenticated, eligible student joins the active challenge for their campus,
creating an enrollment record.

**User story.** As a student, I want to join the active challenge for my campus so that I can start
earning check-ins and prizes.

```gherkin
@FR-C1 @source:UC-1
Feature: Challenge enrollment

  Background:
    Given I am authenticated and eligible
    And an active challenge exists for my campus

  Scenario: Student enrolls in the active challenge
    When I tap "Join the [Theme] Challenge"
    Then an enrollment is created linking me to that challenge
    And I am taken to my passport

  Scenario: Student cannot enroll twice
    Given I am already enrolled in the active challenge
    When I open the app
    Then I see my passport directly
    And no duplicate enrollment is created

  Scenario: No active challenge for the campus
    Given no active challenge exists for my campus
    When I sign in
    Then I see a "no active challenge" message
    And I am not offered an enrollment action
```

### US-4 — Role-based access control
**Pri:** M · **Satisfies:** FR-A4

**Description.** Admin surfaces (builder, reports, live ops) are restricted by role. A student role
cannot reach any admin capability.

**User story.** As Student Health Services, I want admin tools restricted to staff roles so that
students cannot author challenges or read reports.

```gherkin
@FR-A4 @security @source:UC-1
Feature: Role-based access control

  Scenario: Student is denied access to the admin builder
    Given I am signed in with the student role
    When I attempt to open the challenge builder
    Then access is denied
    And I am returned to my passport

  Scenario: Admin reaches admin surfaces
    Given I am signed in with the admin role
    When I open the challenge builder or reports
    Then access is granted

  Scenario: Direct API access is authorized by role
    Given I hold the student role
    When I call an admin-only API endpoint directly
    Then the request is rejected as unauthorized
```

---

## Feature UC-2 — Student views passport & progress
**Pri:** M · **Satisfies:** FR-C2, C3, C4, C5 · **Actor:** Student

The student sees their themed passport with weekly status, a progress countdown, and prize
eligibility — online or offline. Stories: US-5, US-6, US-7.

### US-5 — View passport & progress countdown
**Pri:** M · **Satisfies:** FR-C2, FR-C3

**Description.** The student sees all weeks/tasks as themed tiles with status (locked / available /
complete) and a progress countdown ("3 of 7 complete, 4 remaining").

**User story.** As an enrolled student, I want to see all my weeks with their status and a progress
countdown so that I know what I have done and what remains.

```gherkin
@FR-C2 @FR-C3 @source:UC-2
Feature: View passport and progress countdown

  Background:
    Given I am enrolled in a 7-week challenge

  Scenario: Passport shows week tiles with status
    When I open my passport
    Then I see themed tiles for all 7 weeks
    And each tile shows a status of "locked", "available", or "complete"
    And future weeks are shown as locked

  Scenario: Progress countdown reflects completion
    Given I have completed 3 of 7 weeks
    When I open my passport
    Then I see "3 of 7 complete, 4 remaining"

  Scenario: Countdown updates after a new completion
    Given I have completed 3 of 7 weeks
    When a new check-in marks a fourth week complete
    Then the countdown updates to "4 of 7 complete, 3 remaining"
```

### US-6 — Offline / installable PWA viewing
**Pri:** M · **Satisfies:** FR-C4

**Description.** The app is a mobile-first, installable PWA. Progress is viewable offline from the
last synced cache.

**User story.** As a student, I want to install the app and view my progress offline so that I can
check my passport even without a connection.

```gherkin
@FR-C4 @pwa @source:UC-2
Feature: Offline and installable PWA viewing

  Scenario: App is installable to the home screen
    Given I open the app in a mobile browser
    Then I am offered an "install to home screen" option
    And launching from the home screen opens the app full-screen

  Scenario: Offline shows last-synced progress
    Given I previously loaded my passport while online
    When I open the app with no network connection
    Then I see my last-synced weeks and progress from cache
    And I see an "offline" indicator

  Scenario: Actions requiring the network are disabled offline
    Given I am offline
    When I attempt to scan a QR to check in
    Then I am told the action requires a connection
    And no invalid check-in is queued as complete
```

### US-7 — Prize-eligibility indicator
**Pri:** S · **Satisfies:** FR-C5

**Description.** The passport shows prize-eligibility status derived from completion of all required
tasks (a query, not a stored flag).

**User story.** As a student, I want to see whether I am prize-eligible so that I know if I have met
the drawing requirements.

```gherkin
@FR-C5 @source:UC-2
Feature: Prize-eligibility indicator

  Scenario: Not yet eligible while required tasks remain
    Given the challenge has 4 required tasks
    And I have completed 2 of them
    When I open my passport
    Then the prize-eligibility indicator shows "not yet eligible"

  Scenario: Eligible once all required tasks are complete
    Given the challenge has 4 required tasks
    And I have completed all 4
    When I open my passport
    Then the prize-eligibility indicator shows "eligible"

  Scenario: Eligibility ignores non-required tasks
    Given all required tasks are complete
    And one optional task is incomplete
    Then the prize-eligibility indicator still shows "eligible"
```

---

## Feature UC-3 — Student checks in at an event via QR  *(core loop)*
**Pri:** M · **Satisfies:** FR-D1, D2, D4, D5, E1 · **Actor:** Student, Event Attendant

The core loop: a student scans the event QR to complete a week, with production anti-gaming via a
rotating signed token. Stories: US-8, US-9.

### US-8 — Student QR self-check-in
**Pri:** M · **Satisfies:** FR-D1, FR-D2, FR-D4, FR-E1

**Description.** A student scans the event QR in-app; the backend validates (task active, student
eligible, no duplicate, within date window) and records a check-in with `method = event_qr`; the
week flips to complete and the countdown updates. Every UC-3 exception is a scenario here.

**User story.** As an enrolled student, I want to scan the event QR to complete a week so that my
attendance is captured automatically without clickers or stickers.

```gherkin
@FR-D1 @FR-D2 @FR-D4 @source:UC-3
Feature: Student QR self-check-in

  Background:
    Given I am authenticated and enrolled in the active challenge
    And task "Week 3 - Vision Check" is active with a valid event QR

  Scenario: Successful check-in marks the week complete
    When I scan the event QR for "Week 3 - Vision Check"
    Then a check-in is recorded with method "event_qr" and a timestamp
    And "Week 3" flips to "complete"
    And my progress countdown decreases by one
    And I am shown a personalized tip for that task

  Scenario: Duplicate scan is rejected
    Given I already completed "Week 3 - Vision Check"
    When I scan the event QR again
    Then I see "Already completed this week"
    And no second check-in is recorded

  Scenario: Expired or invalid token is rejected
    When I scan a QR whose token is expired or invalid
    Then I see "This code is no longer valid, ask the attendant"
    And no check-in is recorded

  Scenario: Scan outside the task date window is rejected
    Given the current date is outside "Week 3"'s date window
    When I scan the event QR
    Then the check-in is rejected with a reason
    And no check-in is recorded

  Scenario: Ineligible student cannot check in
    Given I am not eligible for the active challenge
    When I scan the event QR
    Then the check-in is rejected
    And no check-in is recorded
```

### US-9 — Rotating signed QR token
**Pri:** C · **Satisfies:** FR-D5

**Description.** Production anti-gaming: the event QR is a signed, short-lived token that rotates
every ~30–60s on the staff screen, so a screenshot cannot be shared off-site.

**User story.** As Student Health Services, I want the event QR to be a rotating signed token so that
students cannot check in from off-site by sharing a screenshot.

```gherkin
@FR-D5 @security @source:UC-3
Feature: Rotating signed QR token

  Scenario: Fresh token is accepted
    Given the staff screen displays a signed token minted 10 seconds ago
    When a student scans it
    Then the signature validates and the check-in is recorded

  Scenario: Stale token is rejected
    Given a token that was valid but is now older than its rotation window
    When a student scans it
    Then the check-in is rejected as expired
    And the student is told to rescan the current code

  Scenario: Forged or tampered token is rejected
    When a student scans a token whose signature does not validate
    Then the check-in is rejected
    And the attempt is logged
```

---

## Feature UC-4 — Staff verifies a student directly  *(high-assurance option)*
**Pri:** S · **Satisfies:** FR-D3, D4 · **Actor:** Event Attendant

Story: US-10.

### US-10 — Staff-scans-student verification
**Pri:** S · **Satisfies:** FR-D3, FR-D4

**Description.** Higher-assurance option: an event attendant in staff mode scans the student's
personal passport QR and confirms the task; the check-in is recorded with `method = staff`.

**User story.** As an event attendant, I want to scan a student's passport QR so that I can verify
attendance at high-assurance events.

```gherkin
@FR-D3 @FR-D4 @source:UC-4
Feature: Staff-scans-student verification

  Background:
    Given I am signed in as an event attendant in staff mode

  Scenario: Attendant verifies a student for the active task
    When I scan a student's personal passport QR
    And I confirm the task "Week 5 - Lab Safety"
    Then a check-in is recorded for that student with method "staff"
    And the recording attendant is captured as verified_by

  Scenario: Attendant cannot verify a duplicate completion
    Given the student already completed "Week 5 - Lab Safety"
    When I scan their passport QR for that task
    Then I see "Already completed"
    And no second check-in is recorded
```

---

## Feature UC-5 — Admin builds/edits a challenge
**Pri:** M · **Satisfies:** FR-B1, B2, B3, B4, B6 · **Actor:** SHS Staff (Admin)

An admin authors a challenge as data/config: ordered weekly tasks, assessment items, theme, and the
option to duplicate a prior challenge. Stories: US-11, US-12, US-13, US-14.

### US-11 — Create / edit challenge with weekly tasks
**Pri:** M · **Satisfies:** FR-B1, FR-B2

**Description.** An admin creates a challenge (name, semester, start/end) and adds an ordered list of
weekly tasks, each with title, caption, activity type, location, date window, prize, and a required
flag. Challenge is data/config, never code.

**User story.** As an admin, I want to build a challenge with ordered weekly tasks so that I can set
up each semester without engineering help.

```gherkin
@FR-B1 @FR-B2 @source:UC-5
Feature: Create and edit challenge with weekly tasks

  Background:
    Given I am signed in as an admin

  Scenario: Create a challenge with core attributes
    When I create a challenge with name, semester, and start/end dates
    Then the challenge is saved in draft status for my campus

  Scenario: Add ordered weekly tasks
    Given a draft challenge
    When I add tasks with title, caption, activity type, location, date window, prize, and required flag
    Then the tasks are saved in the order I set
    And each task retains all of its attributes

  Scenario: Reorder tasks
    Given a challenge with tasks in weeks 1 through 7
    When I move week 5 before week 3
    Then the task order updates accordingly
    And students see the new order

  Scenario: Publish a challenge
    Given a complete draft challenge
    When I publish it
    Then eligible students on my campus can enroll
```

### US-12 — Attach assessment items with outcome tags
**Pri:** S · **Satisfies:** FR-B3

**Description.** An admin attaches assessment items (MCQ and/or reflection) to a task, each tagged to
a learning outcome for later aggregate reporting.

**User story.** As an admin, I want to attach quiz items tagged to learning outcomes so that I can
measure knowledge gains per outcome.

```gherkin
@FR-B3 @source:UC-5
Feature: Attach assessment items with outcome tags

  Background:
    Given I am editing a task in a draft challenge

  Scenario: Attach an MCQ with an answer key and outcome tag
    When I add an MCQ with a prompt, options, an answer key, and a learning-outcome tag
    Then the MCQ is saved against the task
    And it is linked to that learning-outcome tag

  Scenario: Attach a reflection with a rubric and outcome tag
    When I add a reflection item with a prompt, a rubric, and a learning-outcome tag
    Then the reflection is saved against the task
    And it is linked to that learning-outcome tag
```

### US-13 — Theme selection / re-skin
**Pri:** S · **Satisfies:** FR-B4

**Description.** An admin selects or edits a theme (palette, logo, hero art, copy tone) applied to
the student app. Re-skinning is a config change, not a code change (NFR-6).

**User story.** As an admin, I want to pick and adjust a theme so that each semester's challenge is
re-skinned without engineering effort.

```gherkin
@FR-B4 @NFR-6 @source:UC-5
Feature: Theme selection and re-skin

  Background:
    Given I am editing a challenge as an admin

  Scenario: Apply a theme to the student app
    When I select the "Stranger Things" theme
    Then the student app renders with that palette, logo, hero art, and copy tone

  Scenario: Re-skin without a code change
    Given a published challenge using the "Stranger Things" theme
    When I switch it to the "Harry Potter" theme
    Then the student app re-skins from configuration alone
    And no code deployment is required

  Scenario: Edit theme attributes
    When I adjust the palette or copy tone of the current theme
    Then the student app reflects the edited theme
```

### US-14 — Duplicate prior challenge
**Pri:** C · **Satisfies:** FR-B6

**Description.** An admin duplicates a prior challenge as a starting point for a new one.

**User story.** As an admin, I want to duplicate last semester's challenge so that I can start from a
known-good template instead of a blank page.

```gherkin
@FR-B6 @source:UC-5
Feature: Duplicate prior challenge

  Scenario: Duplicate creates an editable draft
    Given a prior challenge "Fall 2025 - Stranger Things"
    When I duplicate it
    Then a new draft challenge is created with the same tasks, quiz items, and theme
    And the copy is independent of the original

  Scenario: Editing the copy does not affect the original
    Given a duplicated draft challenge
    When I change a task in the copy
    Then the original challenge is unchanged
```

---

## Feature UC-6 — Student receives personalized health education
**Pri:** M · **Satisfies:** FR-E1, E6 · **Actor:** Student, AI Wellness Guide

Story: US-15.

### US-15 — Post-check-in personalized tip
**Pri:** M · **Satisfies:** FR-E1, FR-E6

**Description.** On a successful check-in (or opening a week), the student receives a personalized
tip/resource grounded in SHS-approved content, tailored by task, remaining progress, and interests.
All model calls are server-side; no PHI is sent.

**User story.** As a student, I want a personalized tip after each check-in so that I get relevant,
accurate health education tied to what I just did.

```gherkin
@FR-E1 @FR-E6 @ai @privacy @source:UC-6
Feature: Post-check-in personalized tip

  Scenario: Tip is shown after a check-in
    Given I just checked in to "Week 3 - Vision Check"
    When the completion is recorded
    Then I see a tip grounded in SHS content relevant to vision health
    And a resource or short video and a next step are shown

  Scenario: Tip is personalized by progress
    Given I have one required task remaining
    When I receive a post-check-in tip
    Then the tip acknowledges my remaining progress

  Scenario: Model calls are server-side with no PHI
    When a personalized tip is generated
    Then the model is called server-side through Bedrock
    And no PHI is included in the request
```

---

## Feature UC-7 — Student consults the AI wellness guide
**Pri:** M · **Satisfies:** FR-E2, E3, E6, NFR-8 · **Actor:** Student, AI Wellness Guide

A themed, grounded assistant with non-negotiable safety guardrails and crisis routing. Stories:
US-16, US-17.

### US-16 — Conversational wellness guide
**Pri:** M · **Satisfies:** FR-E2, FR-E6

**Description.** A themed in-app assistant answers wellness questions grounded in SHS content, nudges
the next task, and links campus resources. (Safety guardrails are US-17.)

**User story.** As a student, I want to chat with a themed wellness guide so that I can ask questions
and get grounded answers and next steps.

```gherkin
@FR-E2 @FR-E6 @ai @source:UC-7
Feature: Conversational wellness guide

  Scenario: Guide answers a wellness question from grounded content
    Given I open the themed wellness guide chat
    When I ask a wellness question within the SHS content scope
    Then the guide answers from grounded SHS content
    And it nudges my next task and links a campus resource

  Scenario: Guide is skinned to the active theme
    Given the active challenge uses the "Stranger Things" theme
    When I open the guide
    Then it presents with the theme's name and persona

  Scenario: Conversations are minimally logged with no PHI
    When I chat with the guide
    Then the conversation is minimally logged for improvement
    And no PHI is collected or stored
```

### US-17 — Guide guardrails + crisis routing
**Pri:** M · **Satisfies:** FR-E3, NFR-8

**Description.** A cross-cutting safety story: the guide is educational only (no diagnosis or
treatment), refuses out-of-scope requests, and hard-codes crisis routing to real resources on any
self-harm/urgent signal — never left to model discretion.

**User story.** As Student Health Services, I want the guide to refuse out-of-scope requests and
escalate crises so that students are protected and no medical advice is given.

```gherkin
@FR-E3 @NFR-8 @ai-safety @source:UC-7
Feature: Wellness guide guardrails and crisis routing

  Scenario: Out-of-scope medical request is declined
    Given I am chatting with the wellness guide
    When I ask for a diagnosis or medication dosage
    Then the guide declines to give medical advice
    And it redirects me to SHS or a clinician

  Scenario: Crisis signal triggers immediate escalation
    Given I am chatting with the wellness guide
    When my message contains a self-harm or urgent-crisis signal
    Then crisis resources (988 and campus counseling) are surfaced immediately
    And the SHS front-desk contact is shown
    And the response is hard-coded, not left to model discretion

  Scenario: Responses stay grounded and refuse to invent
    When I ask a question outside the SHS content corpus
    Then the guide deflects rather than fabricating an answer
```

---

## Feature UC-8 — Student completes an assessment
**Pri:** S · **Satisfies:** FR-E4, E5 · **Actor:** Student, AI Wellness Guide

Auto-scored knowledge checks and AI-scored reflections, with human override. Stories: US-18, US-19.

### US-18 — MCQ auto-scoring
**Pri:** S · **Satisfies:** FR-E4

**Description.** Multiple-choice knowledge checks are auto-scored instantly against the answer key,
and the score is stored against the learning-outcome tag.

**User story.** As a student, I want my MCQ knowledge check scored instantly so that I get immediate
feedback.

```gherkin
@FR-E4 @source:UC-8
Feature: MCQ auto-scoring

  Scenario: Correct answer is scored instantly
    Given an MCQ with a defined answer key
    When I submit the correct option
    Then I see an instant correct result
    And the score is stored against the learning-outcome tag

  Scenario: Incorrect answer is scored instantly with feedback
    When I submit an incorrect option
    Then I see an instant incorrect result
    And the score is stored against the learning-outcome tag
```

### US-19 — AI reflection scoring + human override
**Pri:** S · **Satisfies:** FR-E5

**Description.** Free-text reflections are scored by Claude against a per-item rubric mapped to a
learning-outcome tag, producing a score plus short feedback. An admin can override the AI score
(`scored_by = human`).

**User story.** As a student, I want my written reflection scored against a rubric with feedback so
that I learn from it; and as an admin, I want to override a score when needed.

```gherkin
@FR-E5 @ai @source:UC-8
Feature: AI reflection scoring with human override

  Scenario: Reflection is AI-scored against a rubric
    Given a reflection item with a rubric and a learning-outcome tag
    When I submit a free-text reflection
    Then it is scored against the rubric with short feedback
    And the response is stored with scored_by "auto"

  Scenario: Admin overrides an AI score
    Given an AI-scored reflection
    When an admin adjusts the score
    Then the stored score updates
    And scored_by is set to "human"
```

---

## Feature UC-9 — Admin AI-imports a challenge from a document  *(sleeper feature)*
**Pri:** S · **Satisfies:** FR-B5 · **Actor:** SHS Staff (Admin), AI Wellness Guide

Story: US-20.

### US-20 — AI document import to draft challenge
**Pri:** S · **Satisfies:** FR-B5

**Description.** An admin uploads a source Word/PDF (e.g. `Stranger Things Challenge.docx`) and
Claude drafts structured weeks, tasks, date windows, prizes, themed captions, and starter quiz items,
which the admin reviews and edits before publishing.

**User story.** As an admin, I want to upload my challenge document and have it drafted into a
structured challenge so that setup takes minutes instead of days.

```gherkin
@FR-B5 @ai @source:UC-9
Feature: AI document import to draft challenge

  Background:
    Given I am signed in as an admin

  Scenario: Uploaded document is drafted into an editable challenge
    When I upload "Stranger Things Challenge.docx"
    Then the system drafts ordered weeks with titles, captions, date windows, and prizes
    And starter quiz items are drafted with learning-outcome tags
    And the draft is editable and unpublished until I confirm

  Scenario: Admin edits before publishing
    Given a drafted challenge from an imported document
    When I edit a task caption and publish
    Then students see only the published, edited version

  Scenario: Unsupported or unreadable file is handled gracefully
    When I upload a file the system cannot parse
    Then I see a clear error
    And no partial or corrupt draft is created
```

---

## Feature UC-10 — Admin runs reports & exports prize list
**Pri:** M · **Satisfies:** FR-F1, F2, F3, F4, F5, F6 · **Actor:** SHS Staff (Admin), Reporting Consumer

Participation, attendance-method, engagement, and learning-outcome reporting, plus the prize-eligible
export — all privacy-aware. Stories: US-21, US-22, US-23, US-24, US-25, US-26.

### US-21 — Participation & completion funnel report
**Pri:** M · **Satisfies:** FR-F1

**Description.** Admins view participation and a per-week completion funnel showing how many students
completed each week.

**User story.** As an admin, I want a participation and per-week completion funnel so that I can see
where students drop off.

```gherkin
@FR-F1 @source:UC-10
Feature: Participation and completion funnel report

  Background:
    Given I am signed in as an admin viewing the active challenge

  Scenario: Report shows enrollment and per-week completion
    When I open the participation report
    Then I see total enrollments
    And I see the count of students completing each week
    And the weeks are shown as a funnel

  Scenario: Report reflects new check-ins
    Given a new check-in is recorded for week 4
    When I refresh the report
    Then week 4's completion count increases by one
```

### US-22 — Auto-vs-manual attendance report
**Pri:** S · **Satisfies:** FR-F2

**Description.** A report breaks down attendance by capture method (event_qr / staff vs. manual) so
SHS can show how much attendance is captured automatically.

**User story.** As an admin, I want to see auto vs. manual attendance counts so that I can quantify
the effort the system saves.

```gherkin
@FR-F2 @source:UC-10
Feature: Auto-vs-manual attendance report

  Scenario: Attendance is broken down by method
    When I open the attendance report
    Then I see counts grouped by method: event_qr, staff, and manual
    And the totals reconcile with total check-ins

  Scenario: Auto share is highlighted
    Given most check-ins used event_qr
    When I view the report
    Then the automatically-captured share is shown as a percentage
```

### US-23 — Engagement report
**Pri:** S · **Satisfies:** FR-F3

**Description.** A report shows engagement metrics: content views and wellness-guide usage.

**User story.** As an admin, I want engagement metrics so that I can see how much students use the
content and the guide.

```gherkin
@FR-F3 @source:UC-10
Feature: Engagement report

  Scenario: Report shows content views and guide usage
    When I open the engagement report
    Then I see counts of content views
    And I see counts of guide chat sessions
    And both can be viewed per challenge
```

### US-24 — Learning-outcome aggregate report
**Pri:** S · **Satisfies:** FR-F4

**Description.** Assessment scores are aggregated by learning-outcome tag, replacing the hand-scoring
Lauren does today.

**User story.** As an admin, I want aggregated scores by learning outcome so that I can report
knowledge gains without hand-scoring.

```gherkin
@FR-F4 @source:UC-10
Feature: Learning-outcome aggregate report

  Scenario: Scores aggregate by outcome tag
    Given quiz responses scored against learning-outcome tags
    When I open the learning-outcome report
    Then I see aggregated scores grouped by outcome tag

  Scenario: Human-overridden scores are included
    Given some reflections were overridden with scored_by "human"
    When I view the aggregate
    Then the overridden scores are reflected in the totals
```

### US-25 — Reporting privacy / aggregation
**Pri:** C · **Satisfies:** FR-F6, NFR-1

**Description.** Reports are aggregated and privacy-aware (FERPA), optionally surfaced in QuickSight,
never exposing PHI.

**User story.** As Student Health Services, I want reports to be privacy-aware and aggregated so that
we honor FERPA and never expose PHI.

```gherkin
@FR-F6 @NFR-1 @privacy @source:UC-10
Feature: Reporting privacy and aggregation

  Scenario: Reports never contain PHI
    When I open any report
    Then no PHI is present in the data
    And participation records are access-controlled

  Scenario: Small aggregates respect privacy
    Given a report grouping with very few students
    When it is displayed
    Then it is presented in a privacy-aware manner
```

### US-26 — Prize-eligible CSV export
**Pri:** M · **Satisfies:** FR-F5

**Description.** Admins export the list of prize-eligible students (those who completed all required
tasks) to CSV for the drawing. Eligibility is derived, so the export is always correct.

**User story.** As an admin, I want to export prize-eligible students to CSV so that I can run the
drawing.

```gherkin
@FR-F5 @source:UC-10
Feature: Prize-eligible CSV export

  Scenario: Export contains only prize-eligible students
    Given several students, some with all required tasks complete
    When I export the prize-eligible list
    Then the CSV contains only students who completed every required task
    And students missing any required task are excluded

  Scenario: Export reflects derived eligibility
    Given a student just completed their final required task
    When I re-export the list
    Then that student now appears in the CSV
```

---

## Feature UC-11 — Admin manages a live event
**Pri:** S · **Satisfies:** FR-D4, D6 · **Actor:** SHS Staff (Admin), Event Attendant

An admin runs an event: generate the QR, watch real-time counts, and manually correct completions
with an audit trail. Stories: US-27, US-28.

### US-27 — Manual completion override + audit
**Pri:** S · **Satisfies:** FR-D6

**Description.** An admin can manually add or override a completion, always writing an audit trail
(who, when, why) with `method = manual`.

**User story.** As an admin, I want to manually mark or correct a completion so that I can handle
edge cases, with every change recorded for audit.

```gherkin
@FR-D6 @audit @source:UC-11
Feature: Manual completion override with audit

  Background:
    Given I am signed in as an admin

  Scenario: Admin manually marks a completion
    When I manually mark a student complete for "Week 2 - Nutrition"
    Then a check-in is recorded with method "manual"
    And the audit trail records my identity, the timestamp, and a reason

  Scenario: Admin overrides an existing completion
    Given a student has an erroneous completion for "Week 2 - Nutrition"
    When I remove or correct it
    Then the change is recorded in the audit trail
    And the prior state is preserved for audit
```

### US-28 — Live event dashboard
**Pri:** S · **Satisfies:** FR-D4

**Description.** During an event, an admin generates the event QR and watches real-time check-in
counts.

**User story.** As an admin running an event, I want a live check-in count so that I can monitor
attendance as it happens.

```gherkin
@FR-D4 @source:UC-11
Feature: Live event dashboard

  Background:
    Given I am signed in as an admin running "Week 3 - Vision Check"

  Scenario: Generate the event QR
    When I open live ops for the task
    Then an event QR is generated for students to scan

  Scenario: Live count updates as students check in
    Given the live dashboard is open
    When students scan and check in
    Then the real-time check-in count increases accordingly
```

---

## Feature UC-12 — Deploy to another CSU campus  *(stretch)*
**Pri:** C · **Satisfies:** FR-A5, NFR-4 · **Actor:** ITS

Story: US-29.

### US-29 — Campus IdP registration & tenancy
**Pri:** C · **Satisfies:** FR-A5, NFR-4

**Description.** ITS registers a campus IdP (SAML), sets the `campus_id` mapping, and deploys the same
codebase; every record is scoped by `campus_id` so campuses are isolated and each authors its own
challenges without code changes.

**User story.** As ITS, I want to onboard a new CSU campus by registering its IdP and mapping so that
the same codebase serves that campus with isolated data.

```gherkin
@FR-A5 @NFR-4 @multi-tenant @source:UC-12
Feature: Campus IdP registration and tenancy

  Scenario: Register a new campus IdP
    Given I am ITS onboarding a new campus
    When I register the campus SAML issuer and set its campus_id mapping
    Then students from that campus can authenticate
    And no code change is required

  Scenario: Data is isolated by campus
    Given challenges and check-ins exist for campus A and campus B
    When a campus A admin views challenges
    Then only campus A records are visible

  Scenario: Each campus authors its own challenges
    Given two onboarded campuses
    When each campus authors a challenge
    Then the challenges are independent and scoped to their campus_id
```

---

## Traceability summary

**Feature (use case) → stories → requirements.** Every functional requirement is covered by at least
one story.

| Feature (UC) | Stories | Requirements |
|---|---|---|
| UC-1 Auth & enroll | US-1, US-2, US-3, US-4 | FR-A1, A2, A3, A4, C1 |
| UC-2 View passport | US-5, US-6, US-7 | FR-C2, C3, C4, C5 |
| UC-3 QR check-in | US-8, US-9 | FR-D1, D2, D4, D5, E1 |
| UC-4 Staff verify | US-10 | FR-D3, D4 |
| UC-5 Build challenge | US-11, US-12, US-13, US-14 | FR-B1, B2, B3, B4, B6 |
| UC-6 Personalized education | US-15 | FR-E1, E6 |
| UC-7 Wellness guide | US-16, US-17 | FR-E2, E3, E6, NFR-8 |
| UC-8 Assessment | US-18, US-19 | FR-E4, E5 |
| UC-9 AI doc import | US-20 | FR-B5 |
| UC-10 Reporting/export | US-21, US-22, US-23, US-24, US-25, US-26 | FR-F1–F6, NFR-1 |
| UC-11 Live event | US-27, US-28 | FR-D4, D6 |
| UC-12 Multi-campus | US-29 | FR-A5, NFR-4 |
