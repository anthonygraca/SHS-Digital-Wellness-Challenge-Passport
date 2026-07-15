#!/usr/bin/env bash
# Start the deployment. Safe to run when it is already up.
#
# Costs money while running (~$0.02/hr for the t3.small). Run down.sh when you
# are not demoing.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

state="$(instance_state)"
say "Instance is: $state"

case "$state" in
  running) info "already running" ;;
  stopped)
    info "starting..."
    aws ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
    info "started"
    ;;
  missing) die "instance $INSTANCE_ID does not exist. Run provision.sh." ;;
  *) die "instance is '$state' — wait for it to settle, then retry." ;;
esac

# The Elastic IP survives a stop/start; a plain public IP does not. Re-associate
# defensively in case the address was ever detached.
if [[ -n "${ALLOCATION_ID:-}" ]]; then
  aws ec2 associate-address --instance-id "$INSTANCE_ID" \
    --allocation-id "$ALLOCATION_ID" >/dev/null 2>&1 || true
fi

host="$(app_host)"
say "Waiting for the app"
if wait_for_healthz "$host"; then
  say "Up:  http://${host}/"
  info "the systemd unit re-logs into ECR and brings compose up on boot,"
  info "so a stop/start needs nothing else from you."
else
  die "instance is running but the app never answered. Check: scripts/deploy/logs.sh"
fi
