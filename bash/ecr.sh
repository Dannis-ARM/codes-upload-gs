#!/bin/bash

# 变量配置
REPO_NAME="your-ecr-repo-name"
IMAGE_TAG="v1.2.3" # 或者是你的 $TAG 变量
IMAGE_FULL_NAME="123456789012.dkr.ecr.us-east-1.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

echo "正在检查 ECR 标签状态..."

# 1. 使用 AWS CLI 检查标签是否存在
# --query 能够直接筛选结果，2>/dev/null 隐藏找不到标签时的报错
EXISTING_TAG=$(aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$IMAGE_TAG" \
    --query 'imageDetails[0].imageTags' \
    --output text 2>/dev/null)

if [ "$EXISTING_TAG" == "$IMAGE_TAG" ]; then
    echo "警告: 标签 [$IMAGE_TAG] 在仓库 [$REPO_NAME] 中已存在。"
    echo "由于 ECR 开启了不可变策略，跳过推送。"
    # 如果你想让脚本在这里失败退出，取消下面这行的注释
    # exit 1 
else
    echo "标签不存在，准备推送镜像..."
    
    # 2. 执行推送
    if podman push "$IMAGE_FULL_NAME"; then
        echo "✅ 镜像推送成功！"
        # 在这里执行你的后续逻辑，比如 echo 123
        echo 123
    else
        echo "❌ Podman 推送失败，请检查网络或权限。"
        exit 1
    fi
fi