import boto3
from botocore.exceptions import ClientError
import datetime


def execute_once(s3_client, bucket: str, lock_key: str, expire_seconds: int, task_func):
    """
    Execute a task exactly once across distributed servers using S3 atomic lock.
    Lock auto-expires after expire_seconds.
    
    Args:
        s3_client: boto3 S3 client
        bucket: S3 bucket name
        lock_key: unique lock path (e.g., ".locks/process_data")
        expire_seconds: lock expiration time in seconds
        task_func: function to run once (can return value)
    
    Returns:
        task result if executed, None if skipped
    """
    try:
        # Calculate expiration time
        expire_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=expire_seconds)
        
        # Atomic create lock: only if object does NOT exist
        s3_client.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=b"",  # empty content
            IfNoneMatch="*",
            Expires=expire_date
        )

        # Lock acquired: run the task and return result
        return task_func()

    except ClientError as e:
        # 412 = PreconditionFailed → lock already exists
        if e.response["ResponseMetadata"]["HTTPStatusCode"] == 412:
            return None
        
        # Re-raise other errors (network, permission, etc.)
        raise



# Initialize S3 client
s3 = boto3.client("s3")

# Define your task (can return any value)
def my_task():
    print("Running non-idempotent operation ONCE")
    # Your logic here: read S3, process, write DB...
    return {"status": "success", "id": 1001}

# Run once with 1-hour expiration lock
result = execute_once(
    s3_client=s3,
    bucket="your-bucket",
    lock_key=".locks/your-unique-task",
    expire_seconds=3600,
    task_func=my_task
)

# Check result
if result is not None:
    print("Task executed, result:", result)
else:
    print("Task skipped (already run by another server)")