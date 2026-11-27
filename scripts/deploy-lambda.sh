#!/usr/bin/env bash
# Package lambda/lambda_function.py and push it to the existing Lambda function.
#
# Usage:
#   ./scripts/deploy-lambda.sh
#   FUNCTION_NAME=other-fn AWS_REGION=us-east-1 ./scripts/deploy-lambda.sh
set -euo pipefail

cd "$(dirname "$0")/.."

FUNCTION_NAME="${FUNCTION_NAME:-students-submit}"
REGION="${AWS_REGION:-us-west-2}"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

cp lambda/lambda_function.py "$BUILD_DIR/"
(cd "$BUILD_DIR" && zip -q function.zip lambda_function.py)

aws lambda update-function-code \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --zip-file "fileb://$BUILD_DIR/function.zip" \
  --query '{Function: FunctionName, LastModified: LastModified}' \
  --output table

aws lambda wait function-updated --region "$REGION" --function-name "$FUNCTION_NAME"
echo "Deployed $FUNCTION_NAME in $REGION"
