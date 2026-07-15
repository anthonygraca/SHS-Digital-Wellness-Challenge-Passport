#!/usr/bin/env bash
# Control who can reach the deployment.
#
#   access.sh public       - open tcp/80 to the whole internet (for sharing a demo)
#   access.sh me           - restrict to the IP you are running this from
#   access.sh ip 1.2.3.4   - restrict to a specific address
#
# Each mode REPLACES the existing ingress rules, so the security group always says
# exactly one thing about who can get in.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

: "${SECURITY_GROUP_ID:?set in .deploy-local/env}"

mode="${1:-}"

revoke_all_ingress() {
  local ids
  ids="$(aws ec2 describe-security-group-rules \
    --filters "Name=group-id,Values=${SECURITY_GROUP_ID}" \
    --query 'SecurityGroupRules[?IsEgress==`false`].SecurityGroupRuleId' --output text)"
  [[ -z "$ids" ]] && return 0
  # shellcheck disable=SC2086
  aws ec2 revoke-security-group-ingress --group-id "$SECURITY_GROUP_ID" \
    --security-group-rule-ids $ids >/dev/null
}

allow() {
  local cidr="$1" note="$2"
  aws ec2 authorize-security-group-ingress --group-id "$SECURITY_GROUP_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=${cidr},Description='${note}'}]" \
    >/dev/null
}

case "$mode" in
  public)
    say "Opening tcp/80 to 0.0.0.0/0"
    revoke_all_ingress
    allow "0.0.0.0/0" "public demo - mock IdP grants app-admin to any visitor by design"
    printf '\n  \033[33mThis is now reachable by anyone who finds the address.\033[0m\n'
    info "By design for a demo: the mock IdP hands app-admin to any visitor, which is"
    info "the stakeholder use case being shown. It is data, not the box — the app has"
    info "no shell, no file writes and no raw SQL, and the instance role is ECR-read + SSM."
    info "The realistic risk is someone editing your demo data before a walkthrough."
    info "Lock it back down with: scripts/deploy/access.sh me"
    ;;
  me)
    myip="$(curl -s --max-time 8 https://checkip.amazonaws.com | tr -d '[:space:]')"
    [[ -n "$myip" ]] || die "could not determine your public IP"
    say "Restricting tcp/80 to ${myip}/32"
    revoke_all_ingress
    allow "${myip}/32" "operator only"
    ;;
  ip)
    target="${2:-}"
    [[ -n "$target" ]] || die "usage: access.sh ip <address>"
    say "Restricting tcp/80 to ${target}/32"
    revoke_all_ingress
    allow "${target}/32" "single address"
    ;;
  *)
    die "usage: access.sh [public|me|ip <address>]"
    ;;
esac

say "Ingress is now"
aws ec2 describe-security-group-rules \
  --filters "Name=group-id,Values=${SECURITY_GROUP_ID}" \
  --query 'SecurityGroupRules[?IsEgress==`false`].{AllowedFrom:CidrIpv4,Port:FromPort,Note:Description}' \
  --output table
