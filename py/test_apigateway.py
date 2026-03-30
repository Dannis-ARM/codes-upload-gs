import boto3
import io
import zipfile
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

lambda_client = boto3.client("lambda")

# VALID Lambda ZIP structure (critical fix for unzip error)
def create_lambda_zip(code: str) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", code)
    return zip_buffer.getvalue()

DEFAULT_LAMBDA_CODE = """
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": "VPC Lambda + Private API Gateway"
    }
"""

def deploy_lambda(
    function_name: str,
    runtime: str,
    role_arn: str,
    subnet_ids: list[str],
    security_group_ids: list[str],
    handler: str = "lambda_function.lambda_handler",
    memory_size: int = 128,
    timeout: int = 30
):
    code_zip = create_lambda_zip(DEFAULT_LAMBDA_CODE)
    
    config = {
        "Runtime": runtime,
        "Role": role_arn,
        "VpcConfig": {"SubnetIds": subnet_ids, "SecurityGroupIds": security_group_ids},
        "MemorySize": memory_size,
        "Timeout": timeout,
    }

    try:
        lambda_client.get_function(FunctionName=function_name)
        logger.info(f"Lambda exists → updating: {function_name}")
        
        lambda_client.update_function_configuration(FunctionName=function_name, **config)
        resp = lambda_client.update_function_code(
            FunctionName=function_name, ZipFile=code_zip, Publish=True
        )
        return resp

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"Creating new Lambda: {function_name}")
            resp = lambda_client.create_function(
                FunctionName=function_name,
                Handler=handler,
                Code={"ZipFile": code_zip},
                **config,
                Publish=True
            )
            return resp
        else:
            logger.error(f"Error: {e}")
            raise