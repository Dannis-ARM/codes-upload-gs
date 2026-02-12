#!/bin/bash

# =================================================================
# Script: migrate_image.sh
# Description: Parse, tag, and push a docker image to a Harbor registry.
# Usage: ./migrate_image.sh <SOURCE_IMAGE_URL> <TARGET_HARBOR_URL>
# =================================================================

# --- Global Variables for Harbor Credentials ---
# Suggestion: Set these in your environment or CI/CD secrets
export HARBOR_USER="${HARBOR_USER:-admin}"
export HARBOR_PASS="${HARBOR_PASS:-Harbor12345}"

# --- Function: Parse Source Image URL ---
parse_image_url() {
    local full_url=$1

    # 1. Extract Tag
    if [[ $full_url == *":"* ]]; then
        IMG_TAG="${full_url##*:}"
        local without_tag="${full_url%:*}"
    else
        IMG_TAG="latest"
        local without_tag="$full_url"
    fi

    # 2. Extract Registry
    REG_URL="${without_tag%%/*}"

    # 3. Extract Project and Repo
    local path_part="${without_tag#*/}"
    if [[ "$path_part" == *"/"* ]]; then
        PROJ_NAME="${path_part%%/*}"
        REPO_NAME="${path_part#*/}"
    else
        PROJ_NAME="library"
        REPO_NAME="$path_part"
    fi
}

# --- Function: Push to Target Harbor ---
push_to_harbor() {
    local target_reg=$1
    local proj=$2
    local repo=$3
    local tag=$4
    local source_img=$5
    local auth="${HARBOR_USER}:${HARBOR_PASS}"

    echo "[INFO] Creating/Checking Project: $proj"
    local create_code=$(curl -k -u "$auth" -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        "https://$target_reg/api/v2.0/projects" \
        -d "{\"project_name\": \"$proj\", \"metadata\": {\"public\": \"false\"}}")

    local target_full_image="${target_reg}/${proj}/${repo}:${tag}"
    
    echo "[STEP] Tagging: $source_img -> $target_full_image"
    podman tag "$source_img" "$target_full_image"

    echo "[STEP] Pushing to Harbor..."
    podman push "$target_full_image"

    return $?
}

# --- Main Logic ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <SOURCE_IMAGE_URL> <TARGET_HARBOR_URL>"
    echo "Example: $0 registry.cn-hangzhou.aliyuncs.com/ali-space/app:v1 harbor.my.com"
    exit 1
fi

SOURCE_IMG=$1
TARGET_REG=$2

parse_image_url "$SOURCE_IMG"
push_to_harbor "$TARGET_REG" "$PROJ_NAME" "$REPO_NAME" "$IMG_TAG" "$SOURCE_IMG"

if [ $? -eq 0 ]; then
    echo "Done!"
else
    echo "Failed!"
    exit 1
fi