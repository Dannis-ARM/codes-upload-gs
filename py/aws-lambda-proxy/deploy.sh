#!/bin/bash
# <#noparse>

# Deploys the AWS Lambda function by packaging the code, uploading it to S3,
# and deploying the CloudFormation stack from a template also in S3.
#
# Usage:
#   ./deploy.sh <stack-name> <template-file> <s3-bucket-name> <region> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>
#
# Arguments:
#   stack-name: The name of the CloudFormation stack to deploy.
#   template-file: The name of the CloudFormation template file (e.g., 'template.yaml').
#   s3-bucket-name: The name of the S3 bucket to upload artifacts to.
#   region: The AWS region to deploy to (e.g., 'us-east-1').
#   update-worker-arn: The ARN of the worker Lambda for updating records (e.g., arn:aws-cn:lambda:...)
#   fetch-worker-arn: The ARN of the worker Lambda for fetching records (e.g., arn:aws-cn:lambda:...)
#   vpc-id: The ID of the VPC for the private API endpoint.
#   security-group-id: The Security Group ID for the Lambda function.
#   subnet-ids: A comma-separated list of Subnet IDs for the Lambda function (e.g., "subnet-123,subnet-456").

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
STACK_NAME=""
TEMPLATE_FILE="$2"
S3_BUCKET="$3"
REGION="$4"
UPDATE_WORKER_ARN="$5"
FETCH_WORKER_ARN="$6"
VPC_ID="$7"
SECURITY_GROUP_ID="$8"
SUBNET_IDS="$9"

# The name of the zip file that will be created and uploaded
ZIP_FILE="main.py.zip"
# The key (path) in the S3 bucket where the zip file will be stored
S3_CODE_KEY="lambda-code/$ZIP_FILE"
# The key (path) in the S3 bucket where the CloudFormation template will be stored
S3_TEMPLATE_KEY="cfn-templates/$TEMPLATE_FILE"


# --- Validate Input ---
if [ -z "$STACK_NAME" ] || [ -z "$TEMPLATE_FILE" ] || [ -z "$S3_BUCKET" ] || [ -z "$REGION" ] || [ -z "$UPDATE_WORKER_ARN" ] || [ -z "$FETCH_WORKER_ARN" ] || [ -z "$VPC_ID" ] || [ -z "$SECURITY_GROUP_ID" ] || [ -z "$SUBNET_IDS" ]; then
  echo "Usage: $0 <stack-name> <template-file> <s3-bucket-name> <region> <update-worker-arn> <fetch-worker-arn> <vpc-id> <security-group-id> <subnet-ids>"
  echo "Please provide all required arguments."
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
aws s3 cp dist/main.py.zip "s3://$S3_BUCKET/$S3_CODE_KEY" --region "$REGION"

echo "Uploading CloudFormation template to S3..."
aws s3 cp "$TEMPLATE_FILE" "s3://$S3_BUCKET/$S3_TEMPLATE_KEY" --region "$REGION"

# --- Find AWS Region for Template URL ---
echo "Using AWS Region: $REGION"

# Construct the S3 Template URL.
S3_URL_PATH_STYLE="https://s3.$REGION.amazonaws.com/$S3_BUCKET/$S3_TEMPLATE_KEY"

# --- Deployment Functions ---

create_stack() {
  echo "Creating CloudFormation stack '$STACK_NAME'..."
  aws cloudformation create-stack \
    --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --template-url "$S3_URL_PATH_STYLE" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameters \
      ParameterKey=CodeS3Bucket,ParameterValue=$S3_BUCKET \
      ParameterKey=CodeS3Key,ParameterValue=$S3_CODE_KEY \
      ParameterKey=UpdateWorkerLambdaArn,ParameterValue=$UPDATE_WORKER_ARN \
      ParameterKey=FetchWorkerLambdaArn,ParameterValue=$FETCH_WORKER_ARN \
      ParameterKey=VpcId,ParameterValue=$VPC_ID \
      ParameterKey=SecurityGroupId,ParameterValue=$SECURITY_GROUP_ID \
      ParameterKey=SubnetIds,ParameterValue="$SUBNET_IDS"

  echo "Waiting for stack creation to complete..."
  set +e # Disable exit on error temporarily
  aws cloudformation wait stack-create-complete --region "$REGION" --stack-name "$STACK_NAME"
  local exit_code=$?
  set -e # Re-enable exit on error
  return $exit_code
}

update_stack() {
  echo "Updating CloudFormation stack '$STACK_NAME'..."
  # The update-stack command can fail if there are no changes. We handle this.
  set +e # Disable exit on error temporarily
  UPDATE_OUTPUT=$(aws cloudformation update-stack \
    --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --template-url "$S3_URL_PATH_STYLE" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameters \
      ParameterKey=CodeS3Bucket,ParameterValue=$S3_BUCKET \
      ParameterKey=CodeS3Key,ParameterValue=$S3_CODE_KEY \
      ParameterKey=UpdateWorkerLambdaArn,ParameterValue=$UPDATE_WORKER_ARN \
      ParameterKey=FetchWorkerLambdaArn,ParameterValue=$FETCH_WORKER_ARN \
      ParameterKey=VpcId,ParameterValue=$VPC_ID \
      ParameterKey=SecurityGroupId,ParameterValue=$SECURITY_GROUP_ID \
      ParameterKey=SubnetIds,ParameterValue="$SUBNET_IDS" 2>&1)
  
  UPDATE_EXIT_CODE=$?
  set -e # Re-enable exit on error

  if [ $UPDATE_EXIT_CODE -ne 0 ]; then
    if [[ "$UPDATE_OUTPUT" == *"No updates are to be performed"* ]]; then
      echo "No changes detected for stack '$STACK_NAME'. Update not needed."
      return 0 # Treat as success
    else
      echo "Error updating stack: $UPDATE_OUTPUT" >&2
      return $UPDATE_EXIT_CODE # Propagate other errors
    fi
  fi
  
  echo "Waiting for stack update to complete..."
  aws cloudformation wait stack-update-complete --region "$REGION" --stack-name "$STACK_NAME"
}

destroy_stack() {
  echo "Attempting to destroy CloudFormation stack '$STACK_NAME'..."
  if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" > /dev/null 2>&1; then
    echo "Stack '$STACK_NAME' exists. Deleting..."
    aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK_NAME"
    echo "Waiting for stack to be destroyed..."
    aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK_NAME"
    echo "Stack '$STACK_NAME' destroyed."
  else
    echo "Stack '$STACK_NAME' does not exist, no need to destroy."
  fi
}

# --- Main Deployment Logic ---
if aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" > /dev/null 2>&1; then
  echo "Stack '$STACK_NAME' exists. Attempting to update..."
  if ! update_stack; then
    echo "Stack update failed. Please check the stack events for more details." >&2
    exit 1
  fi
else
  echo "Stack '$STACK_NAME' does not exist. Attempting to create..."
  if ! create_stack; then
    echo "Initial stack creation failed. Attempting to destroy the stack..." >&2
    destroy_stack
    echo "Stack destruction complete." >&2
    exit 1
  fi
fi

echo "Deployment of stack '$STACK_NAME' complete."

# Clean up local zip file
echo "Cleaning up..."
rm -rf dist

echo "Done."
# </#noparse>