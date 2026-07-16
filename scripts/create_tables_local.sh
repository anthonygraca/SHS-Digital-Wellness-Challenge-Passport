#!/usr/bin/env bash
#
# Create the seven DynamoDB tables (with GSIs) against DynamoDB Local, matching
# template.yaml and app/repositories/dynamo_repo.py. Use this for offline testing
# with `sam local start-api` (docs/serverless-backend-guide.md §4).
#
# Prereqs: DynamoDB Local running, e.g.
#   docker run -d --name dynamodb-local -p 8000:8000 amazon/dynamodb-local
#
# Usage (from anywhere):
#   scripts/create_tables_local.sh                       # prefix wp-, http://localhost:8000
#   ENDPOINT=http://localhost:8000 PREFIX=wp- REGION=us-west-2 scripts/create_tables_local.sh
set -euo pipefail

ENDPOINT="${ENDPOINT:-http://localhost:8000}"
REGION="${REGION:-us-west-2}"
PREFIX="${PREFIX:-wp-}"

# DynamoDB Local ignores credentials but the CLI still needs some set.
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"

ddb() { aws dynamodb "$@" --endpoint-url "$ENDPOINT" --region "$REGION"; }

create() {  # create <TableSuffix> <extra create-table args...>
  local name="${PREFIX}$1"; shift
  if ddb describe-table --table-name "$name" >/dev/null 2>&1; then
    echo "==> $name already exists, skipping"
    return
  fi
  echo "==> creating $name"
  ddb create-table --table-name "$name" --billing-mode PAY_PER_REQUEST "$@" >/dev/null
}

create Students \
  --attribute-definitions AttributeName=student_id,AttributeType=S \
  --key-schema AttributeName=student_id,KeyType=HASH

create Challenges \
  --attribute-definitions \
    AttributeName=id,AttributeType=N \
    AttributeName=campus_id,AttributeType=S \
    AttributeName=created_at,AttributeType=S \
    AttributeName=pub_campus_id,AttributeType=S \
    AttributeName=published_sort,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=ByCampus,KeySchema=[{AttributeName=campus_id,KeyType=HASH},{AttributeName=created_at,KeyType=RANGE}],Projection={ProjectionType=ALL}' \
    'IndexName=PublishedByCampus,KeySchema=[{AttributeName=pub_campus_id,KeyType=HASH},{AttributeName=published_sort,KeyType=RANGE}],Projection={ProjectionType=ALL}'

create Tasks \
  --attribute-definitions \
    AttributeName=id,AttributeType=N \
    AttributeName=challenge_id,AttributeType=N \
    AttributeName=position,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=ByChallenge,KeySchema=[{AttributeName=challenge_id,KeyType=HASH},{AttributeName=position,KeyType=RANGE}],Projection={ProjectionType=ALL}'

create AssessmentItems \
  --attribute-definitions \
    AttributeName=id,AttributeType=N \
    AttributeName=task_id,AttributeType=N \
    AttributeName=challenge_id,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=ByTask,KeySchema=[{AttributeName=task_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    'IndexName=ByChallenge,KeySchema=[{AttributeName=challenge_id,KeyType=HASH}],Projection={ProjectionType=ALL}'

create Enrollments \
  --attribute-definitions \
    AttributeName=student_id,AttributeType=S \
    AttributeName=challenge_id,AttributeType=N \
  --key-schema \
    AttributeName=student_id,KeyType=HASH \
    AttributeName=challenge_id,KeyType=RANGE

create CheckIns \
  --attribute-definitions \
    AttributeName=student_id,AttributeType=S \
    AttributeName=task_id,AttributeType=N \
  --key-schema \
    AttributeName=student_id,KeyType=HASH \
    AttributeName=task_id,KeyType=RANGE

create Counters \
  --attribute-definitions AttributeName=name,AttributeType=S \
  --key-schema AttributeName=name,KeyType=HASH

echo "==> Done. Tables:"
ddb list-tables --query 'TableNames' --output text
