#!/usr/bin/env bash
# Tail the app's container logs without an SSH key, via SSM.
#
#   logs.sh          - last 100 lines
#   logs.sh 500      - last 500 lines
#   logs.sh boot     - the cloud-init bootstrap log (for a host that never came up)

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[[ "$(instance_state)" == "running" ]] || die "instance is not running."

arg="${1:-100}"
if [[ "$arg" == "boot" ]]; then
  remote='tail -n 200 /var/log/wp-bootstrap.log'
else
  remote="cd /opt/wellness-passport && docker compose logs --tail ${arg}"
fi

cmd_id="$(aws ssm send-command --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "commands=[\"$remote\"]" \
  --query 'Command.CommandId' --output text)"

for _ in $(seq 1 20); do
  status="$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$INSTANCE_ID" \
    --query 'Status' --output text 2>/dev/null || echo Pending)"
  [[ "$status" == "InProgress" || "$status" == "Pending" ]] || break
  sleep 2
done

aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$INSTANCE_ID" \
  --query '[StandardOutputContent,StandardErrorContent]' --output text

printf '\nFor an interactive shell instead:\n  aws ssm start-session --target %s --region %s\n' \
  "$INSTANCE_ID" "$AWS_REGION"
