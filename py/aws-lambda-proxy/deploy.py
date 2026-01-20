"""
Converts the deploy.sh script to a Python script for deploying the Lambda proxy.

This script packages a Lambda function, uploads it and a CloudFormation template to S3,
and then creates or updates the CloudFormation stack.
"""
import argparse
import logging
import shutil
import sys
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, WaiterError

# Configure a named logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set default level

# Create a stream handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO) # Set handler level

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

def parse_arguments():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Deploy AWS Lambda proxy via CloudFormation.")
    parser.add_argument("stack_name", help="The name of the CloudFormation stack.")
    parser.add_argument("template_file", help="Path to the CloudFormation template file.")
    parser.add_argument("s3_bucket", help="S3 bucket for artifacts.")
    parser.add_argument("region", help="AWS region for deployment.")
    parser.add_argument("update_worker_arn", help="ARN for the update worker Lambda.")
    parser.add_argument("fetch_worker_arn", help="ARN for the fetch worker Lambda.")
    parser.add_argument("vpc_id", help="VPC ID for the private API endpoint.")
    parser.add_argument("security_group_id", help="Security Group ID for the Lambda.")
    parser.add_argument("subnet_ids", help="Comma-separated Subnet IDs for the Lambda.")
    return parser.parse_args()

def package_lambda(source_file: Path, dist_dir: Path) -> Path:
    """Packages the lambda source code into a zip file."""
    logger.info("Packaging Lambda function...")
    dist_dir.mkdir(exist_ok=True)
    zip_path = dist_dir / f"{source_file.stem}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(source_file, arcname=source_file.name)
    logger.info(f"Lambda function packaged at {zip_path}")
    return zip_path

def upload_to_s3(s3_client, file_path: Path, bucket: str, key: str):
    """Uploads a file to an S3 bucket."""
    logger.info(f"Uploading {file_path} to s3://{bucket}/{key}...")
    try:
        s3_client.upload_file(str(file_path), bucket, key)
        logger.info("Upload successful.")
    except ClientError as e:
        logger.error(f"Failed to upload {file_path} to S3: {e}")
        raise

def get_stack_parameters(s3_bucket, s3_code_key, update_worker_arn, fetch_worker_arn, vpc_id, security_group_id, subnet_ids):
    """Returns the parameters for the CloudFormation stack."""
    return [
        {'ParameterKey': 'CodeS3Bucket', 'ParameterValue': s3_bucket},
        {'ParameterKey': 'CodeS3Key', 'ParameterValue': s3_code_key},
        {'ParameterKey': 'UpdateWorkerLambdaArn', 'ParameterValue': update_worker_arn},
        {'ParameterKey': 'FetchWorkerLambdaArn', 'ParameterValue': fetch_worker_arn},
        {'ParameterKey': 'VpcId', 'ParameterValue': vpc_id},
        {'ParameterKey': 'SecurityGroupId', 'ParameterValue': security_group_id},
        # The template expects a list, but the script passes a comma-separated string.
        # The CLI handles conversion, but for boto3 we pass it as a string.
        {'ParameterKey': 'SubnetIds', 'ParameterValue': subnet_ids},
    ]

def stack_exists(cf_client, stack_name: str) -> bool:
    """Checks if a CloudFormation stack exists."""
    try:
        cf_client.describe_stacks(StackName=stack_name)
        return True
    except ClientError as e:
        if "does not exist" in e.response['Error']['Message']:
            return False
        else:
            raise

def destroy_stack(cf_client, stack_name: str):
    """Destroys a CloudFormation stack."""
    logger.info(f"Attempting to destroy CloudFormation stack '{stack_name}'...")
    try:
        if stack_exists(cf_client, stack_name):
            logger.info(f"Stack '{stack_name}' exists. Deleting...")
            cf_client.delete_stack(StackName=stack_name)
            waiter = cf_client.get_waiter('stack_delete_complete')
            waiter.wait(StackName=stack_name)
            logger.info(f"Stack '{stack_name}' destroyed.")
        else:
            logger.info(f"Stack '{stack_name}' does not exist, no need to destroy.")
    except (ClientError, WaiterError) as e:
        logger.error(f"Error destroying stack '{stack_name}': {e}")
        # Don't re-raise, just log the error during cleanup

def create_stack(cf_client, stack_name, template_url, parameters):
    """Creates a CloudFormation stack."""
    logger.info(f"Creating CloudFormation stack '{stack_name}'...")
    try:
        cf_client.create_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=parameters,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
        )
        waiter = cf_client.get_waiter('stack_create_complete')
        logger.info("Waiting for stack creation to complete...")
        waiter.wait(StackName=stack_name)
        logger.info(f"Stack '{stack_name}' created successfully.")
    except (ClientError, WaiterError) as e:
        logger.error(f"Failed to create stack '{stack_name}'.")
        raise e

def update_stack(cf_client, stack_name, template_url, parameters):
    """Updates a CloudFormation stack."""
    logger.info(f"Updating CloudFormation stack '{stack_name}'...")
    try:
        cf_client.update_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=parameters,
            Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
        )
        waiter = cf_client.get_waiter('stack_update_complete')
        logger.info("Waiting for stack update to complete...")
        waiter.wait(StackName=stack_name)
        logger.info(f"Stack '{stack_name}' updated successfully.")
    except WaiterError as e:
        logger.error(f"Failed to update stack '{stack_name}'.")
        raise e
    except ClientError as e:
        if "No updates are to be performed" in e.response['Error']['Message']:
            logger.info(f"No changes detected for stack '{stack_name}'. Update not needed.")
        else:
            logger.error(f"Failed to update stack '{stack_name}'.")
            raise e

def main():
    """Main function to orchestrate the deployment."""
    args = parse_arguments()
    
    # Store args in local variables for clarity and easier maintenance
    stack_name = args.stack_name
    template_file_str = args.template_file
    s3_bucket = args.s3_bucket
    region = args.region
    update_worker_arn = args.update_worker_arn
    fetch_worker_arn = args.fetch_worker_arn
    vpc_id = args.vpc_id
    security_group_id = args.security_group_id
    subnet_ids = args.subnet_ids

    # Define paths
    source_file = Path("main.py")
    template_file = Path(template_file_str)
    dist_dir = Path("dist")

    if not source_file.exists():
        logger.error(f"Source file '{source_file}' not found.")
        sys.exit(1)
    if not template_file.exists():
        logger.error(f"Template file '{template_file}' not found.")
        sys.exit(1)

    # Define S3 keys
    zip_file_name = "main.py.zip" # Keep consistent with shell script
    s3_code_key = f"lambda-code/{zip_file_name}"
    s3_template_key = f"cfn-templates/{template_file.name}"
    
    try:
        # 1. Package
        zip_path = package_lambda(source_file, dist_dir)
        
        # 2. Upload
        s3_client = boto3.client('s3', region_name=region)
        upload_to_s3(s3_client, zip_path, s3_bucket, s3_code_key)
        upload_to_s3(s3_client, template_file, s3_bucket, s3_template_key)
        
        # 3. Deploy
        cf_client = boto3.client('cloudformation', region_name=region)
        template_url = f"https://s3.{region}.amazonaws.com/{s3_bucket}/{s3_template_key}"

        parameters = get_stack_parameters(s3_bucket, s3_code_key, update_worker_arn, fetch_worker_arn, vpc_id, security_group_id, subnet_ids)
        
        if stack_exists(cf_client, stack_name):
            logger.info(f"Stack '{stack_name}' exists. Attempting to update...")
            try:
                update_stack(cf_client, stack_name, template_url, parameters)
            except (ClientError, WaiterError) as e:
                logger.error(f"Stack update failed: {e}. Please check the stack events for more details.")
                sys.exit(1)
        else:
            logger.info(f"Stack '{stack_name}' does not exist. Attempting to create...")
            try:
                create_stack(cf_client, stack_name, template_url, parameters)
            except (ClientError, WaiterError) as e:
                logger.error(f"Initial stack creation failed: {e}. Attempting to clean up by deleting the stack.")
                destroy_stack(cf_client, stack_name)
                sys.exit(1)

        logger.info(f"Deployment of stack '{stack_name}' complete.")

    except (ClientError, WaiterError) as e:
        logger.error(f"An unexpected AWS API error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        # 4. Cleanup
        if dist_dir.exists():
            logger.info("Cleaning up...")
            shutil.rmtree(dist_dir)
            logger.info("Done.")

if __name__ == "__main__":
    main()
