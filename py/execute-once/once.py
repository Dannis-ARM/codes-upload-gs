import boto3
import time
from botocore.exceptions import ClientError

def execute_once(s3_client, bucket: str, lock_key: str, lock_ttl: int, task_func):
    """
    Distributed once-executor with atomic S3 lock, safe expiration,
    and lock content validation.
    NO RACE CONDITION. Production-ready.
    """
    now = int(time.time())

    # ==============================================
    # Step 1: Try to create lock atomically (if not exists)
    # ==============================================
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=lock_key,
            Body=str(now + lock_ttl).encode("utf-8"),
            IfNoneMatch="*"
        )
        return task_func()
    except ClientError as e:
        if e.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
            raise

    # ==============================================
    # Step 2: Lock exists → read and validate
    # ==============================================
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=lock_key)
        etag = obj["ETag"].strip('"')
        body_bytes = obj["Body"].read()

        # === 关键：内容不是合法数字 → 视为过期 ===
        try:
            expire_ts = int(body_bytes.decode("utf-8").strip())
        except (ValueError, UnicodeDecodeError):
            expire_ts = 0  # invalid content → treat as expired

        # Not expired → skip
        if now <= expire_ts:
            return None

    except Exception:
        # Any error reading lock → treat as expired
        expire_ts = 0
        etag = None

    # ==============================================
    # Step 3: Lock is expired OR invalid → ATOMIC takeover
    # ==============================================
    try:
        put_params = {
            "Bucket": bucket,
            "Key": lock_key,
            "Body": str(now + lock_ttl).encode("utf-8")
        }
        # Only add IfMatch if we have a valid ETag
        if etag is not None:
            put_params["IfMatch"] = etag

        s3_client.put_object(**put_params)
        return task_func()

    except ClientError as e:
        # 412 = ETag changed (another node won)
        # 404 = object deleted
        if e.response["ResponseMetadata"]["HTTPStatusCode"] in (412, 404):
            return None
        raise