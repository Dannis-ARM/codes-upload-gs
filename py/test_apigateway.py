import boto3
import json
import logging

logging.basicConfig(level=logging.INFO)

def create_lambda_function(
    function_name: str,
    py_version: str,
    vpc_id: str,
    subnet_ids: list,
    sg_ids: list,
    execution_role_arn: str,
    handler: str = "lambda_function.lambda_handler",
    description: str = "Created via boto3",
    memory_size: int = 128,
    timeout: int = 30
):
    """
    Create AWS Lambda function with VPC configuration using boto3
    Supports Python 3.8~3.12, VPC, Subnets, Security Groups
    """
    lambda_client = boto3.client("lambda")

    # Minimal hello world code
    code_content = """
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": "Hello from Private Lambda"
    }
"""

    try:
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime=py_version,
            Role=execution_role_arn,
            Handler=handler,
            Code={
                "ZipFile": code_content.encode("utf-8")
            },
            Description=description,
            MemorySize=memory_size,
            Timeout=timeout,
            VpcConfig={
                "SubnetIds": subnet_ids,
                "SecurityGroupIds": sg_ids
            },
            Publish=True
        )

        function_arn = response["FunctionArn"]
        logging.info(f"Lambda created: {function_arn}")
        return response

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise


# ------------------------------
# Example Usage
# ------------------------------
if __name__ == "__main__":
    create_lambda_function(
        function_name="my-private-lambda",
        py_version="python3.12",
        vpc_id="vpc-12345678",
        subnet_ids=["subnet-111111", "subnet-222222"],
        sg_ids=["sg-111111"],
        execution_role_arn="arn:aws:iam::123456789012:role/lambda-execution-role"
    )