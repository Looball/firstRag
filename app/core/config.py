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

# 大语言模型配置。保留 DEEPSEEK_API_KEY 作为旧配置的兼容回退。
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek").strip().lower()
LLM_MODEL = os.environ.get("LLM_MODEL")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get(
    "DEEPSEEK_API_KEY"
)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "8000"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))

# 用户自带 API Key 的加密主密钥，必须与 JWT 密钥分离配置。
USER_SETTINGS_ENCRYPTION_KEY = os.environ.get(
    "USER_SETTINGS_ENCRYPTION_KEY"
)
ALLOW_USER_CUSTOM_LLM_BASE_URL = os.environ.get(
    "ALLOW_USER_CUSTOM_LLM_BASE_URL",
    "false",
).lower() == "true"
