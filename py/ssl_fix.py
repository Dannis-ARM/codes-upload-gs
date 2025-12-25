import ssl

# 1. 备份原有的创建上下文函数
original_create_default_context = ssl.create_default_context

# 2. 定义一个新的函数，强制设置安全级别
def patched_create_default_context(*args, **kwargs):
    # 调用原函数创建一个标准的上下文
    context = original_create_default_context(*args, **kwargs)
    # 核心步骤：强制将加密级别降为 1 (允许 1024位 DH 密钥)
    # 如果 1 还不行，可以尝试设为 'DEFAULT'
    context.set_ciphers('DEFAULT@SECLEVEL=1')
    return context

# 3. 替换掉全局的创建函数
ssl.create_default_context = patched_create_default_context

# --- 现在再导入和使用 boto3 ---
import boto3
from botocore.config import Config

# 正常创建 client
s3 = boto3.client('s3', region_name='your-region')

# 测试连接
# response = s3.list_buckets()