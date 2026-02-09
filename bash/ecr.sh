#!/bin/bash

# Configuration
REPO_NAME="your-repo-name"
IMAGE_TAG="v1.2.3"
REGISTRY_URL="123456789012.dkr.ecr.us-east-1.amazonaws.com"
FULL_IMAGE="${REGISTRY_URL}/${REPO_NAME}:${IMAGE_TAG}"

echo "Starting deployment check for ${FULL_IMAGE}..."

# 1. Check if the repository is Immutable
# Check repository tag mutability setting
MUTABILITY=$(aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --query 'repositories[0].imageTagMutability' \
    --output text)

echo "Repository mutability setting: $MUTABILITY"

SHOULD_PUSH=true

if [ "$MUTABILITY" == "IMMUTABLE" ]; then
    echo "Policy is IMMUTABLE. Checking for existing tag..."
    
    # 2. Check if the tag already exists in the ECR repo
    # If the tag exists, describe-images will return 0; if not, it returns an error
    if aws ecr describe-images --repository-name "$REPO_NAME" --image-ids imageTag="$IMAGE_TAG" > /dev/null 2>&1; then
        echo "Error: Tag '$IMAGE_TAG' already exists and repository is immutable."
        SHOULD_PUSH=false
    else
        echo "Tag '$IMAGE_TAG' does not exist. Proceeding..."
    fi
else
    echo "Repository is MUTABLE. Overwriting is allowed."
fi

# 3. Execution logic
if [ "$SHOULD_PUSH" = true ]; then
    echo "Executing: podman push $FULL_IMAGE"
    if podman push "$FULL_IMAGE"; then
        echo "Push successful!"
        # Put your next steps here (e.g., echo 123)
        echo 123
    else
        echo "Push failed due to network or authentication issues."
        exit 1
    fi
else
    echo "Push aborted to prevent tag conflict."
    # Decide if you want the script to fail (exit 1) or just skip (exit 0)
    exit 1
fi