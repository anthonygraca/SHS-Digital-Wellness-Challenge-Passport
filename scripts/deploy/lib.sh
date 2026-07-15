#!/usr/bin/env bash
# Shared helpers for the deploy scripts. Sourced, not run.
#
# Real identifiers live in .deploy-local/env (git-ignored) because this repo is
# public. Copy .deploy-local/env.example and fill it in, or run `provision.sh`
# which writes it for you.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.deploy-local/env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE not found." >&2
  echo "       Run scripts/deploy/provision.sh first, or copy .deploy-local/env.example." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${AWS_REGION:?set in .deploy-local/env}"
: "${AWS_ACCOUNT_ID:?set in .deploy-local/env}"
: "${INSTANCE_ID:?set in .deploy-local/env}"

export AWS_DEFAULT_REGION="$AWS_REGION"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_REPO="${ECR_REGISTRY}/wellness-passport"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\nerror: %s\n' "$*" >&2; exit 1; }

instance_state() {
  aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "missing"
}

app_host() {
  # The Elastic IP is the stable address; fall back to whatever is attached.
  if [[ -n "${APP_HOST:-}" ]]; then
    echo "$APP_HOST"
  else
    aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
      --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
  fi
}

wait_for_healthz() {
  local host="$1" tries="${2:-60}"
  info "waiting for http://${host}/healthz ..."
  for ((i = 1; i <= tries; i++)); do
    if curl -sf --max-time 4 "http://${host}/healthz" >/dev/null 2>&1; then
      info "healthy after ~$((i * 5))s"
      return 0
    fi
    sleep 5
  done
  return 1
}

ecr_login() {
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null
}
