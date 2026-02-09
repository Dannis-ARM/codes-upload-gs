#!/bin/bash

# --- Configuration ---
REPO_NAME="your-repo-name"
IMAGE_TAG="v1.2.3"
REGISTRY_URL="123456789012.dkr.ecr.us-east-1.amazonaws.com"
FULL_IMAGE="${REGISTRY_URL}/${REPO_NAME}:${IMAGE_TAG}"

# --- Functions ---

# Function: Check if the ECR repository is set to IMMUTABLE
# Returns: "IMMUTABLE" or "MUTABLE"
get_repo_mutability() {
    local repo=$1
    # Get the mutability setting using AWS CLI
    aws ecr describe-repositories \
        --repository-names "$repo" \
        --query 'repositories[0].imageTagMutability' \
        --output text
}

# Function: Check if a specific tag already exists in the ECR repo
# Returns: 0 (exists), 1 (does not exist)
check_tag_exists() {
    local repo=$1
    local tag=$2
    # Check for image existence; suppress output
    if aws ecr describe-images --repository-name "$repo" --image-ids imageTag="$tag" > /dev/null 2>&1; then
        return 0 # Tag exists
    else
        return 1 # Tag does not exist
    fi
}

# Function: Core logic to decide whether to push or abort
safe_push() {
    local repo=$1
    local tag=$2
    local full_img=$3

    echo "Checking policy for repository: $repo"
    
    # 1. Get mutability status
    local mutability=$(get_repo_mutability "$repo")
    
    if [ "$mutability" == "IMMUTABLE" ]; then
        echo "Status: IMMUTABLE. Checking for tag existence..."
        
        # 2. Check for tag conflict
        if check_tag_exists "$repo" "$tag"; then
            echo "Error: Tag '$tag' already exists. Aborting push to prevent policy violation."
            return 1
        fi
        echo "Tag '$tag' is unique. Proceeding..."
    else
        echo "Status: MUTABLE. Overwriting is allowed."
    fi

    # 3. Perform the actual push
    echo "Pushing image: $full_img"
    if podman push "$full_img"; then
        return 0
    else
        echo "Push failed during execution."
        return 1
    fi
}

# --- Main Execution ---

# Call the function and handle the result
if safe_push "$REPO_NAME" "$IMAGE_TAG" "$FULL_IMAGE"; then
    echo "✅ Success: 123"
else
    echo "❌ Failed: Push aborted or encountered error."
    exit 1
fi