import os
from pathlib import Path


# 设置文件存储路径
UPLOAD_ROOT = Path("./uploads")

# 设置JWT配置信息，环境变量中需要有 JWT_SECRET_KEY
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
