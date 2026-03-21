#!/usr/bin/env bash
# deploy-fargate.sh — Deploy Zorora as an ECS Fargate service
# SEP-052: First Fargate service on the Ona platform
set -euo pipefail

# ── Configuration ──
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-af-south-1}"
STAGE="${STAGE:-prod}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com"
APP_NAME="ona-zorora"
CLUSTER_NAME="${APP_NAME}-${STAGE}"
SERVICE_NAME="${APP_NAME}-${STAGE}"
TASK_FAMILY="${APP_NAME}-${STAGE}"
LOG_GROUP="/ecs/${APP_NAME}-${STAGE}"
EXECUTION_ROLE_NAME="${APP_NAME}-task-execution-role"
CONTAINER_PORT=5000

# Image tag: prefer immutable (stage-sha), fall back to stage
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo '')"
IMAGE_TAG="${GIT_SHA:+${STAGE}-${GIT_SHA}}"
IMAGE_TAG="${IMAGE_TAG:-$STAGE}"
IMAGE_URI="${ECR_REGISTRY}/${APP_NAME}:${IMAGE_TAG}"

echo "=== Zorora Fargate Deployment ==="
echo "Region:  ${AWS_DEFAULT_REGION}"
echo "Stage:   ${STAGE}"
echo "Image:   ${IMAGE_URI}"
echo "Cluster: ${CLUSTER_NAME}"
echo ""

# ── Step 1: IAM Task Execution Role ──
echo "Step 1: Ensuring IAM task execution role..."

ASSUME_ROLE_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

EXECUTION_ROLE_ARN=$(aws iam get-role \
    --role-name "${EXECUTION_ROLE_NAME}" \
    --query 'Role.Arn' --output text 2>/dev/null || true)

if [ -z "${EXECUTION_ROLE_ARN}" ] || [ "${EXECUTION_ROLE_ARN}" = "None" ]; then
    echo "  Creating execution role: ${EXECUTION_ROLE_NAME}"
    EXECUTION_ROLE_ARN=$(aws iam create-role \
        --role-name "${EXECUTION_ROLE_NAME}" \
        --assume-role-policy-document "${ASSUME_ROLE_POLICY}" \
        --query 'Role.Arn' --output text)

    aws iam attach-role-policy \
        --role-name "${EXECUTION_ROLE_NAME}" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
    echo "  Attached AmazonECSTaskExecutionRolePolicy"
else
    echo "  Execution role already exists: ${EXECUTION_ROLE_ARN}"
fi

# ── Step 2: CloudWatch Log Group ──
echo "Step 2: Ensuring CloudWatch log group..."
aws logs create-log-group \
    --log-group-name "${LOG_GROUP}" \
    --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true
echo "  Log group: ${LOG_GROUP}"

# ── Step 3: ECS Cluster ──
echo "Step 3: Ensuring ECS cluster..."
aws ecs create-cluster \
    --cluster-name "${CLUSTER_NAME}" \
    --region "${AWS_DEFAULT_REGION}" >/dev/null
echo "  Cluster: ${CLUSTER_NAME}"

# ── Step 4: Register Task Definition ──
echo "Step 4: Registering task definition..."

TASK_DEF_JSON=$(cat <<TASKDEF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "containerDefinitions": [{
    "name": "${APP_NAME}",
    "image": "${IMAGE_URI}",
    "essential": true,
    "portMappings": [{
      "containerPort": 5000,
      "protocol": "tcp"
    }],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "${LOG_GROUP}",
        "awslogs-region": "${AWS_DEFAULT_REGION}",
        "awslogs-stream-prefix": "zorora"
      }
    }
  }]
}
TASKDEF
)

aws ecs register-task-definition \
    --cli-input-json "${TASK_DEF_JSON}" \
    --region "${AWS_DEFAULT_REGION}" >/dev/null
echo "  Task definition: ${TASK_FAMILY}"

# ── Step 5: Discover VPC and Subnets ──
echo "Step 5: Discovering VPC and subnets..."

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' --output text \
    --region "${AWS_DEFAULT_REGION}")
echo "  VPC: ${VPC_ID}"

SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" \
    --query 'Subnets[*].SubnetId' --output text \
    --region "${AWS_DEFAULT_REGION}" | tr '\t' ',')
echo "  Subnets: ${SUBNETS}"

# ── Step 6: Security Group ──
echo "Step 6: Ensuring security group..."

SG_NAME="${APP_NAME}-${STAGE}-sg"
SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
    --query 'SecurityGroups[0].GroupId' --output text \
    --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true)

if [ -z "${SG_ID}" ] || [ "${SG_ID}" = "None" ]; then
    echo "  Creating security group: ${SG_NAME}"
    SG_ID=$(aws ec2 create-security-group \
        --group-name "${SG_NAME}" \
        --description "Zorora Fargate service - port ${CONTAINER_PORT}" \
        --vpc-id "${VPC_ID}" \
        --query 'GroupId' --output text \
        --region "${AWS_DEFAULT_REGION}")

    aws ec2 authorize-security-group-ingress \
        --group-id "${SG_ID}" \
        --protocol tcp \
        --port 5000 \
        --cidr "0.0.0.0/0" \
        --region "${AWS_DEFAULT_REGION}" >/dev/null
    echo "  Opened port 5000 ingress"
else
    echo "  Security group already exists: ${SG_ID}"
fi

# ── Step 7: Create or Update ECS Service ──
echo "Step 7: Deploying ECS service..."

NETWORK_CONFIG="awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"

EXISTING_SERVICE=$(aws ecs describe-services \
    --cluster "${CLUSTER_NAME}" \
    --services "${SERVICE_NAME}" \
    --query 'services[?status==`ACTIVE`].serviceName' --output text \
    --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true)

if [ -z "${EXISTING_SERVICE}" ] || [ "${EXISTING_SERVICE}" = "None" ]; then
    echo "  Creating new service: ${SERVICE_NAME}"
    aws ecs create-service \
        --cluster "${CLUSTER_NAME}" \
        --service-name "${SERVICE_NAME}" \
        --task-definition "${TASK_FAMILY}" \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "${NETWORK_CONFIG}" \
        --region "${AWS_DEFAULT_REGION}" >/dev/null
else
    echo "  Updating existing service: ${SERVICE_NAME}"
    aws ecs update-service \
        --cluster "${CLUSTER_NAME}" \
        --service "${SERVICE_NAME}" \
        --task-definition "${TASK_FAMILY}" \
        --desired-count 1 \
        --network-configuration "${NETWORK_CONFIG}" \
        --region "${AWS_DEFAULT_REGION}" >/dev/null
fi

# ── Step 8: Wait and retrieve public IP ──
echo "Step 8: Waiting for task to start..."
sleep 10

TASK_ARN=$(aws ecs list-tasks \
    --cluster "${CLUSTER_NAME}" \
    --service-name "${SERVICE_NAME}" \
    --query 'taskArns[0]' --output text \
    --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true)

PUBLIC_IP=""
if [ -n "${TASK_ARN}" ] && [ "${TASK_ARN}" != "None" ]; then
    ENI_ID=$(aws ecs describe-tasks \
        --cluster "${CLUSTER_NAME}" \
        --tasks "${TASK_ARN}" \
        --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
        --output text \
        --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true)

    if [ -n "${ENI_ID}" ] && [ "${ENI_ID}" != "None" ]; then
        PUBLIC_IP=$(aws ec2 describe-network-interfaces \
            --network-interface-ids "${ENI_ID}" \
            --query 'NetworkInterfaces[0].Association.PublicIp' \
            --output text \
            --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true)
    fi
fi

echo ""
echo "=== Deployment Complete ==="
if [ -n "${PUBLIC_IP}" ] && [ "${PUBLIC_IP}" != "None" ]; then
    echo "Endpoint: http://${PUBLIC_IP}:5000"
    echo "Health:   http://${PUBLIC_IP}:5000/health"
else
    echo "Public IP not yet available. Task may still be starting."
    echo "Check with: aws ecs list-tasks --cluster ${CLUSTER_NAME}"
fi
