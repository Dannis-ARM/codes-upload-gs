import ssl
import boto3
from botocore.config import Config
from botocore.httpsession import URLLib3Session

# 1. 创建一个完全自定义的 SSL Context
custom_context = ssl.create_default_context()
custom_context.check_hostname = False
custom_context.verify_mode = ssl.CERT_NONE

# 2. 强制设置加密套件和安全级别
# SECLEVEL=0 是 OpenSSL 的底线，允许一切过时的算法
custom_context.set_ciphers('DEFAULT@SECLEVEL=0')

# 3. 核心黑科技：通过 Boto3 的事件系统注入
# 虽然 Config 不直接支持，但我们可以通过这种方式强制 Boto3 使用我们的 context
def add_custom_ssl_context(request, **kwargs):
    # 这里直接修改请求对象的上下文（如果底层支持）
    pass

# 如果上面的方法太麻烦，试试最直接的：修改 botocore 源码级别的默认值
import botocore.httpsession
orig_init = botocore.httpsession.URLLib3Session.__init__

def new_init(self, *args, **kwargs):
    # 强制在初始化时注入我们宽松的 verify 逻辑
    kwargs['verify'] = False 
    orig_init(self, *args, **kwargs)

botocore.httpsession.URLLib3Session.__init__ = new_init