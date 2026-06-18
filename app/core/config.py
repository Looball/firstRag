import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# 设置文件存储路径
UPLOAD_ROOT = Path("./uploads")

# 设置上传文件大小限制，默认 200MB，与前端限制保持一致
MAX_UPLOAD_FILE_SIZE_BYTES = int(
    os.environ.get("MAX_UPLOAD_FILE_SIZE_BYTES", str(200 * 1024 * 1024))
)

# 设置Chroma向量库存储路径和集合名称
VECTOR_STORE_PATH = Path(
    os.environ.get("VECTOR_STORE_PATH", "./vector_db/chroma")
)
CHROMA_COLLECTION_NAME = os.environ.get(
    "CHROMA_COLLECTION_NAME",
    "langchain",
)

# 设置本地 Cross-Encoder 精排序模型路径
RERANKER_MODEL_PATH = Path(
    os.environ.get(
        "RERANKER_MODEL_PATH",
        "models/rerankers/bge-reranker-base",
    )
)

# 设置JWT配置信息，环境变量中需要有 JWT_SECRET_KEY
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# 设置大模型 API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
