import boto3
from datetime import datetime, timezone, timedelta
import re

def is_image_older_than_90_days(image_arn: str, days: int = 90) -> tuple[bool, str | None]:
    """
    根据 ECR 镜像 ARN 判断镜像是否超过指定天数
    
    返回: (是否超过90天, 镜像推送时间字符串 或 None)
    """
    # 解析 ARN 获取 region, registry, repo_name, image_tag/digest
    # 示例 ARN: arn:aws:ecr:us-west-2:123456789012:repository/my-app/image:2025-01-15
    pattern = r'^arn:aws:ecr:([^:]+):(\d{12}):repository/(.+?)(?::(.+))?$'
    match = re.match(pattern, image_arn)
    
    if not match:
        return False, "无效的 ECR ARN 格式"

    region, account_id, repository_name, image_tag = match.groups()
    
    # 如果 ARN 没有 :tag 部分，通常是 image digest 格式，需要特别处理
    if image_tag is None:
        # 假设传入的是 digest 格式，需要改用 describe-images 的 imageDigest 过滤
        return False, "暂不支持直接用 digest 的 ARN，请提供带 tag 的 ARN"

    ecr_client = boto3.client('ecr', region_name=region)

    try:
        response = ecr_client.describe_images(
            registryId=account_id,
            repositoryName=repository_name,
            imageIds=[
                {
                    'imageTag': image_tag
                }
            ],
            filter={
                'tagStatus': 'TAGGED'
            }
        )

        if not response.get('imageDetails'):
            return False, f"镜像 {image_arn} 不存在或已被删除"

        # 取第一个匹配的镜像（通常 tag 只对应一个镜像）
        image_detail = response['imageDetails'][0]
        
        # 推送时间（UTC）
        pushed_at: datetime = image_detail['imagePushedAt']
        
        # 确保是 timezone-aware 的 datetime
        if pushed_at.tzinfo is None:
            pushed_at = pushed_at.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        age_days = (now - pushed_at).total_seconds() / 86400
        
        age_str = pushed_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if age_days > days:
            return True, f"镜像已存在 {age_days:.1f} 天（推送时间：{age_str}） → 超过 {days} 天"
        else:
            return False, f"镜像只存在 {age_days:.1f} 天（推送时间：{age_str}）"

    except ecr_client.exceptions.ImageNotFoundException:
        return False, f"镜像 {image_arn} 不存在"
    except Exception as e:
        return False, f"查询失败: {str(e)}"


# ────────────────────────────────────────────────
# 使用示例
# ────────────────────────────────────────────────

if __name__ == "__main__":
    # 替换成你真实的 ARN
    test_arn = "arn:aws:ecr:us-west-2:123456789012:repository/my-backend:latest"
    
    is_old, message = is_image_older_than_90_days(test_arn, days=90)
    
    print("镜像 ARN:", test_arn)
    print("结果:", "超过90天" if is_old else "未超过90天")
    print("详细信息:", message)