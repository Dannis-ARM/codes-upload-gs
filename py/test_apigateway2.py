import urllib.request
import urllib.error
import json
import hashlib
import hmac
import datetime
import os

# ===================== 【仅需修改这里】你的配置 =====================
API_ID = "你的API ID"
REGION = "us-east-1"       # 你的区域
STAGE = "prod"             # 部署阶段
RESOURCE_PATH = "your/path" # 资源路径（如 test）
METHOD = "GET"             # 请求方法
BODY = ""                  # POST 填 JSON 字符串，GET 填空

# Private API 必须用这个内网域名
API_URL = f"https://{API_ID}-{REGION}.vpce.amazonaws.com/{STAGE}/{RESOURCE_PATH}"
SERVICE = "execute-api"

# ===================== 签名工具函数 =====================
def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region, service):
    k_date = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, 'aws4_request')
    return k_signing

# ===================== Lambda 入口 =====================
def lambda_handler(event, context):
    # 1. 获取时间
    now = datetime.datetime.utcnow()
    amz_date = now.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = now.strftime('%Y%m%d')

    # 2. 从 Lambda 环境自动获取凭证（无需配置！）
    access_key = os.environ['AWS_ACCESS_KEY_ID']
    secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
    session_token = os.environ.get('AWS_SESSION_TOKEN')  # Lambda 一定会有这个

    # 3. 构建规范请求
    canonical_uri = f'/{STAGE}/{RESOURCE_PATH}'
    canonical_querystring = ''
    host = f"{API_ID}-{REGION}.vpce.amazonaws.com"
    canonical_headers = f'host:{host}\nx-amz-date:{amz_date}\n'
    signed_headers = 'host;x-amz-date'
    payload_hash = hashlib.sha256(BODY.encode('utf-8')).hexdigest()

    canonical_request = (
        f"{METHOD}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    # 4. 构建待签字符串
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = (
        f"{algorithm}\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
    )

    # 5. 生成签名
    signing_key = get_signature_key(secret_key, date_stamp, REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # 6. 构建 Authorization header
    auth_header = (
        f"{algorithm} "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    # 7. 请求头
    headers = {
        'Host': host,
        'X-Amz-Date': amz_date,
        'Authorization': auth_header,
        'X-Amz-Security-Token': session_token,  # Lambda 必须加这个！
        'Content-Type': 'application/json'
    }

    # ===================== 发送请求 =====================
    try:
        req = urllib.request.Request(
            API_URL,
            data=BODY.encode('utf-8') if BODY else None,
            headers=headers,
            method=METHOD
        )

        with urllib.request.urlopen(req, timeout=10) as res:
            result = res.read().decode('utf-8')
            print("✅ 调用成功：", result)
            return {
                'statusCode': 200,
                'body': json.dumps(json.loads(result), ensure_ascii=False)
            }

    except urllib.error.HTTPError as e:
        error = e.read().decode()
        print(f"❌ HTTP错误 {e.code}: {error}")
        return {'statusCode': e.code, 'body': error}

    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}