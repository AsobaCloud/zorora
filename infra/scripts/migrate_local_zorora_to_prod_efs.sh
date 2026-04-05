#!/usr/bin/env bash
# Upload local ~/.zorora to S3 and run a one-shot Fargate task that extracts it onto
# the production Regional (Multi-AZ) EFS volume (same FS + access point as ona-zorora-prod).
#
# Prerequisites: aws CLI, tar; credentials with ecs:RunTask, s3:PutObject, s3:GetObject (presign).
#
# Usage:
#   export AWS_REGION=af-south-1   # default af-south-1
#   ./migrate_local_zorora_to_prod_efs.sh [path-to-zorora-dir]
#
# Default source: $HOME/.zorora
#
# Important:
# - Data that lived only on pre-EFS Fargate disk is gone; this seeds from a directory you still have.
# - After success, delete the tarball from S3: aws s3 rm s3://BUCKET/KEY

set -euo pipefail

REGION="${AWS_REGION:-af-south-1}"
CLUSTER="${ZORORA_ECS_CLUSTER:-ona-zorora-prod}"
MIGRATE_FAMILY="${ZORORA_EFS_MIGRATE_FAMILY:-ona-zorora-prod-efs-migrate:1}"
BUCKET="${ZORORA_MIGRATE_BUCKET:-ona-zorora-prod-user-state-migrate}"
SUBNETS="${ZORORA_SERVICE_SUBNETS:-subnet-01f9e7a1edce50c78,subnet-0805996e37a517151,subnet-0960479847914f901}"
TASK_SG="${ZORORA_TASK_SG:-sg-0355a648eecb65f29}"

SRC="${1:-$HOME/.zorora}"
if [[ ! -d "$SRC" ]]; then
  echo "Source directory missing: $SRC" >&2
  exit 1
fi

aws s3 mb "s3://${BUCKET}" --region "$REGION" 2>/dev/null || true

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
KEY="seed/${STAMP}/zorora-home.tgz"
TMP="$(mktemp /tmp/zorora-home-migrate.XXXXXX.tgz)"
trap 'rm -f "$TMP"' EXIT

echo "==> Archiving $SRC -> $TMP"
tar czf "$TMP" -C "$SRC" .

echo "==> Upload s3://${BUCKET}/${KEY}"
aws s3 cp "$TMP" "s3://${BUCKET}/${KEY}" --region "$REGION"

echo "==> Presign (2h)"
export URL
URL="$(aws s3 presign "s3://${BUCKET}/${KEY}" --region "$REGION" --expires-in 7200)"

python3 -c "import json, os; json.dump(
  {'containerOverrides': [{'name': 'migrate', 'environment': [{'name': 'PRESIGNED_URL', 'value': os.environ['URL']}]}]},
  open('/tmp/zorora_migrate_override.json', 'w'))"

NET="subnets=[${SUBNETS}],securityGroups=[${TASK_SG}],assignPublicIp=ENABLED"

echo "==> Run migration task $MIGRATE_FAMILY"
TASK_ARN="$(aws ecs run-task --region "$REGION" --cluster "$CLUSTER" --launch-type FARGATE \
  --task-definition "$MIGRATE_FAMILY" \
  --network-configuration "awsvpcConfiguration={${NET}}" \
  --overrides file:///tmp/zorora_migrate_override.json \
  --query 'tasks[0].taskArn' --output text)"

echo "TASK_ARN=$TASK_ARN"

echo "==> Wait for STOPPED"
aws ecs wait tasks-stopped --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK_ARN"

EXIT="$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$TASK_ARN" \
  --query 'tasks[0].containers[0].exitCode' --output text)"
if [[ "$EXIT" != "0" ]]; then
  echo "Migration container exit code: $EXIT" >&2
  exit "$EXIT"
fi

echo "==> OK. Remove tarball when done:"
echo "    aws s3 rm s3://${BUCKET}/${KEY} --region $REGION"
