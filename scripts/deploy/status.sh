#!/usr/bin/env bash
# What is running, where, and who can reach it.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

state="$(instance_state)"
say "Instance"
info "id:     $INSTANCE_ID"
info "state:  $state"

if [[ "$state" == "running" ]]; then
  host="$(app_host)"
  info "url:    http://${host}/"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 6 "http://${host}/healthz" 2>/dev/null || echo "---")"
  info "health: ${code}"
fi

say "Who can reach it"
aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=${SECURITY_GROUP_ID}" \
  --query 'SecurityGroupRules[?IsEgress==`false`].{AllowedFrom:CidrIpv4,Port:FromPort,Note:Description}' \
  --output table

if aws ec2 describe-security-group-rules \
     --filters "Name=group-id,Values=${SECURITY_GROUP_ID}" \
     --query 'SecurityGroupRules[?IsEgress==`false`].CidrIpv4' --output text 2>/dev/null | grep -q '0.0.0.0/0'; then
  printf '  \033[33mPUBLIC — anyone on the internet can reach this.\033[0m\n'
  printf '  The mock IdP grants app-admin to any visitor, by design, for demos.\n'
  printf '  Restrict with: scripts/deploy/access.sh me\n'
fi

say "Cost"
if [[ "$state" == "running" ]]; then
  info "~\$0.02/hr for the t3.small, plus EBS and the Elastic IP."
  info "Not demoing? scripts/deploy/down.sh"
else
  info "compute is stopped; only EBS + the Elastic IP accrue (pennies/day)."
fi
