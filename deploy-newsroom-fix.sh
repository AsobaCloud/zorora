#!/usr/bin/env bash
# deploy-newsroom-fix.sh - Deploy Zorora with newsroom S3 fix
# Automates build, push, and ECS deployment

set -euo pipefail

AWS_REGION="af-south-1"
AWS_ACCOUNT_ID="905418405543"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
APP_NAME="ona-zorora"
CLUSTER_NAME="${APP_NAME}-prod"
SERVICE_NAME="${APP_NAME}-prod"
TASK_FAMILY="${APP_NAME}-prod"

echo "=== Zorora Newsroom Fix Deployment ==="
echo "Region: ${AWS_REGION}"
echo ""

# Get commit hash
COMMIT=$(git rev-parse --short HEAD)
IMAGE_TAG="prod-${COMMIT}"
IMAGE_URI="${ECR_REGISTRY}/${APP_NAME}:${IMAGE_TAG}"

echo "Commit: ${COMMIT}"
echo "Image: ${IMAGE_URI}"
echo ""

# Step 1: Build Docker image
echo "Step 1: Building Docker image (ARM64 for Fargate Graviton)..."
docker build -t ona-zorora:latest .
docker tag ona-zorora:latest "${IMAGE_URI}"
echo "✓ Image built"
echo ""

# Step 2: Push to ECR
echo "Step 2: Pushing to ECR..."
echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
    docker login --username AWS --password-stdin "${ECR_REGISTRY}"
docker push "${IMAGE_URI}"
echo "✓ Image pushed"
echo ""

# Step 3: Update task definition file with new image
TASK_DEF_FILE="task-def-23.json"
echo "Step 3: Updating task definition..."

# Get execution role ARN
EXECUTION_ROLE_ARN=$(aws iam get-role \
    --role-name "${APP_NAME}-task-execution-role" \
    --query 'Role.Arn' --output text 2>/dev/null || echo "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${APP_NAME}-task-execution-role")

TASK_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/ona-zorora-task-role"

cat > "${TASK_DEF_FILE}" <<EOF
{
  "family": "${TASK_FAMILY}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "networkMode": "awsvpc",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}",
      "image": "${IMAGE_URI}",
      "cpu": 0,
      "portMappings": [
        {
          "containerPort": 5000,
          "hostPort": 5000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        { "name": "FRED_API_KEY", "value": "" },
        { "name": "HF_TOKEN", "value": "" },
        { "name": "BRAVE_SEARCH_API_KEY", "value": "" },
        { "name": "OPENAI_API_KEY", "value": "" },
        { "name": "CONGRESS_GOV_API_KEY", "value": "" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${TASK_FAMILY}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "zorora"
        }
      }
    }
  ],
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "runtimePlatform": {
    "cpuArchitecture": "ARM64",
    "operatingSystemFamily": "LINUX"
  }
}
EOF

echo "✓ Task definition updated: ${TASK_DEF_FILE}"
echo ""

# Step 4: Register task definition
echo "Step 4: Registering task definition..."
REVISION=$(aws ecs register-task-definition \
    --cli-input-json "file://${TASK_DEF_FILE}" \
    --region "${AWS_REGION}" \
    --query 'taskDefinition.revision' \
    --output text)
echo "✓ Task definition registered: revision ${REVISION}"
echo ""

# Step 5: Update ECS service
echo "Step 5: Updating ECS service..."
aws ecs update-service \
    --cluster "${CLUSTER_NAME}" \
    --service "${SERVICE_NAME}" \
    --task-definition "${TASK_FAMILY}:${REVISION}" \
    --force-new-deployment \
    --region "${AWS_REGION}" \
    >/dev/null

echo "✓ ECS service updated"
echo ""

# Step 6: Wait for deployment
echo "Step 6: Waiting for deployment to complete..."
echo "(This may take 2-3 minutes)"
echo ""

# Wait for service to stabilize
aws ecs wait services-stable \
    --cluster "${CLUSTER_NAME}" \
    --services "${SERVICE_NAME}" \
    --region "${AWS_REGION}"

echo "✓ Deployment complete!"
echo ""

# Step 7: Verify
echo "Step 7: Verification"
echo "Service status:"
aws ecs describe-services \
    --cluster "${CLUSTER_NAME}" \
    --services "${SERVICE_NAME}" \
    --region "${AWS_REGION}" \
    --query 'services[0].{running:runningCount, pending:pendingCount, desired:desiredCount}' \
    --output table

echo ""
echo "=== Deployment Summary ==="
echo "Image: ${IMAGE_URI}"
echo "Task Definition: ${TASK_FAMILY}:${REVISION}"
echo "Cluster: ${CLUSTER_NAME}"
echo "Service: ${SERVICE_NAME}"
echo ""
echo "Check logs: aws logs tail /ecs/${TASK_FAMILY} --region ${AWS_REGION} --follow"
echo "Check newsroom: Open Zorora UI and verify newsroom loads"
echo ""
echo "✅ Done!"
