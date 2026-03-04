import boto3
import json
import datetime
import logging
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_env_info(context):
    """Extract Region and Account ID from Lambda context."""
    try:
        arn_parts = context.invoked_function_arn.split(':')
        return {
            'region': arn_parts[3],
            'account_id': arn_parts[4]
        }
    except (IndexError, AttributeError) as e:
        logger.error(f"Failed to parse context ARN: {e}")
        raise

def is_repo_compliant(ecr_client, repo_name, max_days=90):
    """Check all images in a repository for compliance based on push date."""
    now = datetime.datetime.now(datetime.timezone.utc)
    paginator = ecr_client.get_paginator('describe_images')
    
    try:
        for page in paginator.paginate(repositoryName=repo_name):
            for image in page.get('imageDetails', []):
                push_date = image.get('imagePushedAt')
                if not push_date:
                    continue
                
                age = (now - push_date).days
                if age > max_days:
                    msg = f"Non-compliant: Image {image.get('imageDigest')} pushed {age} days ago."
                    return False, msg
        
        return True, "Compliant: All images are within the 90-day limit."
    except ClientError as e:
        logger.error(f"Error describing images for repo {repo_name}: {e}")
        return None, f"Error: {str(e)}"

def submit_evaluation(config_client, resource_id, compliance_type, annotation, event):
    """Submit the evaluation result back to AWS Config."""
    try:
        invoking_event = json.loads(event['invoking_event'])
        result_token = event['resultToken']
        
        config_client.put_evaluations(
            Evaluations=[{
                'ComplianceResourceType': 'AWS::ECR::Repository',
                'ComplianceResourceId': resource_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': invoking_event['notificationCreationTime']
            }],
            ResultToken=result_token
        )
        logger.info(f"Successfully submitted {compliance_type} for {resource_id}")
    except ClientError as e:
        logger.error(f"Failed to submit evaluation for {resource_id}: {e}")

# --- Main Entry Point ---
def lambda_handler(event, context):
    """Main Lambda function for AWS Config Custom Rule."""
    logger.info("Starting ECR compliance scan...")
    
    # 1. Setup environment and clients
    env = get_env_info(context)
    ecr_client = boto3.client('ecr', region_name=env['region'])
    config_client = boto3.client('config', region_name=env['region'])
    
    # 2. List all ECR repositories using paginator
    try:
        repo_paginator = ecr_client.get_paginator('describe_repositories')
        for repo_page in repo_paginator.paginate():
            for repo in repo_page.get('repositories', []):
                repo_name = repo['repositoryName']
                
                # 3. Perform the compliance check
                is_compliant, message = is_repo_compliant(ecr_client, repo_name)
                
                # Skip if there was an error during image check
                if is_compliant is None:
                    continue
                
                status = 'COMPLIANT' if is_compliant else 'NON_COMPLIANT'
                
                # 4. Report results
                submit_evaluation(config_client, repo_name, status, message, event)
                
    except ClientError as e:
        logger.error(f"Critical error listing repositories: {e}")
        return {'statusCode': 500, 'body': str(e)}

    logger.info("Scan completed successfully.")
    return {'statusCode': 200, 'body': 'Evaluation complete'}