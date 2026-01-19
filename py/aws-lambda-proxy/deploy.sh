#!/bin/bash

# Deploys the AWS Lambda function by packaging the code, uploading it to S3,
# and deploying the CloudFormation stack.
#
# Usage:
#   ./deploy.sh <s3-bucket-name> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>
#
# Arguments:
#   s3-bucket-name: The name of the S3 bucket to upload the Lambda code to.
#   update-worker-arn: The ARN of the worker Lambda for updating records (e.g., arn:aws-cn:lambda:...)
#   fetch-worker-arn: The ARN of the worker Lambda for fetching records (e.g., arn:aws-cn:lambda:...)
#   vpc-id: The ID of the VPC for the private API endpoint.
#   security-group-id: The Security Group ID for the Lambda function.
#   subnet-ids: A comma-separated list of Subnet IDs for the Lambda function (e.g., "subnet-123,subnet-456").

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
STACK_NAME="ActionHandlerLambdaStack"
TEMPLATE_FILE="template.yaml"
S3_BUCKET="$1"
UPDATE_WORKER_ARN="$2"
FETCH_WORKER_ARN="$3"
VPC_ID="$4"
SECURITY_GROUP_ID="$5"
SUBNET_IDS="$6"

# The name of the zip file that will be created and uploaded
ZIP_FILE="main.py.zip"
# The key (path) in the S3 bucket where the zip file will be stored
S3_KEY="lambda-code/$ZIP_FILE"

# --- Validate Input ---
if [ -z "$S3_BUCKET" ] || [ -z "$UPDATE_WORKER_ARN" ] || [ -z "$FETCH_WORKER_ARN" ] || [ -z "$VPC_ID" ] || [ -z "$SECURITY_GROUP_ID" ] || [ -z "$SUBNET_IDS" ]; then
  echo "Usage: $0 <s3-bucket-name> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>"
  echo "Please provide all required arguments."
  exit 1
fi

# --- Wait for Worker Lambdas ---
echo "Checking for existence of worker Lambdas..."
WORKER_ARNS=("$UPDATE_WORKER_ARN" "$FETCH_WORKER_ARN")
MAX_WAIT_SECONDS=300 # 5 minutes
SECONDS=0 # Reset the timer

while [ $SECONDS -lt $MAX_WAIT_SECONDS ]; do
  all_found=true
  for arn in "${WORKER_ARNS[@]}"; do
    echo "Checking for $arn..."
    if ! aws lambda get-function --function-name "$arn" > /dev/null 2>&1; then
      echo "Worker Lambda $arn not found yet."
      all_found=false
      break # Exit the inner for-loop
    else
      echo "Worker Lambda $arn found."
    fi
  done

  if [ "$all_found" = true ]; then
    echo "All worker Lambdas found."
    break # Exit the while-loop
  fi

  echo "Waiting 10 seconds before retrying..."
  sleep 10
done

if [ "$all_found" = false ]; then
  echo "Timeout: One or more worker Lambdas were not found after $MAX_WAIT_SECONDS seconds."
  exit 1
fi

# --- Main Script ---

# 1. Package the Lambda function code
echo "Packaging Lambda function..."
# Create a temporary directory for packaging to ensure clean zip structure
mkdir -p dist
zip -j dist/$ZIP_FILE main.py # -j junks paths, so it doesn't store directory structure

# 2. Upload the package to S3
echo "Uploading package to S3 bucket: $S3_BUCKET"
aws s3 cp dist/$ZIP_FILE s3://$S3_BUCKET/$S3_KEY

# 3. Deploy the CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    CodeS3Bucket=$S3_BUCKET \
    CodeS3Key=$S3_KEY \
    UpdateWorkerLambdaArn=$UPDATE_WORKER_ARN \
    FetchWorkerLambdaArn=$FETCH_WORKER_ARN \
    VpcId=$VPC_ID \
    SecurityGroupId=$SECURITY_GROUP_ID \
    SubnetIds="""$SUBNET_IDS"""

echo "Deployment complete."

# Clean up local zip file
echo "Cleaning up..."
rm -rf dist

echo "Done."