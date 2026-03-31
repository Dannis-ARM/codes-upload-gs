import urllib.request
import urllib.error
import json
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import os

# ===================== 【你只需要改这里】 =====================
API_ID = "你的API_ID"
REGION = "us-east-1"
STAGE = "prod"
RESOURCE_PATH = "test"  # 你的路由
METHOD = "GET"
BODY = b""  # POST 传 bytes，GET 空

# Private API 必须用内网域名
HOST = f"{API_ID}-{REGION}.vpce.amazonaws.com"
URL = f"https://{HOST}/{STAGE}/{RESOURCE_PATH}"

# ===================== Lambda 入口 =====================
def lambda_handler(event, context):
    # 1. 从 Lambda 环境自动拿凭证（官方推荐，最安全）
    creds = Credentials(
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        token=os.environ["AWS_SESSION_TOKEN"]
    )

    # 2. 构建 AWS 请求（给 botocore 签名用）
    aws_request = AWSRequest(
        method=METHOD,
        url=URL,
        data=BODY,
        headers={"Host": HOST}
    )

    # 3. ✅ 官方 SigV4 签名（核心！不手搓）
    sigv4 = SigV4Auth(creds, "execute-api", REGION)
    sigv4.add_auth(aws_request)  # 自动加 Authorization、X-Amz-Date、Token 等

    # 4. 把签好的 headers 丢给 urllib
    final_headers = dict(aws_request.headers)

    # ===================== urllib 发送请求 =====================
    try:
        req = urllib.request.Request(
            URL,
            data=BODY,
            headers=final_headers,
            method=METHOD
        )

        with urllib.request.urlopen(req, timeout=8) as resp:
            result = resp.read().decode("utf-8")
            print("✅ 调用成功：", result)
            return {"statusCode": 200, "body": result}

    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"❌ 错误 {e.code}: {err}")
        return {"statusCode": e.code, "body": err}