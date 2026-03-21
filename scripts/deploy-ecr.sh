#!/usr/bin/env bash
# deploy-ecr.sh — Build and push the Zorora Docker image to AWS ECR (SEP-051).
# Usage: STAGE=prod [AWS_ACCOUNT_ID=123456789012] ./scripts/deploy-ecr.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_NAME="ona-zorora"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-af-south-1}"
STAGE="${STAGE:-prod}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com"
IMAGE_URI="${ECR_REGISTRY}/${REPO_NAME}"

GIT_SHA="$(git rev-parse --short HEAD)"

echo "==> Deploying ${REPO_NAME}:${STAGE} (sha=${GIT_SHA}) to ${ECR_REGISTRY}"

# ---------------------------------------------------------------------------
# 1. Create ECR repository (idempotent — ignore error if it already exists)
# ---------------------------------------------------------------------------

aws ecr create-repository \
  --repository-name "${REPO_NAME}" \
  --region "${AWS_DEFAULT_REGION}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. Authenticate Docker against ECR
# ---------------------------------------------------------------------------

aws ecr get-login-password --region "${AWS_DEFAULT_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# ---------------------------------------------------------------------------
# 3. Build the image for linux/amd64 (Fargate x86_64)
# ---------------------------------------------------------------------------

docker build \
  --platform linux/amd64 \
  --tag "${IMAGE_URI}:${STAGE}" \
  --tag "${IMAGE_URI}:${STAGE}-${GIT_SHA}" \
  .

# ---------------------------------------------------------------------------
# 4. Push both tags to ECR
# ---------------------------------------------------------------------------

docker push "${IMAGE_URI}:${STAGE}"
docker push "${IMAGE_URI}:${STAGE}-${GIT_SHA}"

echo "==> Done. Image available at:"
echo "    ${IMAGE_URI}:${STAGE}"
echo "    ${IMAGE_URI}:${STAGE}-${GIT_SHA}"
