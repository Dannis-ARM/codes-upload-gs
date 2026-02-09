#!/bin/bash

# --- Input ---
FULL_IMAGE="123456789012.dkr.ecr.us-east-1.amazonaws.com/my-app/backend:v1.2.3"

# --- Functions ---

parse_image_full() {
    local full_img=$1
    local reg="${full_img%%/*}"
    local path_with_tag="${full_img#*/}"
    local tag="${path_with_tag##*:}"
    local repo="${path_with_tag%:*}"
    echo "$reg" "$repo" "$tag"
}

execute_safe_push() {
    local full_img=$1
    read -r REGISTRY REPO TAG <<< $(parse_image_full "$full_img")

    # 1. Get Mutability Setting
    # English: Fetch repository configuration from ECR
    local mutability=$(aws ecr describe-repositories \
        --repository-names "$REPO" \
        --query 'repositories[0].imageTagMutability' \
        --output text 2>/dev/null)

    if [ $? -ne 0 ]; then
        echo "ERROR: Repository '$REPO' not found in ECR."
        return 1
    fi

    # 2. Check Tag existence if IMMUTABLE
    # English: If policy is IMMUTABLE, check for existing tag to avoid push failure
    if [ "$mutability" == "IMMUTABLE" ]; then
        if aws ecr describe-images --repository-name "$REPO" --image-ids imageTag="$TAG" > /dev/null 2>&1; then
            echo "SKIPPED: Tag '$TAG' exists in IMMUTABLE repo. No action taken."
            return 0 # Or return 1 if you want to treat this as an error
        fi
    fi

    # 3. Perform Push
    # English: Execute the actual push and capture any internal errors
    if podman push "$full_img" > /dev/null 2>&1; then
        echo "SUCCESS: Image pushed successfully to $REPO:$TAG."
        return 0
    else
        echo "ERROR: Podman push failed. Check network or permissions."
        return 1
    fi
}

# --- Main Execution ---

# English: Execute function and capture the message into a variable
# Chinese: 执行函数并将返回的 Message 捕获到变量中
RESULT_MESSAGE=$(execute_safe_push "$FULL_IMAGE")
EXIT_STATUS=$?

# English: Handle the result based on exit status
# Chinese: 根据状态码判断后续逻辑
if [ $EXIT_STATUS -eq 0 ]; then
    echo "Done! Details: $RESULT_MESSAGE"
    # 执行成功的后续逻辑 (Success logic)
    echo 123
else
    echo "Something went wrong: $RESULT_MESSAGE"
    # 执行失败的后续逻辑 (Failure logic)
    exit 1
fi