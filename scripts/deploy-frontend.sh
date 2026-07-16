#!/usr/bin/env bash
#
# Re-deploy the built SPA to S3 + invalidate CloudFront (docs/cloudfront-deploy-guide.md
# step 7). Run after any frontend change. The one-time bucket/distribution/OAC/behaviour
# setup is done once in the Console per that guide; this just ships new bits.
#
# Usage (from the repo root):
#   scripts/deploy-frontend.sh <bucket> <distribution-id>
# or via env:
#   FRONTEND_BUCKET=shs-wellness-passport-frontend \
#   CLOUDFRONT_DISTRIBUTION_ID=E123ABC... \
#   scripts/deploy-frontend.sh
#
# Requires: awscli configured with credentials, and Node (for the build).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BUCKET="${1:-${FRONTEND_BUCKET:-}}"
DIST_ID="${2:-${CLOUDFRONT_DISTRIBUTION_ID:-}}"

if [[ -z "$BUCKET" || -z "$DIST_ID" ]]; then
  echo "usage: scripts/deploy-frontend.sh <s3-bucket> <cloudfront-distribution-id>" >&2
  echo "   or: set FRONTEND_BUCKET and CLOUDFRONT_DISTRIBUTION_ID in the environment" >&2
  exit 2
fi

echo "==> Building the SPA (tsc + vite -> PWA)"
( cd "$ROOT/frontend" && npm run build )

echo "==> Syncing frontend/dist -> s3://$BUCKET (deleting removed objects)"
aws s3 sync "$ROOT/frontend/dist" "s3://$BUCKET" --delete

echo "==> Invalidating CloudFront distribution $DIST_ID (/*)"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" \
  --query 'Invalidation.Id' --output text

echo "==> Done. New bits are live once the invalidation completes (usually <1 min)."
