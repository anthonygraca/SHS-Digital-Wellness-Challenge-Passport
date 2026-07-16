#!/usr/bin/env bash
#
# Re-deploy the built SPA to S3 + invalidate CloudFront. Run after any frontend change.
# The bucket, distribution, OAC and behaviours are provisioned by template.yaml (see
# docs/cloudfront-deploy-guide.md); this just ships new bits into them.
#
# Usage (from the repo root):
#   scripts/deploy-frontend.sh <bucket> <distribution-id>
# or via env:
#   FRONTEND_BUCKET=... CLOUDFRONT_DISTRIBUTION_ID=E123ABC... scripts/deploy-frontend.sh
#
# The bucket and distribution id are the FrontendBucket / DistributionId stack outputs:
#   aws cloudformation describe-stacks --stack-name shs-wellness-passport-backend \
#     --query "Stacks[0].Outputs" --output table
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

# Two passes, because the files cache differently.
#
# Hashed assets (assets/index-<hash>.js): the name changes on every build, so they can
# cache forever — immutable + a year. NO --delete: a browser holding an older index.html
# may still ask for an older asset, and deleting it would 404 that user mid-session.
# They are kilobytes; prune with an S3 lifecycle rule if they ever pile up.
echo "==> Syncing immutable hashed assets -> s3://$BUCKET/assets"
aws s3 sync "$ROOT/frontend/dist/assets" "s3://$BUCKET/assets" \
  --cache-control "public,max-age=31536000,immutable"

# Everything else keeps a fixed name across builds (index.html, sw.js, registerSW.js,
# manifest.webmanifest, workbox-*.js), so it must be re-checked, not cached hard.
# --delete here (assets excluded) removes files a build stopped emitting.
echo "==> Syncing entry files (must-revalidate) -> s3://$BUCKET"
aws s3 sync "$ROOT/frontend/dist" "s3://$BUCKET" \
  --exclude "assets/*" --delete \
  --cache-control "public,max-age=0,must-revalidate"

# Invalidate only the fixed-name entry points. The hashed assets never need it (a new
# build has new names), so this stays a handful of paths rather than a blanket /* that
# bills per-path beyond the free allotment and needlessly drops warm cache for assets.
echo "==> Invalidating CloudFront $DIST_ID (entry points only)"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths /index.html /sw.js /registerSW.js /manifest.webmanifest \
  --query 'Invalidation.Id' --output text

echo "==> Done. New bits are live once the invalidation completes (usually <1 min)."
