import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

lambda_client = boto3.client("lambda")

DEFAULT_CODE = """
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": "Lambda connected to VPC & Private API Gateway"
    }
""".encode("utf-8")

def deploy_lambda(
    function_name: str,
    runtime: str,
    role_arn: str,
    subnet_ids: list[str],
    security_group_ids: list[str],
    handler: str = "lambda_function.lambda_handler",
    memory_size: int = 128,
    timeout: int = 30,
    code_zip: bytes = DEFAULT_CODE
):
    """
    Reusable deploy function:
    - CREATE if Lambda does NOT exist
    - UPDATE configuration + code if Lambda ALREADY exists
    """

    config_params = {
        "Runtime": runtime,
        "Role": role_arn,
        "VpcConfig": {
            "SubnetIds": subnet_ids,
            "SecurityGroupIds": security_group_ids
        },
        "MemorySize": memory_size,
        "Timeout": timeout,
    }

    try:
        # Try to get existing Lambda
        lambda_client.get_function(FunctionName=function_name)
        logger.info(f"Lambda {function_name} exists → updating...")

        # Update config
        lambda_client.update_function_configuration(
            FunctionName=function_name,** config_params
        )

        # Update code
        resp = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=code_zip,
            Publish=True
        )
        return resp

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.info(f"Lambda {function_name} not found → creating...")
            resp = lambda_client.create_function(
                FunctionName=function_name,
                Handler=handler,
                Code={"ZipFile": code_zip},
                **config_params,
                Publish=True
            )
            return resp
        else:
            logger.error(f"Error: {e}")
            raise