import boto3
from datetime import datetime, timezone, timedelta

# Initialize ECR client (assumes default AWS credentials/profile/region)
client = boto3.client('ecr')

# Threshold: images older than 90 days
OLD_THRESHOLD_DAYS = 90
now = datetime.now(timezone.utc)
threshold_date = now - timedelta(days=OLD_THRESHOLD_DAYS)

def paginate_list_repos():
    """List all repositories with pagination."""
    repos = []
    paginator = client.get_paginator('list_repositories')
    for page in paginator.paginate():
        repos.extend(page.get('repositories', []))
    return repos

def get_tagged_images_in_repo(repo_name):
    """
    Get all tagged image IDs using list_images (filter TAGGED),
    then describe them to get imagePushedAt.
    Handles pagination.
    """
    image_ids = []
    paginator = client.get_paginator('list_images')
    for page in paginator.paginate(
        repositoryName=repo_name,
        filter={'tagStatus': 'TAGGED'},
        PaginationConfig={'PageSize': 1000}
    ):
        image_ids.extend(page.get('imageIds', []))

    if not image_ids:
        return []

    # Now describe images to get details (including imagePushedAt)
    # describe_images supports up to 100 imageIds per call
    old_images = []
    for i in range(0, len(image_ids), 100):
        batch = image_ids[i:i+100]
        response = client.describe_images(
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
                old_images.append({
                    'tags': tags,
                    'digest': detail['imageDigest'],
                    'pushed_at': pushed_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'age_days': age_days
                })

    return old_images

# Main logic
print("Scanning all ECR repositories for images older than {} days...\n".format(OLD_THRESHOLD_DAYS))

repositories = paginate_list_repos()

if not repositories:
    print("No repositories found.")
else:
    for repo in repositories:
        repo_name = repo['repositoryName']
        print(f"Repository: {repo_name}")

        old_images = get_tagged_images_in_repo(repo_name)

        if old_images:
            print(f"  Found {len(old_images)} tagged images older than {OLD_THRESHOLD_DAYS} days:")
            for img in old_images:
                tags_str = ', '.join(img['tags'])
                print(f"    - Tags: {tags_str}")
                print(f"      Digest: {img['digest'][:20]}...")  # shorten for readability
                print(f"      Pushed: {img['pushed_at']}")
                print(f"      Age: {img['age_days']} days")
                print()
        else:
            print("  No old tagged images found (or no tagged images at all).")
        print("-" * 60)

print("Scan complete.")