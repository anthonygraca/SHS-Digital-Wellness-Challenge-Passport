# Architecture & Implementation Plan
## SHS Digital Wellness Passport — CSUB Student Health Services (DxHub 2026)

> Mobile-first digital wellness passport with QR check-in, an AI wellness guide, personalized
> health education, and automated assessment/reporting. Standalone, SSO-based, themeable per
> semester, and built to deploy across the 22-campus CSU system.

---

## 1. Requirements distilled (from proposal + discovery call)

| # | Requirement | Source | Architectural consequence |
|---|---|---|---|
| R1 | Mobile-first; "phone is everywhere" | Erika/Nick | **PWA** (installable web app), not native |
| R2 | SAML SSO, no 9-digit ID self-entry; validate *current* student | Brian | Campus IdP via SAML; store only opaque SSO subject |
| R3 | No PHI; standalone; EHR does not integrate | Erika | No clinical data, no EHR calls; FERPA-aware only |
| R4 | QR check-in with manual oversight, "good faith" | Erika/Nick | Event-QR scan → mark week complete |
| R5 | Admin builder: configure N weeks/tasks/quizzes each semester | Erika/Nicholas | Challenge = **data/config**, not code |
| R6 | Re-skin per semester (Stranger Things → Harry Potter) | Nick/Erika | Theme = config (colors, art, copy) |
| R7 | Pull reports: participation, completion, learning outcomes | Lauren | Reporting store + dashboard/export |
| R8 | AI: personalization, conversational guide, auto-scoring | Proposal | Claude via Bedrock + RAG on SHS content |
| R9 | C# + Microsoft SQL Server for ongoing support | Brian | .NET target; Python only as fallback (rewrite risk) |
| R10 | AWS landing zone available; QuickSight in use | Dominique | Host on AWS; Bedrock for AI; QuickSight optional BI |
| R11 | ~200 completers; twice/year; deployable CSU-wide | Erika/Brian | Low steady load, burst at events; multi-tenant-ready |

**Scale reality:** ~200 concurrent-ish completers per challenge, 2 challenges/year, bursty at events.
This is a *small* system. Optimize for clarity, low ops burden, and a clean multi-campus story —
not for scale.

---

## 2. Recommended platform decisions

### 2.1 PWA over native app  ✅
A native iOS/Android app is overkill for a program that runs twice a year and needs zero app-store
friction for students. A **Progressive Web App** gives: install-to-home-screen, camera access for QR
scanning, push-capable, SSO in-browser, one codebase, instant updates. This is the pragmatic and
correct choice.

### 2.2 The QR check-in model  ✅
Two directions exist; support the simple one first, keep the strong one as a config option.

- **Event QR (default):** Staff display a QR at the event. Student scans it in-app → backend marks
  that week complete for the authenticated student. Captures attendance automatically (the metric
  Lauren wants) with near-zero staff effort.
  - *Anti-gaming for production:* make the QR a **signed, short-lived token that rotates every
    ~30–60s** on the staff screen, so a screenshot can't be shared off-site. Prototype can use a
    static per-event code.
- **Staff-scans-student (option):** For higher-assurance events (labs), staff scans the student's
  personal passport QR. Same endpoint, `method = staff_verified`.

Both funnel to one `POST /checkins` endpoint that records `{student, task, timestamp, method}`.
This directly replaces clickers + stickers and is the automatic attendance capture SHS asked for.

### 2.3 Challenge-as-config  ✅
A "challenge" (weeks, tasks, dates, prizes, quiz items, theme) is **data**, authored in the admin
builder — never code. Re-skinning and re-sequencing each semester is then a content operation, which
is exactly how Erika/Lauren already think ("I just put in 6 weeks, 8 weeks").

---

## 3. System architecture

```
                         ┌─────────────────────────────────────────────┐
                         │        Campus IdP (SAML)  — per CSU campus     │
                         └───────────────────────┬───────────────────────┘
                                                 │ SAML assertion (current-student attrs)
                                                 ▼
   ┌──────────────┐   HTTPS    ┌──────────────────────────────────────────────────┐
   │  Student PWA │──────────▶ │              ASP.NET Core API (C#)                 │
   │ (React/Blazor)│           │  Auth ·  Challenges ·  CheckIns ·  Assessment ·    │
   │  QR scanner   │◀──────────│  Reporting ·  AI orchestration                     │
   └──────────────┘           └───┬───────────────┬───────────────┬────────────────┘
                                  │               │               │
   ┌──────────────┐              ▼               ▼               ▼
   │  Admin PWA   │        ┌───────────┐   ┌────────────┐   ┌──────────────┐
   │ builder +    │───────▶│ MS SQL     │   │ Amazon      │   │  S3           │
   │ dashboard    │        │ Server(RDS)│   │ Bedrock     │   │ (media,       │
   └──────────────┘        │            │   │ (Claude)    │   │  content docs)│
                           └───────────┘   └─────┬──────┘   └──────┬────────┘
                                                 │ RAG            │
                                                 ▼                ▼
                                          ┌───────────────────────────────┐
                                          │  Vector index over SHS-approved │
                                          │  wellness content (OpenSearch / │
                                          │  pgvector / in-SQL)             │
                                          └───────────────────────────────┘

   Reporting/BI:  SQL  ──▶  QuickSight dashboards (participation, completion, outcomes)
```

**One API, two front-end surfaces** (student PWA, admin PWA) sharing an auth layer. Everything AI
routes through the API so guardrails, grounding, and logging are centralized — the model is never
called directly from the browser.

---

## 4. Tech stack

| Layer | Production choice | Why | Camp-prototype note |
|---|---|---|---|
| Front end | **React PWA** (or Blazor WASM) + `html5-qrcode`/`BarcodeDetector` | Mobile-first, installable, camera QR | Same; theme via CSS variables |
| API | **ASP.NET Core (C#)** Web API | R9 — team-supportable, CSU-standard | Build in .NET to match prod |
| DB | **Microsoft SQL Server** (Amazon RDS) | R9/R10 | SQLite/LocalDB fine for demo |
| Auth | **SAML** via campus IdP (`Sustainsys.Saml2` for .NET) | R2, CSU-wide | Mock IdP or single test SP for demo |
| AI | **Claude (Opus 4.8 / Sonnet 5) via Amazon Bedrock** | On AWS already; enterprise data controls | Same; keep prompts server-side |
| RAG | OpenSearch Serverless *or* pgvector *or* SQL-native vector | Ground guide + tips in SHS content | Start with a small in-memory/JSON index |
| Hosting | **AWS App Runner or ECS Fargate** + CloudFront | Simple container ops on their landing zone | App Runner is fastest to demo |
| Media/content | **S3** (`dxhub-camp-2026-csub-shs-digital-wellness`) + CloudFront | Already provisioned | Reuse existing bucket |
| Reporting | SQL views → **QuickSight** | Dominique already uses "Quick" | CSV export is enough for demo |
| Secrets | AWS Secrets Manager | No creds in code | — |

**Stack recommendation:** build the prototype **in .NET + SQL Server** even for the camp. The sponsor
(Brian) explicitly named C#/MS SQL as the condition for ongoing support and CSU-wide adoption, so a
.NET prototype *is* the adoption pitch — it demos the real production path, not a throwaway. A
Python/FastAPI prototype would ship marginally faster but carries an explicit rewrite cost Brian
flagged in the call ("our team is not trained on that… what does ongoing support mean"). Only fall
back to Python if the camp team has no C# capability at all.

---

## 5. Data model (no PHI)

```
Challenge(id, campus_id, name, theme_id, semester, starts_on, ends_on, status)
Theme(id, name, palette_json, logo_key, hero_key, copy_tone)          -- R6 skinning
Task(id, challenge_id, week_no, title, caption, activity_type,        -- R5 the "weeks"
     location, date_start, date_end, prize, is_required, order)
QuizItem(id, task_id, kind[mcq|reflection], prompt, options_json,     -- R8 assessment
         answer_key, rubric_json, learning_outcome_tag)

Student(id, campus_id, sso_subject, affiliation, created_at)          -- R2/R3 minimal identity
Enrollment(id, student_id, challenge_id, enrolled_at)

CheckIn(id, student_id, task_id, ts, method[event_qr|staff|manual],   -- R4 replaces sticker/clicker
        verified_by)
QuizResponse(id, student_id, quiz_item_id, response, score,           -- R8 auto-scored
             ai_feedback, scored_by[auto|human], ts)
ContentView(id, student_id, task_id, content_ref, ts)                 -- engagement metric
PrizeEligibility  -- DERIVED VIEW: student completed all is_required tasks in a challenge
```

**Identity:** the only identifier stored is the SAML `sso_subject` (e.g. eduPersonPrincipalName) plus
affiliation. No name-typing, no 9-digit ID, no PHI. Uniqueness is guaranteed by the IdP (solves
Erika's "two students, same name" concern).

**Prize eligibility is a query, not a flag** — derived from completion of required tasks, so it's
always correct and auditable.

---

## 6. The AI layer (the actual differentiator)

All three AI capabilities are grounded in **SHS-approved content** (RAG) and run server-side through
Bedrock. This is what makes it "AI value," not just digital tracking.

### 6.1 Personalized health education (post-check-in)
On each check-in, generate/select a tailored tip + resource + short video, personalized by: which
task, remaining progress, prior engagement, and any student-stated interests. Grounded in SHS
materials so content is on-brand and accurate. *Example from the call:* scan the vision-check QR →
"Get your eyes checked annually — here's why, and here's the campus follow-up."

### 6.2 Conversational wellness guide (themed chatbot)
An in-app assistant skinned to the theme ("Portal Guide" for Stranger Things, "Marauder's Map guide"
for Harry Potter) that answers wellness questions, nudges the next task, and points to campus
resources. **Guardrails (non-negotiable):**
- Educational, **not** medical advice; no diagnosis, no treatment recommendations.
- Answers grounded in retrieved SHS content; refuses/deflects out-of-scope.
- **Crisis routing:** any self-harm/urgent signal → immediate handoff to real services (988,
  campus counseling, SHS front desk) — hard-coded, not model-discretion.
- No PHI collected in chat; conversation minimally logged for improvement.

### 6.3 Automated assessment (replaces hand-scored paper)
- **MCQ knowledge checks:** auto-scored instantly.
- **Reflections:** Claude scores free-text against a per-item rubric mapped to a
  `learning_outcome_tag`, producing a score + short feedback. Aggregates into the learning-outcomes
  report Lauren scores by hand today. Human can override (`scored_by = human`).

### 6.4 AI-assisted admin builder (the sleeper feature)
Erika authors challenges as a Word doc today (we have the Stranger Things one). Let the admin **paste
or upload that doc → Claude drafts the structured challenge**: weeks, tasks, date windows, prizes,
themed captions/taglines, and starter quiz items — which the admin then edits. This maps directly to
their real workflow and turns a multi-day setup into minutes. Strong demo moment: ingest
`Stranger Things Challenge.docx` live and watch the challenge configure itself.

---

## 7. Admin experience

- **Builder:** create challenge → set weeks/tasks/dates/prizes → attach quiz items → pick/adjust
  theme. AI-assisted draft from source doc (§6.4).
- **Live ops:** generate event QR codes; view real-time check-in counts; manual override/mark.
- **Reporting (R7):** participation, check-in-vs-manual, completion funnel by week, engagement
  (content views/chat use), learning-outcome scores, prize-eligibility export. SQL views feeding
  QuickSight; CSV export for the registrar/prize drawing.

---

## 8. Privacy, safety & compliance

- **No PHI** stored or transmitted; challenge participation only (R3).
- **FERPA-aware:** participation is a student record — access-controlled, aggregated for reporting.
- **Minimal identity:** SSO subject + affiliation only; authorization can require
  "current student" attributes from the assertion (answers Lauren's past-student question).
- **AI safety:** grounding + refusal + crisis routing (§6.2); prompts and guardrails server-side;
  Bedrock keeps data within the AWS account (no training on your data).
- **Multi-campus/tenancy:** `campus_id` on every row; SAML issuer → campus mapping. Same codebase
  deploys per campus (Brian's CSU-wide path).

---

## 9. Build plan (camp week → Friday demo)

Prioritized so that each phase is independently demoable; stop wherever time runs out.

- **Phase 0 — Done.** Data pulled from S3 (passport, challenge doc, discovery call).
- **Phase 1 — Core loop (must-have).** SSO login → enroll → see weeks with progress countdown →
  scan event QR → week marked complete. Seed with the real **Stranger Things** 7-week challenge.
- **Phase 2 — AI value (the demo's heart).** Post-check-in personalized tip + themed conversational
  wellness guide (Bedrock/Claude + small RAG index of SHS content) with guardrails.
- **Phase 3 — Assessment.** MCQ knowledge check + AI-scored reflection feeding a learning-outcome
  number.
- **Phase 4 — Admin + reporting.** Builder with **AI doc-ingest** (live-configure from the Word
  doc), theming toggle, and a reporting view. This is the sponsor-facing "you'll actually use this"
  moment.
- **Stretch.** Rotating signed QR, QuickSight dashboard, second theme (Harry Potter) to prove
  re-skinning, push notifications for weekly nudges.

**Friday demo narrative:** log in as a student (SSO) → Stranger Things passport → scan a vision-check
QR → instant completion + personalized tip → ask the Portal Guide a question → take a knowledge
check → flip to admin → ingest the Word doc to build next semester's challenge → show the completion
& learning-outcome report.

---

## 10. Success metrics (instrumented from day one)

| Proposal metric | How the system measures it |
|---|---|
| Challenge completion rate | Enrollments vs. students completing all required tasks |
| Auto vs. hand attendance | `CheckIn.method` breakdown (event_qr/staff vs manual) |
| Engagement | ContentViews + chat sessions per student |
| Learning-outcome scores | Aggregated QuizResponse scores by `learning_outcome_tag` |
| Staff hours saved | Baseline (sticker/clicker/hand-scoring time) vs. near-zero after |
| Participant satisfaction | Optional end-of-challenge in-app survey |

---

## 11. Open questions to confirm with SHS / ITS

1. **Prototype stack:** confirm .NET (recommended) vs. Python for the camp build — capability check.
2. **QR assurance level:** static event code (simplest) vs. rotating signed token (anti-gaming)?
3. **SSO for the demo:** is a CSUB test IdP/SP available this week, or do we mock SAML for Friday?
4. **Bedrock access:** is Claude enabled in the account/region on the landing zone?
5. **Content for RAG:** which SHS wellness materials are cleared to ground the guide/tips?
6. **Crisis-routing resources:** exact campus counseling / SHS numbers to hard-code.
```
