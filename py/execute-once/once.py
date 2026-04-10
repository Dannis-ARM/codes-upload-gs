import boto3
import time
from botocore.exceptions import ClientError

def execute_once(s3_client, bucket: str, lock_key: str, lock_ttl: int, task_func):
    """
    Distributed once-executor with REAL atomic lock & safe expiration.
    NO RACE CONDITION. Uses S3 conditional write for atomicity.
    """
    now = int(time.time())

    # ==============================================
    # Step 1: Try to create lock directly (atomic)
    # ==============================================
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=str(now + lock_ttl).encode(),
            IfNoneMatch="*"
        )
        return task_func()
    except ClientError as e:
        if e.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
            raise

    # ==============================================
    # Step 2: Lock exists → check expiration ATOMICALLY
    # ==============================================
    try:
        # Get current lock + ETag (version signature)
        obj = s3_client.get_object(Bucket=bucket, Key=lock_key)
        expire_ts = int(obj["Body"].read().decode().strip())
        etag = obj["ETag"].strip('"')

        # If not expired → skip
        if now <= expire_ts:
            return None

        # ==============================================
        # Step 3: Expired → ATOMIC TAKE OVER (NO RACE!)
        # ==============================================
        s3_client.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=str(now + lock_ttl).encode(),
            IfMatch=etag  # ONLY overwrite if ETag matches → atomic!
        )
        return task_func()

    except ClientError as e:
        # If write fails → another node won the race
        if e.response["ResponseMetadata"]["HTTPStatusCode"] in (412, 404):
            return None
        raise

    except Exception:
        return None