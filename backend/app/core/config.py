import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


def resolve_project_path(value: str | os.PathLike[str], default: Path) -> Path:
    """将配置中的相对路径统一解析到项目根目录，避免受启动目录影响。"""
    path = Path(value or default)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_int_env(name: str, default: int) -> int:
    """读取整数环境变量，非法值回退到默认配置。"""
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def read_bool_env(name: str, default: bool) -> bool:
    """读取布尔环境变量，非法值回退到默认配置。"""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return default


# 设置文件存储路径
UPLOAD_ROOT = PROJECT_ROOT / "uploads"

# 设置上传文件大小限制，默认 200MB，与前端限制保持一致
MAX_UPLOAD_FILE_SIZE_BYTES = read_int_env(
    "MAX_UPLOAD_FILE_SIZE_BYTES",
    200 * 1024 * 1024,
)
USER_UPLOAD_MAX_FILES = read_int_env("USER_UPLOAD_MAX_FILES", 200)
USER_UPLOAD_MAX_BYTES = read_int_env(
    "USER_UPLOAD_MAX_BYTES",
    2 * 1024 * 1024 * 1024,
)
VECTOR_INDEX_MAX_BATCH_FILES = read_int_env(
    "VECTOR_INDEX_MAX_BATCH_FILES",
    100,
)

# 进程内限流配置。单机部署直接生效，多实例公网部署仍建议叠加网关限流。
LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS = read_int_env(
    "LOGIN_FAILURE_RATE_LIMIT_MAX_ATTEMPTS",
    5,
)
LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS = read_int_env(
    "LOGIN_FAILURE_RATE_LIMIT_WINDOW_SECONDS",
    300,
)
API_RATE_LIMIT_WINDOW_SECONDS = read_int_env(
    "API_RATE_LIMIT_WINDOW_SECONDS",
    60,
)
CHAT_RATE_LIMIT_MAX_REQUESTS = read_int_env(
    "CHAT_RATE_LIMIT_MAX_REQUESTS",
    60,
)
UPLOAD_RATE_LIMIT_MAX_REQUESTS = read_int_env(
    "UPLOAD_RATE_LIMIT_MAX_REQUESTS",
    20,
)
VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS = read_int_env(
    "VECTOR_INDEX_RATE_LIMIT_MAX_REQUESTS",
    30,
)
MODEL_TEST_RATE_LIMIT_MAX_REQUESTS = read_int_env(
    "MODEL_TEST_RATE_LIMIT_MAX_REQUESTS",
    20,
)

# 设置Chroma向量库存储路径和集合名称
VECTOR_STORE_PATH = resolve_project_path(
    os.environ.get("VECTOR_STORE_PATH", ""),
    PROJECT_ROOT / "vector_db/chroma",
)
CHROMA_COLLECTION_NAME = os.environ.get(
    "CHROMA_COLLECTION_NAME",
    "langchain",
)

# Rerank provider 历史环境变量兼容。新版本远程 rerank 推荐在
# 登录后的设置页按用户保存 provider/model/API Key。
RERANK_PROVIDER = os.environ.get("RERANK_PROVIDER", "local").strip().lower()
RERANK_MODEL = os.environ.get("RERANK_MODEL", "").strip()
RERANK_BASE_URL = os.environ.get("RERANK_BASE_URL", "").strip()
RERANK_INSTRUCT = os.environ.get("RERANK_INSTRUCT", "").strip()

# 设置本地 Cross-Encoder 精排序模型路径
RERANKER_MODEL_PATH = resolve_project_path(
    os.environ.get("RERANKER_MODEL_PATH", ""),
    PROJECT_ROOT / "models/rerankers/bge-reranker-base",
)

# 设置JWT配置信息，环境变量中需要有 JWT_SECRET_KEY
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
ALLOW_PUBLIC_REGISTRATION = read_bool_env("ALLOW_PUBLIC_REGISTRATION", True)

# 大语言模型生成参数默认值。provider、model 和 API Key 由用户登录后配置。
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "8000"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))

# 用户自带 API Key 的加密主密钥，必须与 JWT 密钥分离配置。
USER_SETTINGS_ENCRYPTION_KEY = os.environ.get(
    "USER_SETTINGS_ENCRYPTION_KEY"
)
ALLOW_USER_CUSTOM_LLM_BASE_URL = read_bool_env(
    "ALLOW_USER_CUSTOM_LLM_BASE_URL",
    False,
)
