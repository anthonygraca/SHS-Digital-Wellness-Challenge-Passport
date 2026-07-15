#!/usr/bin/env bash
# Create the AWS infrastructure from nothing, and write .deploy-local/env.
#
# Run this once. Afterwards use release.sh / up.sh / down.sh / access.sh.
# To start over: destroy.sh, then this again.
#
# Creates: ECR repo, IAM role + instance profile, security group, Elastic IP,
# and one t3.small running the app. Everything is tagged wellness-passport.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REGION="${AWS_REGION:-us-west-2}"
export AWS_DEFAULT_REGION="$REGION"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\nerror: %s\n' "$*" >&2; exit 1; }

command -v aws >/dev/null    || die "aws cli not found"
command -v docker >/dev/null || die "docker not found"
aws sts get-caller-identity >/dev/null 2>&1 || die "not authenticated. Run: aws sso login"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
ECR_REPO="${REGISTRY}/wellness-passport"

say "Account ${ACCOUNT_ID} / region ${REGION}"

# ---- secrets ---------------------------------------------------------------
# Generated per-deployment. Without these the app runs on the dev defaults that
# are committed to this public repo, which makes every session cookie forgeable
# by anyone who has read config.py. This does not disable the mock IdP demo — it
# just means the demo form is the only way in, rather than one of two.
say "Generating deployment secrets"
JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
QR_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
info "generated (stored in .deploy-local/env, git-ignored)"

# ---- ECR -------------------------------------------------------------------
say "ECR repository"
aws ecr describe-repositories --repository-names wellness-passport >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name wellness-passport \
       --image-scanning-configuration scanOnPush=true >/dev/null
info "$ECR_REPO"

# ---- IAM -------------------------------------------------------------------
say "IAM role and instance profile"
if ! aws iam get-role --role-name wp-ec2-role >/dev/null 2>&1; then
  aws iam create-role --role-name wp-ec2-role \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  # ECR read to pull the image; SSM so we get a shell and run commands without
  # ever opening port 22.
  aws iam attach-role-policy --role-name wp-ec2-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
  aws iam attach-role-policy --role-name wp-ec2-role \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
fi
if ! aws iam get-instance-profile --instance-profile-name wp-ec2-profile >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name wp-ec2-profile >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name wp-ec2-profile --role-name wp-ec2-role
  info "waiting for the instance profile to propagate..."
  sleep 12
fi
info "wp-ec2-role / wp-ec2-profile"

# ---- network ---------------------------------------------------------------
say "Security group"
VPC_ID="$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
[[ "$VPC_ID" != "None" ]] || die "no default VPC in $REGION"
SG_ID="$(aws ec2 describe-security-groups --filters Name=group-name,Values=wp-sg Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)"
if [[ "$SG_ID" == "None" ]]; then
  SG_ID="$(aws ec2 create-security-group --group-name wp-sg \
    --description "Wellness Passport app" --vpc-id "$VPC_ID" --query GroupId --output text)"
  # Starts closed to everything but you. access.sh changes this deliberately.
  MYIP="$(curl -s --max-time 8 https://checkip.amazonaws.com | tr -d '[:space:]')"
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=${MYIP}/32,Description='operator only'}]" >/dev/null
fi
info "$SG_ID (no port 22 — shell is via SSM)"

# ---- instance --------------------------------------------------------------
say "EC2 instance"
AMI="$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value --output text)"

USER_DATA="$(mktemp)"
trap 'rm -f "$USER_DATA"' EXIT
cat > "$USER_DATA" <<EOF
#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/wp-bootstrap.log|logger -t wp-bootstrap -s 2>/dev/console) 2>&1

dnf update -y
dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/wellness-passport
cat > /opt/wellness-passport/docker-compose.yml <<'COMPOSE'
services:
  app:
    image: ${ECR_REPO}:latest
    restart: unless-stopped
    ports:
      - "80:8000"
    volumes:
      - wp-data:/data
    environment:
      # The mock IdP is intentional: it demonstrates the stakeholder use cases
      # without a real campus IdP. It grants app-admin to any visitor, which is
      # why real secrets are set below — so the demo form is the only way in and
      # cookies cannot simply be forged from the repo defaults.
      WP_AUTH_PROVIDER: "mock"
      WP_JWT_SECRET: "${JWT_SECRET}"
      WP_QR_SECRET: "${QR_SECRET}"
      WP_DATABASE_URL: "sqlite:////data/wellness_passport.db"
volumes:
  wp-data:
COMPOSE

aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${REGISTRY}
cd /opt/wellness-passport
docker compose up -d || true

# Bring the stack up on every boot. ECR credentials are short-lived, so the
# re-login in ExecStartPre is load-bearing after a stop/start.
cat > /etc/systemd/system/wellness-passport.service <<'UNIT'
[Unit]
Description=Wellness Passport
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/wellness-passport
ExecStartPre=/bin/bash -c 'aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${REGISTRY}'
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable wellness-passport.service
echo "BOOTSTRAP COMPLETE"
EOF

INSTANCE_ID="$(aws ec2 run-instances \
  --image-id "$AMI" --instance-type t3.small \
  --security-group-ids "$SG_ID" \
  --iam-instance-profile Name=wp-ec2-profile \
  --user-data "file://$USER_DATA" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=wellness-passport}]' \
  --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
  --query 'Instances[0].InstanceId' --output text)"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
info "$INSTANCE_ID"

# ---- elastic ip ------------------------------------------------------------
# A plain public IP is released every time the instance stops, so the URL would
# change on each up.sh and every link already shared would break. An Elastic IP
# is what makes "stop it when we are not demoing" compatible with "share a link".
say "Elastic IP"
ALLOCATION_ID="$(aws ec2 allocate-address --domain vpc \
  --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=wellness-passport}]' \
  --query AllocationId --output text)"
aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOCATION_ID" >/dev/null
APP_HOST="$(aws ec2 describe-addresses --allocation-ids "$ALLOCATION_ID" --query 'Addresses[0].PublicIp' --output text)"
info "$APP_HOST (stable across stop/start)"

# ---- record ----------------------------------------------------------------
mkdir -p "$REPO_ROOT/.deploy-local"
cat > "$REPO_ROOT/.deploy-local/env" <<EOF
# Written by scripts/deploy/provision.sh. Git-ignored: this repo is public and
# these values should not be in it.
export AWS_REGION=${REGION}
export AWS_ACCOUNT_ID=${ACCOUNT_ID}
export ECR_REPO=${ECR_REPO}
export INSTANCE_ID=${INSTANCE_ID}
export SECURITY_GROUP_ID=${SG_ID}
export ALLOCATION_ID=${ALLOCATION_ID}
export APP_HOST=${APP_HOST}
export WP_JWT_SECRET='${JWT_SECRET}'
export WP_QR_SECRET='${QR_SECRET}'
EOF
chmod 600 "$REPO_ROOT/.deploy-local/env"

say "Provisioned"
info "identifiers written to .deploy-local/env"
info ""
info "Next:"
info "  scripts/deploy/release.sh      build + push + roll out the current commit"
info "  scripts/deploy/access.sh public   let anyone reach it"
info "  scripts/deploy/status.sh       where it is and who can reach it"
