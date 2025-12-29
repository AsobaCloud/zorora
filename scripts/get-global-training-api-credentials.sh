#!/bin/bash
#
# Retrieve ONA Platform API credentials from AWS SSM Parameter Store
#
# This script retrieves the API endpoint and token from SSM and outputs
# export commands that can be sourced or evaluated.
#
# Usage:
#   source <(./scripts/get-global-training-api-credentials.sh)
#   # or
#   eval $(./scripts/get-global-training-api-credentials.sh)
#

set -euo pipefail

# SSM Parameter paths
ENDPOINT_PARAM="/ona-platform/prod/global-training-api-endpoint"
TOKEN_PARAM="/ona-platform/prod/global-training-api-token"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed or not in PATH" >&2
    echo "Install AWS CLI: https://aws.amazon.com/cli/" >&2
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured" >&2
    echo "Run 'aws configure' or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY" >&2
    exit 1
fi

# Retrieve endpoint
echo "Retrieving API endpoint from SSM..." >&2
ENDPOINT=$(aws ssm get-parameter \
    --name "$ENDPOINT_PARAM" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null)

if [ -z "$ENDPOINT" ]; then
    echo "Error: Failed to retrieve endpoint from $ENDPOINT_PARAM" >&2
    exit 1
fi

# Retrieve token
echo "Retrieving API token from SSM..." >&2
TOKEN=$(aws ssm get-parameter \
    --name "$TOKEN_PARAM" \
    --with-decryption \
    --query 'Parameter.Value' \
    --output text 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Error: Failed to retrieve token from $TOKEN_PARAM" >&2
    exit 1
fi

# Output export commands
echo "export ONA_API_BASE_URL=\"$ENDPOINT\""
echo "export ONA_API_TOKEN=\"$TOKEN\""
echo "export ONA_USE_IAM=\"false\""

echo "" >&2
echo "✓ Credentials retrieved successfully" >&2
echo "  ONA_API_BASE_URL=$ENDPOINT" >&2
echo "  ONA_API_TOKEN=*** (masked)" >&2
echo "" >&2
echo "To use these credentials, run:" >&2
echo "  source <(./scripts/get-global-training-api-credentials.sh)" >&2
echo "  # or" >&2
echo "  eval \$(./scripts/get-global-training-api-credentials.sh)" >&2
