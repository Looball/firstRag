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


def read_float_env(name: str, default: float) -> float:
    """读取浮点数环境变量，非法值回退到默认配置。"""
    try:
        return float(os.environ.get(name, str(default)))
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
CHAT_ATTACHMENT_ROOT = UPLOAD_ROOT / "chat_attachments"

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

# 扫描 PDF OCR 配置。仅原生文本不足的页面进入本地 Tesseract，避免普通
# PDF 承担额外 CPU 开销；最大页数与超时用于限制公开环境中的资源占用。
PDF_OCR_ENABLED = read_bool_env("PDF_OCR_ENABLED", True)
PDF_OCR_LANGUAGES = os.environ.get(
    "PDF_OCR_LANGUAGES",
    "chi_sim+eng",
).strip() or "chi_sim+eng"
PDF_OCR_DPI = read_int_env("PDF_OCR_DPI", 300)
PDF_OCR_TIMEOUT_SECONDS = read_int_env("PDF_OCR_TIMEOUT_SECONDS", 60)
PDF_OCR_MIN_NATIVE_TEXT_CHARACTERS = read_int_env(
    "PDF_OCR_MIN_NATIVE_TEXT_CHARACTERS",
    1,
)
PDF_OCR_MAX_PAGES = read_int_env("PDF_OCR_MAX_PAGES", 100)

# 限流配置。Docker/生产默认使用 Redis 分布式窗口；本地未显式配置时
# Redis 故障会 fail-open 到进程内限流，避免开发环境被基础设施阻塞。
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
_RATE_LIMIT_BACKEND_ENV = os.environ.get("RATE_LIMIT_BACKEND")
RATE_LIMIT_BACKEND = (
    _RATE_LIMIT_BACKEND_ENV
    or (
        "redis"
        if read_bool_env("REDIS_ENABLED", bool(os.environ.get("REDIS_URL")))
        else "memory"
    )
).strip().lower()
RATE_LIMIT_REDIS_FAILURE_MODE = os.environ.get(
    "RATE_LIMIT_REDIS_FAILURE_MODE",
    "fail_closed" if _RATE_LIMIT_BACKEND_ENV else "fail_open",
).strip().lower()
CHAT_IMAGE_MAX_FILES = read_int_env("CHAT_IMAGE_MAX_FILES", 3)
CHAT_IMAGE_MAX_FILE_SIZE_BYTES = read_int_env(
    "CHAT_IMAGE_MAX_FILE_SIZE_BYTES",
    5 * 1024 * 1024,
)
CHAT_IMAGE_MAX_TOTAL_BYTES = read_int_env(
    "CHAT_IMAGE_MAX_TOTAL_BYTES",
    15 * 1024 * 1024,
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
CHROMA_HOST = os.environ.get("CHROMA_HOST", "").strip()
CHROMA_PORT = read_int_env("CHROMA_PORT", 8000)
CHROMA_SSL = read_bool_env("CHROMA_SSL", False)

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

# Redis 基础设施配置。当前用于健康检查、RAG 热点缓存、分布式限流
# 和 vector worker 运行态观测。
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
REDIS_ENABLED = read_bool_env("REDIS_ENABLED", bool(REDIS_URL))
REDIS_CONNECT_TIMEOUT_SECONDS = read_float_env(
    "REDIS_CONNECT_TIMEOUT_SECONDS",
    1.0,
)
REDIS_COMMAND_TIMEOUT_SECONDS = read_float_env(
    "REDIS_COMMAND_TIMEOUT_SECONDS",
    1.0,
)
VECTOR_WORKER_HEARTBEAT_TTL_SECONDS = read_int_env(
    "VECTOR_WORKER_HEARTBEAT_TTL_SECONDS",
    30,
)
VECTOR_WORKER_FILE_LOCK_TTL_SECONDS = read_int_env(
    "VECTOR_WORKER_FILE_LOCK_TTL_SECONDS",
    15 * 60,
)
