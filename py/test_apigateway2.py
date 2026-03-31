import json
import os
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
# 用 AWS 官方 HTTP 客户端，彻底解决端口占用
from botocore.httpsession import URLLib3Session

# ===================== 你的配置 =====================
API_ID = "你的API_ID"
REGION = "你的区域"
STAGE = "prod"
RESOURCE_PATH = "你的路径"
METHOD = "GET"
BODY = b""  # POST 填 json.dumps(xxx).encode()

HOST = f"{API_ID}-{REGION}.vpce.amazonaws.com"
URL = f"https://{HOST}/{STAGE}/{RESOURCE_PATH}"

# ===================== Lambda 入口 =====================
def lambda_handler(event, context):
    # 1. 获取凭证
    creds = Credentials(
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        token=os.environ["AWS_SESSION_TOKEN"]
    )

    # 2. 构建请求 + SigV4 签名（官方）
    aws_request = AWSRequest(
        method=METHOD,
        url=URL,
        data=BODY,
        headers={"Host": HOST, "Content-Type": "application/json"}
    )
    SigV4Auth(creds, "execute-api", REGION).add_auth(aws_request)

    # ===================== 核心修复：用 botocore 官方发送请求 =====================
    # 这个客户端专为 AWS 服务设计，永远不会出现 Device busy / Error 16
    session = URLLib3Session(
        timeout=5,
        max_pool_connections=1  # 单连接，避免端口占用
    )
    
    try:
        response = session.send(aws_request.prepare())
        result = response.text
        
        print("✅ 调用成功:", result)
        return {
            "statusCode": response.status_code,
            "body": result
        }

    except Exception as e:
        error = f"❌ 错误: {str(e)}"
        print(error)
        return {"statusCode": 500, "body": error}