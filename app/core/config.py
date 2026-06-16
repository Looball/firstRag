import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# 设置文件存储路径
UPLOAD_ROOT = Path("./uploads")

# 设置Chroma向量库存储路径和集合名称
VECTOR_STORE_PATH = Path(
    os.environ.get("VECTOR_STORE_PATH", "./vector_db/chroma")
)
CHROMA_COLLECTION_NAME = os.environ.get(
    "CHROMA_COLLECTION_NAME",
    "langchain",
)

# 设置JWT配置信息，环境变量中需要有 JWT_SECRET_KEY
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
