# Prompt: Material 3 front-end design for the SHS Digital Wellness Passport

Copy everything in the fenced block below into a new Claude session.

---

```
You are a senior product designer + front-end engineer. Design and build an interactive
Material 3 (Material You) front-end prototype for a mobile-first digital wellness passport.

## Context
This is a DxHub project for CSU Bakersfield Student Health Services (SHS). Students opt into
multi-week wellness challenges (7–8 weeks, e.g. a "Stranger Things" theme), check in at campus
health events by scanning a QR code, track their progress, get personalized health education and
a conversational AI wellness guide, and complete in-app assessments. Staff author challenges,
run events, and pull reports. Today it's all paper passports, sticker stamps, and clicker counts.

If you have access to the project repo, read these two files first — they are the source of truth
and this prompt is a summary of them:
  - requirements-and-use-cases.md   (actors, functional/non-functional requirements, 12 use cases)
  - architecture-plan.md            (system architecture, data model, AI layer, stack)

## What to build
A navigable, clickable front-end prototype covering BOTH surfaces:
  1. Student Mobile Responsive Website (primary, mobile-first)
  2. Admin Mobile Responsive Website (SHS staff)

Use realistic seed content from the real "Stranger Things" 7-week challenge:
  Wk1 Immunity Portal (flu shot / wellness kit) · Wk2 Vital Screenings (blood pressure) ·
  Wk3 Labs (glucose, cholesterol, HIV) · Wk4 Signal Distortion Check (vision) ·
  Wk5 Right-Side-Up Check-up (physical/STI) · Wk6 Calm the Chaos (Vinyl & Vibes / stress) ·
  Wk7 Escape the Lab (exercise) · then Final Portal medal ceremony. Grand prize: scooter + helmet.
  Themed voice, e.g. "Step through the first portal: survival starts with protection."

## Design system: Material 3 (non-negotiable)
- Full M3 token system: color roles (primary, secondary, tertiary, error, surface + surface
  container levels, on-* pairs), tonal palettes, state layers, elevation, and the M3 shape scale.
- M3 type scale (display / headline / title / body / label) and M3 components: top app bar,
  bottom navigation bar, FAB, filled/tonal/outlined/text buttons, cards, chips (assist/filter),
  lists, segmented buttons, dialogs, snackbars, filled/outlined text fields, linear & circular
  progress indicators, badges.
- Light AND dark themes, both fully styled. Respect prefers-color-scheme and a manual toggle.
- Accessibility: WCAG AA contrast, ≥48dp touch targets, visible focus, dynamic-type friendly,
  screen-reader labels, reduced-motion support.
- Tasteful M3 motion (state layers, container transforms, shared-axis nav transitions).

## Semester theming (a first-class feature — lean into M3 dynamic color)
The app must be re-skinnable per semester (Stranger Things → Harry Potter → …) as CONFIG, not code.
Model each theme as an M3 "source color" that generates the tonal palettes, plus a logo, hero
image, and copy tone. Ship at least TWO themes to prove it:
  - Stranger Things: dark, red/crimson source color, retro-80s feel.
  - Harry Potter (Marauder's Map): parchment/burgundy/gold source color, lighter feel.
Provide a theme switcher in the prototype so reviewers can flip between them live.

## Screens to design (map each to its use case)
Student PWA:
  - S1  Sign in with campus SSO (SAML) — no ID/password fields; single "Sign in with campus SSO"
        action. Then a "Join the [Theme] Challenge" enrollment screen.               [UC-1]
  - S2  Passport home: themed week tiles with status (locked / available / complete),
        a prominent progress countdown ("3 of 7 complete — 4 to go"), prize-eligibility badge. [UC-2]
  - S3  Week/task detail: caption, activity type, location, date window, prize, CTA to check in.
  - S4  QR scanner → check-in success animation → personalized health tip/resource card.  [UC-3, UC-6]
  - S5  AI Wellness Guide chat (themed persona, e.g. "Portal Guide"), grounded answers, next-step
        nudges, campus-resource links, and a visible crisis-resources affordance.        [UC-7]
  - S6  Assessment: MCQ knowledge check + free-text reflection, with results/feedback.    [UC-8]
  - S7  Completion / prize-eligibility celebration.
Admin PWA:
  - A1  Reporting dashboard: participation, per-week completion funnel, auto-vs-manual attendance,
        engagement, learning-outcome scores, "export prize list (CSV)".                  [UC-10]
  - A2  Challenge builder: list/reorder weeks & tasks; create/edit a challenge.           [UC-5]
  - A3  Task editor: title, caption, activity type, location, dates, prize, required flag, and
        attached MCQ/reflection items with a learning-outcome tag.
  - A4  Theme editor: pick source color / logo / hero / copy tone; live preview.          [FR-B4]
  - A5  AI document import: upload the challenge Word/PDF → AI-drafted weeks/tasks/captions/quizzes
        shown for review/edit.                                                           [UC-9]
  - A6  Live event: generate event QR, watch real-time check-in count, manual override.   [UC-11]

## Hard constraints (from requirements)
- Mobile-first, installable PWA; student flows must feel great one-handed on a phone.
- No PHI anywhere; identity is SSO-only (never show ID-number entry).
- AI guide is educational, NOT medical advice; include the no-diagnosis + crisis-routing affordance.
- Everything themeable is driven by design tokens, not hard-coded colors.

## Tech & deliverables
- Build a real, runnable prototype. Preferred: a single self-contained approach — either React with
  an M3-token implementation, or Material Web components, or hand-authored M3 tokens in CSS custom
  properties. Keep it self-contained (inline/bundled assets) so it can be opened and clicked through.
- Deliverables:
  1. The clickable prototype (both surfaces, navigable, two themes, light/dark).
  2. A documented M3 design-token set (JSON or CSS variables) per theme.
  3. A short component inventory + screen-to-use-case traceability note.
- Design tokens and theming architecture should make adding a third theme trivial.

## Process
Start by proposing the information architecture, navigation model (bottom nav items for the student
app; nav rail/drawer for admin), and the M3 token/theming strategy. Ask me any blocking questions,
then build. Prioritize the student core loop first: S1 → S2 → S3 → S4 → S6, then the AI guide (S5),
then the admin surfaces. Show your work incrementally.
```
