#!/bin/bash
# Build Lambda Layer for shared utilities and dependencies

set -e

LAYER_NAME="newsroom-shared-layer"
ZIP_FILE="lambda_layer.zip"
BUILD_DIR="/tmp/lambda_layer_build"

echo "Building Lambda Layer: $LAYER_NAME"

# Clean up previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/python"

# Copy shared utilities
mkdir -p "$BUILD_DIR/python/tools/research"
cp tools/research/newsroom_dynamodb.py "$BUILD_DIR/python/tools/research/"
cp tools/research/article_tagger.py "$BUILD_DIR/python/tools/research/"

# Install dependencies
pip install -r infra/lambda/newsroom_scraper/requirements_lambda.txt -t "$BUILD_DIR/python/"

# Create zip
cd "$BUILD_DIR"
zip -r "$ZIP_FILE" python/

echo "Lambda Layer built: $ZIP_FILE"
echo "Upload to AWS Lambda:"
echo "aws lambda publish-layer-version --layer-name $LAYER_NAME --zip-file fileb://$BUILD_DIR/$ZIP_FILE --compatible-runtimes python3.9"
