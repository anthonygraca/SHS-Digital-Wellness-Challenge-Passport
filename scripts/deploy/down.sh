#!/usr/bin/env bash
# Stop the deployment to stop paying for it, WITHOUT destroying it.
#
# Stop vs terminate:
#   down.sh (stop)      - compute billing stops; the EBS disk and its SQLite
#                         database persist; the Elastic IP keeps the URL stable.
#                         up.sh brings it back in about a minute.
#   destroy.sh          - deletes everything, including the data. Not reversible.
#
# While stopped you still pay a few cents a month for the EBS volume, and ~$0.005/hr
# for the Elastic IP (AWS charges for an address reserved but not attached to a
# running instance). That is the price of the URL not changing.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

state="$(instance_state)"
say "Instance is: $state"

case "$state" in
  stopped) info "already stopped — nothing to do"; exit 0 ;;
  missing) die "instance $INSTANCE_ID does not exist." ;;
  running) ;;
  *) die "instance is '$state' — wait for it to settle, then retry." ;;
esac

info "stopping..."
aws ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null
aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"

say "Stopped. Compute billing has ceased."
info "The database is on the EBS volume and is untouched."
info "Bring it back with: scripts/deploy/up.sh"
