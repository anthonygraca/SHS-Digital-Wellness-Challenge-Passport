#!/usr/bin/env bash
# Enforce this repo's commit convention: every non-merge commit between the base
# ref and HEAD must reference an issue in its subject line, as "(#N)" or "[#N]".
# Usage: scripts/lint-commits.sh [base-ref]   (default: main)
set -euo pipefail

BASE="${1:-main}"

# Resolve the base to something git can diff against (prefer the remote ref in CI).
if git rev-parse --verify --quiet "origin/${BASE}" >/dev/null; then
  base_ref="origin/${BASE}"
elif git rev-parse --verify --quiet "${BASE}" >/dev/null; then
  base_ref="${BASE}"
else
  echo "lint-commits: base ref '${BASE}' not found" >&2
  exit 2
fi

range="${base_ref}..HEAD"
fail=0

while IFS= read -r line; do
  [ -z "$line" ] && continue
  short="${line%% *}"
  subject="${line#* }"
  if ! printf '%s' "$subject" | grep -Eq '\(#[0-9]+\)|\[#[0-9]+\]'; then
    echo "✗ ${short}  missing (#N) issue reference: ${subject}"
    fail=1
  fi
done < <(git log --no-merges --format='%h %s' "$range")

if [ "$fail" -eq 0 ]; then
  echo "✓ all commits in ${range} reference an issue (#N)"
fi
exit "$fail"
