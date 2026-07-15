#!/usr/bin/env bash
# Build the image, push it to ECR, and roll the running instance onto it.
#
# Run from the repo root on the commit you want to ship.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cd "$REPO_ROOT"

[[ "$(instance_state)" == "running" ]] || die "instance is not running. Run scripts/deploy/up.sh first."

SHA="$(git rev-parse --short HEAD)"
DIRTY=""
git diff --quiet && git diff --cached --quiet || DIRTY="-dirty"
TAG="${SHA}${DIRTY}"

say "Building wellness-passport:${TAG}"
docker build -t "wellness-passport:${TAG}" .

say "Pushing to ECR"
ecr_login
# Tag by SHA so a deployed version is traceable back to a commit, and move
# :latest to match so the instance's compose file needs no edit.
docker tag "wellness-passport:${TAG}" "${ECR_REPO}:${TAG}"
docker tag "wellness-passport:${TAG}" "${ECR_REPO}:latest"
docker push "${ECR_REPO}:${TAG}"
docker push "${ECR_REPO}:latest"

say "Rolling the instance"
cmd_id="$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "deploy ${TAG}" \
  --parameters 'commands=["cd /opt/wellness-passport","aws ecr get-login-password --region '"$AWS_REGION"' | docker login --username AWS --password-stdin '"$ECR_REGISTRY"'","docker compose pull","docker compose up -d","docker image prune -f"]' \
  --query 'Command.CommandId' --output text)"

for _ in $(seq 1 40); do
  status="$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)"
  [[ "$status" == "InProgress" || "$status" == "Pending" ]] || break
  sleep 3
done

if [[ "$status" != "Success" ]]; then
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$INSTANCE_ID" \
    --query '[Status,StandardErrorContent]' --output text
  die "rollout failed (status: $status)"
fi

host="$(app_host)"
say "Verifying"
wait_for_healthz "$host" 24 || die "deployed, but /healthz never answered. See scripts/deploy/logs.sh"

# The SPA is served by the same origin as the API. If the mount is missing, / returns
# JSON or a 404 instead of the app shell — catch that here rather than in a demo.
ctype="$(curl -s -o /dev/null -w '%{content_type}' --max-time 6 "http://${host}/")"
[[ "$ctype" == text/html* ]] || die "/ returned '${ctype}', not HTML — the SPA mount is missing from app/main.py"

say "Released ${TAG}  ->  http://${host}/"
