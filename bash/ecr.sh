#!/bin/bash

# --- Input ---
FULL_IMAGE="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app/backend:v1.2.3"

# --- Functions ---

# Function: Parse full image into Registry, Repo, and Tag
parse_image_full() {
    local full_img=$1

    # 1. Extract Registry: Everything before the first '/'
    local reg="${full_img%%/*}"

    # 2. Extract Path with Tag: Everything after the first '/'
    local path_with_tag="${full_img#*/}"

    # 3. Extract Tag: Everything after the LAST ':'
    local tag="${path_with_tag##*:}"

    # 4. Extract Repo: Everything between the first '/' and the last ':'
    local repo="${path_with_tag%:*}"

    echo "$reg" "$repo" "$tag"
}

# Function: Check ECR Policy and Push
execute_safe_push() {
    local full_img=$1
    
    # Use read to capture the three parts from parse function
    read -r REGISTRY REPO TAG <<< $(parse_image_full "$full_img")

    echo "--- Image Details ---"
    echo "Registry: $REGISTRY"
    echo "Repo Name: $REPO"
    echo "Image Tag: $TAG"
    echo "----------------------"

    # Step 1: Get Mutability Setting (English: Check if repo allows overwriting)
    local mutability=$(aws ecr describe-repositories \
        --repository-names "$REPO" \
        --query 'repositories[0].imageTagMutability' \
        --output text 2>/dev/null)

    # Error handling if repo doesn't exist
    if [ $? -ne 0 ]; then
        echo "Error: Repository '$REPO' not found in ECR."
        return 1
    fi

    # Step 2: Policy Logic
    if [ "$mutability" == "IMMUTABLE" ]; then
        echo "Policy: IMMUTABLE. Checking if tag '$TAG' exists..."
        
        # Check if tag exists (English: Prevent overwrite error)
        if aws ecr describe-images --repository-name "$REPO" --image-ids imageTag="$TAG" > /dev/null 2>&1; then
            echo "Abort: Tag already exists and cannot be overwritten."
            return 1
        fi
    else
        echo "Policy: MUTABLE. Proceeding with push."
    fi

    # Step 3: Actual Push
    if podman push "$full_img"; then
        echo "✅ Push successful: 123"
        return 0
    else
        echo "❌ Podman push command failed."
        return 1
    fi
}

# --- Main ---
execute_safe_push "$FULL_IMAGE"