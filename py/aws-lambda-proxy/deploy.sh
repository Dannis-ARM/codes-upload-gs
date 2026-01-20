#!/bin/bash
# </noparse>

# Deploys the AWS Lambda function by packaging the code, uploading it to S3,
# and deploying the CloudFormation stack from a template also in S3.
#
# Usage:
#   ./deploy.sh <stack-name> <template-file> <s3-bucket-name> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>
#
# Arguments:
#   stack-name: The name of the CloudFormation stack to deploy.
#   template-file: The name of the CloudFormation template file (e.g., 'template.yaml').
#   s3-bucket-name: The name of the S3 bucket to upload artifacts to.
#   update-worker-arn: The ARN of the worker Lambda for updating records (e.g., arn:aws-cn:lambda:...)
#   fetch-worker-arn: The ARN of the worker Lambda for fetching records (e.g., arn:aws-cn:lambda:...)
#   vpc-id: The ID of the VPC for the private API endpoint.
#   security-group-id: The Security Group ID for the Lambda function.
#   subnet-ids: A comma-separated list of Subnet IDs for the Lambda function (e.g., "subnet-123,subnet-456").

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
STACK_NAME="$1"
TEMPLATE_FILE="$2"
S3_BUCKET="$3"
UPDATE_WORKER_ARN="$4"
FETCH_WORKER_ARN="$5"
VPC_ID="$6"
SECURITY_GROUP_ID="$7"
SUBNET_IDS="$8"

# The name of the zip file that will be created and uploaded
ZIP_FILE="main.py.zip"
# The key (path) in the S3 bucket where the zip file will be stored
S3_CODE_KEY="lambda-code/$ZIP_FILE"
# The key (path) in the S3 bucket where the CloudFormation template will be stored
S3_TEMPLATE_KEY="cfn-templates/$TEMPLATE_FILE"


# --- Validate Input ---
if [ -z "$STACK_NAME" ] || [ -z "$TEMPLATE_FILE" ] || [ -z "$S3_BUCKET" ] || [ -z "$UPDATE_WORKER_ARN" ] || [ -z "$FETCH_WORKER_ARN" ] || [ -z "$VPC_ID" ] || [ -z "$SECURITY_GROUP_ID" ] || [ -z "$SUBNET_IDS" ]; then
  echo "Usage: $0 <stack-name> <template-file> <s3-bucket-name> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>"
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

# 1. Package the Lambda function code (main.py is always expected)
echo "Packaging Lambda function..."
# Create a temporary directory for packaging to ensure clean zip structure
mkdir -p dist
zip -j dist/main.py.zip main.py

# 2. Upload artifacts to S3
echo "Uploading Lambda code package to S3..."
aws s3 cp dist/main.py.zip "s3://$S3_BUCKET/$S3_CODE_KEY"

echo "Uploading CloudFormation template to S3..."
aws s3 cp "$TEMPLATE_FILE" "s3://$S3_BUCKET/$S3_TEMPLATE_KEY"

# 3. Deploy the CloudFormation stack with robust logic
# --- Deployment Functions ---

deploy_stack() {
  echo "Deploying CloudFormation stack '$STACK_NAME'..."
  # The 'aws cloudformation deploy' command creates the stack if it doesn't exist,
  # or updates it if it does. It uses the template that's already in S3.
  aws cloudformation deploy \
    --template-file "s3://$S3_BUCKET/$S3_TEMPLATE_KEY" \
    --stack-name "$STACK_NAME" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      CodeS3Bucket="$S3_BUCKET" \
      CodeS3Key="$S3_CODE_KEY" \
      UpdateWorkerLambdaArn="$UPDATE_WORKER_ARN" \
      FetchWorkerLambdaArn="$FETCH_WORKER_ARN" \
      VpcId="$VPC_ID" \
      SecurityGroupId="$SECURITY_GROUP_ID" \
      SubnetIds="$SUBNET_IDS"
}

destroy_stack() {
  echo "Attempting to destroy CloudFormation stack '$STACK_NAME'..."
  # Check if stack exists before trying to delete it to avoid errors.
  if aws cloudformation describe-stacks --stack-name "$STACK_NAME" > /dev/null 2>&1; then
    echo "Stack '$STACK_NAME' exists. Deleting..."
    aws cloudformation delete-stack --stack-name "$STACK_NAME"
    echo "Waiting for stack to be destroyed..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
    echo "Stack '$STACK_NAME' destroyed."
  else
    echo "Stack '$STACK_NAME' does not exist, no need to destroy."
  fi
}

# --- Main Deployment Logic ---
# Based on stack existence, we decide to create or update, with retry logic.
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" > /dev/null 2>&1; then
  echo "Stack '$STACK_NAME' exists. Attempting to update..."
  if ! deploy_stack; then
    echo "Stack update failed. To recover, attempting to destroy and recreate the stack."
    destroy_stack
    echo "Re-attempting to create stack '$STACK_NAME'..."
    if ! deploy_stack; then
      echo "FATAL: Failed to recreate stack '$STACK_NAME' after destruction. Please check the AWS CloudFormation console for details."
      exit 1
    fi
  fi
else
  echo "Stack '$STACK_NAME' does not exist. Attempting to create..."
  if ! deploy_stack; then
    echo "Initial stack creation failed. The stack may be in a ROLLBACK_COMPLETE state."
    echo "To recover, attempting to destroy and recreate the stack."
    destroy_stack
    echo "Re-attempting to create stack '$STACK_NAME'..."
    if ! deploy_stack; then
      echo "FATAL: Failed to create stack '$STACK_NAME' on second attempt. Please check the AWS CloudFormation console for details."
      exit 1
    fi
  fi
fi

echo "Deployment of stack '$STACK_NAME' complete."

# Clean up local zip file
echo "Cleaning up..."
rm -rf dist

echo "Done."
# </#noparse>