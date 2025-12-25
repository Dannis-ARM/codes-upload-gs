import ssl
import urllib3.connectionpool
import boto3
from botocore.config import Config

# 1. 创建一个极致宽松的 SSL Context
# 既解决了 self-signed 证书问题，也解决了 dh key too small 问题
def create_lenient_context(*args, **kwargs):
    # 使用最高兼容性协议
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # 关键：降低安全级别到 0，并禁用 DH 算法作为双重保险
    ctx.set_ciphers('DEFAULT@SECLEVEL=0:!DH')
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# 2. 猴子补丁：劫持 urllib3 的连接池
# 强制让所有的 HTTPS 连接都使用我们这个特殊的 context
orig_HTTPSConnection = urllib3.connectionpool.HTTPSConnection
class PatchedHTTPSConnection(orig_HTTPSConnection):
    def __init__(self, *args, **kwargs):
        # 注入我们自定义的 context，不再让它读取系统默认严苛的配置
        kwargs['ssl_context'] = create_lenient_context()
        super().__init__(*args, **kwargs)

# 应用补丁
urllib3.connectionpool.HTTPSConnection = PatchedHTTPSConnection

# 3. 现在可以正常使用 boto3 了
# 注意：即便 verify=True 也会被我们的补丁强制改为不验证
s3 = boto3.client(
    's3',
    endpoint_url='https://你的_obsv2_endpoint',
    aws_access_key_id='YOUR_AK',
    aws_secret_access_key='YOUR_SK',
    config=Config(signature_version='s3v4') 
)

# 测试连接
response = s3.list_buckets()
print(response)