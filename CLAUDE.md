# CLAUDE.md

Guidance for working in this repository.

## UI: mobile-first

The frontend UI is built for **mobile use**. Design, build, and review all UI for
mobile devices first.

- Assume a phone-sized viewport (~360–430px wide) is the primary target.
- Use responsive, fluid layouts (relative units, flexbox/grid); avoid fixed widths
  that overflow small screens.
- Touch targets should be at least 44×44px; spacing and typography must be legible
  on a phone.
- Test and verify changes at mobile widths before considering them done. Larger
  screens (tablet/desktop) are secondary and should scale up gracefully, not the
  other way around.

## Pull requests

When opening a pull request, **fully populate `.github/pull_request_template.md`
for that specific branch** — do not leave the placeholder text. Fill in every
section (Summary before/after, related issue, motivation, how it was implemented,
how to review, how to test) with content describing the actual changes on the
branch, and check off the checklist items that genuinely apply. Prefer
`gh pr create --body-file <path>` with the completed template as the body.

## This file

`CLAUDE.md` is committed to the repository (not git-ignored) so that this guidance
travels with every branch, including newly created ones. Keep it tracked.
