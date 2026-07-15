#!/usr/bin/env bash
# Delete everything this deployment created. NOT reversible — the database goes too.
#
# If you just want to stop paying while keeping the deployment, use down.sh instead.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

say "This will permanently delete:"
info "  EC2 instance      $INSTANCE_ID  (and its SQLite database)"
info "  Elastic IP        ${APP_HOST:-<none>}  (the shared URL stops working)"
info "  Security group    ${SECURITY_GROUP_ID:-<none>}"
info "  ECR repository    wellness-passport  (all image tags)"
info "  IAM role/profile  wp-ec2-role / wp-ec2-profile"
printf '\nType the word DESTROY to confirm: '
read -r confirm
[[ "$confirm" == "DESTROY" ]] || { echo "aborted."; exit 1; }

say "Terminating instance"
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null 2>&1 || true
aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" 2>/dev/null || true

if [[ -n "${ALLOCATION_ID:-}" ]]; then
  say "Releasing Elastic IP"
  aws ec2 release-address --allocation-id "$ALLOCATION_ID" 2>&1 | tail -1 || true
fi

if [[ -n "${SECURITY_GROUP_ID:-}" ]]; then
  say "Deleting security group"
  # The ENI can take a moment to detach after termination.
  for _ in $(seq 1 10); do
    aws ec2 delete-security-group --group-id "$SECURITY_GROUP_ID" 2>/dev/null && break
    sleep 6
  done
fi

say "Deleting ECR repository"
aws ecr delete-repository --repository-name wellness-passport --force 2>&1 | tail -1 || true

say "Deleting IAM role and instance profile"
aws iam remove-role-from-instance-profile --instance-profile-name wp-ec2-profile --role-name wp-ec2-role 2>/dev/null || true
aws iam delete-instance-profile --instance-profile-name wp-ec2-profile 2>/dev/null || true
aws iam detach-role-policy --role-name wp-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly 2>/dev/null || true
aws iam detach-role-policy --role-name wp-ec2-role --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore 2>/dev/null || true
aws iam delete-role --role-name wp-ec2-role 2>/dev/null || true

rm -f "$ENV_FILE"
say "Destroyed. .deploy-local/env removed; provision.sh will build it again from scratch."
