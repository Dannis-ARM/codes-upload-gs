import boto3
from datetime import datetime, timezone, timedelta

# Initialize clients
ecr_client = boto3.client('ecr')
sts_client = boto3.client('sts')

# Get current AWS account ID and region dynamically
identity = sts_client.get_caller_identity()
ACCOUNT_ID = identity['Account']
REGION = ecr_client.meta.region_name  # or boto3.session.Session().region_name

# Threshold: images older than 90 days
OLD_THRESHOLD_DAYS = 90
now = datetime.now(timezone.utc)
threshold_date = now - timedelta(days=OLD_THRESHOLD_DAYS)

def paginate_list_repos():
    """List all repositories with pagination."""
    repos = []
    paginator = ecr_client.get_paginator('list_repositories')
    for page in paginator.paginate():
        repos.extend(page.get('repositories', []))
    return repos

def get_tagged_images_in_repo(repo_name):
    """
    Get all tagged image IDs using list_images (filter TAGGED),
    then describe them to get imagePushedAt and build docker pull/push URI.
    Handles pagination.
    """
    image_ids = []
    paginator = ecr_client.get_paginator('list_images')
    for page in paginator.paginate(
        repositoryName=repo_name,
        filter={'tagStatus': 'TAGGED'},
        PaginationConfig={'PageSize': 1000}
    ):
        image_ids.extend(page.get('imageIds', []))

    if not image_ids:
        return []

    # Describe images in batches (max 100 per call)
    old_images = []
    for i in range(0, len(image_ids), 100):
        batch = image_ids[i:i+100]
        response = ecr_client.describe_images(
            repositoryName=repo_name,
            imageIds=batch
        )
        for detail in response.get('imageDetails', []):
            pushed_at = detail.get('imagePushedAt')
            tags = detail.get('imageTags', [])
            if not pushed_at or not tags:
                continue

            age_days = (now - pushed_at).days
            if pushed_at < threshold_date:
                # Construct standard ECR image URI using the first tag
                base_uri = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{repo_name}"
                representative_tag = tags[0]  # use first tag as representative
                uri_tagged = f"{base_uri}:{representative_tag}"

                old_images.append({
                    'uri_tagged': uri_tagged,          # e.g. 123456789012.dkr.ecr.us-west-2.amazonaws.com/my-repo:v1.0
                    'tags': tags,                      # all tags (list)
                    'digest': detail.get('imageDigest'),
                    'pushed_at': pushed_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'age_days': age_days
                })

    return old_images

# Main logic
print(f"Scanning all ECR repositories in account {ACCOUNT_ID} ({REGION}) "
      f"for images older than {OLD_THRESHOLD_DAYS} days...\n")

repositories = paginate_list_repos()

if not repositories:
    print("No repositories found in this region/account.")
else:
    for repo in repositories:
        repo_name = repo['repositoryName']
        repo_arn = repo.get('repositoryArn', 'N/A')
        print(f"Repository: {repo_name}  (ARN: {repo_arn})")

        old_images = get_tagged_images_in_repo(repo_name)

        if old_images:
            print(f"  Found {len(old_images)} tagged images older than {OLD_THRESHOLD_DAYS} days:")
            for img in old_images:
                tags_str = ', '.join(img['tags'])
                print(f"    - URI: {img['uri_tagged']}")
                print(f"      Tags: {tags_str}")
                print(f"      Digest: {img['digest'][:20]}...")  # shortened for readability
                print(f"      Pushed: {img['pushed_at']}")
                print(f"      Age: {img['age_days']} days")
                print()
        else:
            print("  No old tagged images found (or no tagged images at all).")
        print("-" * 60)

print("Scan complete.")