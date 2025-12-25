import ssl
import boto3
import urllib3
from botocore.config import Config

# 1. 定义宽松的 SSL Context
def get_lenient_context():
    # 使用 PROTOCOL_TLS_CLIENT 以获得最佳兼容性
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # 强制接受低强度密钥和自签名证书
    ctx.set_ciphers('DEFAULT@SECLEVEL=0')
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# 2. 找到真正的 HTTPSConnection 类并进行劫持
# 在 urllib3 中，HTTPSConnectionPool 内部使用 ConnectionCls 来建立连接
try:
    # 尝试从 connection 模块获取，这是 1.26+ 和 2.x 的标准位置
    from urllib3.connection import HTTPSConnection
except ImportError:
    # 兼容极老版本
    from urllib3.connectionpool import HTTPSConnection

# 记录原始的初始化方法
orig_init = HTTPSConnection.__init__

def patched_init(self, *args, **kwargs):
    # 核心逻辑：无论外部传什么，强制注入我们宽松的 context
    kwargs['ssl_context'] = get_lenient_context()
    # 移除可能冲突的参数（防止多次设置 verify）
    kwargs.pop('cert_reqs', None)
    orig_init(self, *args, **kwargs)

# 应用猴子补丁
HTTPSConnection.__init__ = patched_init

# 3. 正常使用 Boto3
# 此时即使你不写 verify=False，补丁也会强制跳过验证并允许小 DH Key
s3_client = boto3.client(
    's3',
    endpoint_url='https://你的_obsv2_endpoint',
    aws_access_key_id='YOUR_AK',
    aws_secret_access_key='YOUR_SK',
    config=Config(signature_version='s3v4')
)

try:
    print("正在尝试连接 OBS...")
    print(s3_client.list_buckets())
except Exception as e:
    print(f"连接失败: {e}")