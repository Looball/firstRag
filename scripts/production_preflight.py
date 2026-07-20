#!/usr/bin/env python3
"""FirstRAG 生产部署前置检查入口。"""

from __future__ import annotations

import argparse
import base64
import binascii
import ipaddress
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_CONDA_ENV = "firstrag"
MIN_SECRET_LENGTH = 32
MIN_PASSWORD_LENGTH = 16

PLACEHOLDER_VALUES = {
    "firstrag-password",
    "password",
    "username:password",
    "replace-with-a-local-postgres-password",
    "replace-with-a-strong-postgres-password",
    "replace-with-a-random-secret",
    "replace-with-your-llm-api-key",
    "replace-with-your-deepseek-api-key",
    "replace-with-your-zhipu-api-key",
    "replace-with-your-dashscope-api-key",
    "replace-with-your-qwen-api-key",
    "replace-with-your-rerank-api-key",
    "replace-with-a-fernet-key",
}

LOOPBACK_PREFIXES = ("127.0.0.1:", "localhost:")
REDIS_ALLOWED_SCHEMES = {"redis", "rediss"}
REDIS_INTERNAL_HOSTS = {"redis", "localhost"}
REDIS_DEFAULT_PASSWORDS = {
    "admin",
    "changeme",
    "default",
    "firstrag",
    "firstrag-password",
    "password",
    "redis",
    "root",
    "123456",
}
BOOLEAN_ENV_VALUES = {
    "0",
    "1",
    "false",
    "true",
    "no",
    "yes",
    "off",
    "on",
}
CHROMA_COMPOSE_HOST = "chroma"
CHROMA_DEFAULT_PORT = 8000


@dataclass(frozen=True)
class ExternalCheck:
    """外部命令检查结果。"""

    name: str
    success: bool
    message: str


def build_arg_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="Run FirstRAG production deployment preflight checks.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Production dotenv file. Defaults to repository .env.",
    )
    parser.add_argument(
        "--conda-env",
        default=os.environ.get("FIRSTRAG_CONDA_ENV", DEFAULT_CONDA_ENV),
        help="Conda environment used by local migration dry-run.",
    )
    parser.add_argument(
        "--migration-method",
        choices=("compose", "local"),
        default="compose",
        help="Run migration dry-run through Docker Compose or local conda.",
    )
    parser.add_argument(
        "--skip-migration-dry-run",
        action="store_true",
        help="Skip migration dry-run when PostgreSQL is not reachable yet.",
    )
    parser.add_argument(
        "--skip-compose-check",
        action="store_true",
        help="Skip docker compose config validation.",
    )
    parser.add_argument(
        "--skip-path-check",
        action="store_true",
        help="Skip persistent directory checks.",
    )
    parser.add_argument(
        "--check-runtime-health",
        action="store_true",
        help="Require the Compose Chroma service to be running and healthy.",
    )
    parser.add_argument(
        "--require-provider-keys",
        action="store_true",
        help=(
            "Require remote rerank provider keys when remote rerank is enabled."
        ),
    )
    parser.add_argument(
        "--require-reranker",
        action="store_true",
        help="Require local CrossEncoder reranker model files before smoke tests.",
    )
    return parser


def normalize_env_value(raw_value: str) -> str:
    """移除 dotenv 值两侧空白和一层引号。"""
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(env_file: Path) -> dict[str, str]:
    """读取 dotenv 文件，不执行 shell 语法，也不输出变量值。"""
    if not env_file.exists():
        raise FileNotFoundError(f"环境文件不存在：{env_file}")

    values: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        values[key] = normalize_env_value(raw_value)
    return values


def build_runtime_env(env_file: Path) -> dict[str, str]:
    """合并 dotenv 与当前进程环境，进程环境优先。"""
    env = load_env_file(env_file)
    env.update(os.environ)
    return env


def is_placeholder(value: str | None) -> bool:
    """判断配置值是否仍是模板占位值。"""
    if value is None:
        return True

    normalized = value.strip().lower()
    if not normalized:
        return True
    if normalized in PLACEHOLDER_VALUES:
        return True
    return normalized.startswith("replace-with-")


def is_valid_fernet_key(value: str) -> bool:
    """校验 Fernet key 的 base64 形态，不解密任何用户数据。"""
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
    except (binascii.Error, ValueError):
        return False
    return len(decoded) == 32


def require_secret(
    env: Mapping[str, str],
    key: str,
    errors: list[str],
    *,
    min_length: int = MIN_SECRET_LENGTH,
) -> None:
    """校验必填 secret 存在、不是占位值且长度达标。"""
    value = env.get(key)
    if is_placeholder(value):
        errors.append(f"{key} 必须通过生产环境变量或 secret 注入，不能使用模板占位值。")
        return
    if len(value or "") < min_length:
        errors.append(f"{key} 长度过短，请使用生产级随机值。")


def validate_secret_settings(env: Mapping[str, str]) -> list[str]:
    """校验启动必需的生产密钥最低要求。"""
    errors: list[str] = []

    require_secret(env, "POSTGRES_PASSWORD", errors, min_length=MIN_PASSWORD_LENGTH)
    require_secret(env, "JWT_SECRET_KEY", errors)
    require_secret(env, "USER_SETTINGS_ENCRYPTION_KEY", errors)

    encryption_key = env.get("USER_SETTINGS_ENCRYPTION_KEY", "")
    jwt_secret = env.get("JWT_SECRET_KEY", "")
    if encryption_key and not is_placeholder(encryption_key):
        if not is_valid_fernet_key(encryption_key):
            errors.append("USER_SETTINGS_ENCRYPTION_KEY 必须是有效 Fernet key。")
        if jwt_secret and encryption_key == jwt_secret:
            errors.append("USER_SETTINGS_ENCRYPTION_KEY 必须与 JWT_SECRET_KEY 分离。")

    return errors


def has_configured_value(value: str | None) -> bool:
    """判断可选配置是否实际填写了非空值。"""
    return bool(value and value.strip())


def normalize_optional_provider(value: str | None, default: str) -> str:
    """归一化可选 provider 名称，供 preflight 做轻量校验。"""
    return (value or default).strip().lower()


def has_any_configured_key(env: Mapping[str, str], keys: Sequence[str]) -> bool:
    """判断一组可选 Key 中是否至少配置了一个真实值。"""
    return any(
        has_configured_value(env.get(key)) and not is_placeholder(env.get(key))
        for key in keys
    )


def validate_optional_api_keys(
    env: Mapping[str, str],
    keys: Sequence[str],
    errors: list[str],
) -> None:
    """校验一组可选 API Key 不应填写占位值或明显过短值。"""
    for key in keys:
        value = env.get(key)
        if not has_configured_value(value):
            continue
        if is_placeholder(value):
            errors.append(f"{key} 仍是占位值，请留空或替换为真实 provider Key。")
        elif len((value or "").strip()) < 12:
            errors.append(f"{key} 长度过短，请确认是否为真实 provider Key。")


def validate_optional_provider_settings(
    env: Mapping[str, str],
    *,
    require_provider_keys: bool = False,
) -> list[str]:
    """校验仍通过环境变量配置的可选远程 rerank provider。"""
    errors: list[str] = []

    rerank_provider = normalize_optional_provider(
        env.get("RERANK_PROVIDER"),
        "local",
    )
    qwen_rerank_keys = (
        "RERANK_API_KEY",
        "DASHSCOPE_API_KEY",
        "QWEN_API_KEY",
    )
    validate_optional_api_keys(env, qwen_rerank_keys, errors)
    if rerank_provider in {"qwen", "dashscope", "aliyun", "aliyun-qwen"}:
        rerank_base_url = env.get("RERANK_BASE_URL", "")
        if has_configured_value(rerank_base_url) and is_placeholder(rerank_base_url):
            errors.append("RERANK_BASE_URL 仍是占位值，请替换为阿里云工作空间地址。")
        if require_provider_keys:
            if not has_any_configured_key(env, qwen_rerank_keys):
                errors.append("公开 smoke test 前需要配置阿里云 rerank Key。")
            if not has_configured_value(rerank_base_url):
                errors.append("公开 smoke test 前需要配置 RERANK_BASE_URL。")

    return errors


def validate_database_settings(env: Mapping[str, str]) -> list[str]:
    """校验数据库连接配置不含模板值。"""
    errors: list[str] = []
    database_url = env.get("DATABASE_URL", "")
    compose_database_url = env.get("COMPOSE_DATABASE_URL", "")

    if database_url and (
        "username:password" in database_url
        or "replace-with-" in database_url.lower()
    ):
        errors.append("DATABASE_URL 仍包含模板账号或密码，请删除或改为生产连接串。")

    if compose_database_url and "replace-with-" in compose_database_url.lower():
        errors.append("COMPOSE_DATABASE_URL 仍包含模板密码，请改为生产连接串。")

    return errors


def parse_bool_env(value: str | None, default: bool = False) -> bool:
    """解析 dotenv 布尔值，非法值回退到默认值。"""
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def is_internal_redis_host(hostname: str | None) -> bool:
    """判断 Redis host 是否看起来是 Compose/内网地址。"""
    if not hostname:
        return False

    normalized = hostname.strip().strip("[]").lower()
    if normalized in REDIS_INTERNAL_HOSTS:
        return True
    if normalized.endswith((".internal", ".local", ".lan")):
        return True

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False

    return address.is_private or address.is_loopback or address.is_link_local


def validate_redis_settings(env: Mapping[str, str]) -> list[str]:
    """校验 Redis 生产配置、安全边界和限流故障策略。"""
    errors: list[str] = []
    redis_url = (env.get("REDIS_URL") or "").strip()
    redis_enabled = parse_bool_env(
        env.get("REDIS_ENABLED"),
        bool(redis_url),
    )
    rate_limit_backend = (env.get("RATE_LIMIT_BACKEND") or "").strip().lower()
    if not rate_limit_backend:
        rate_limit_backend = "redis" if redis_enabled else "memory"
    failure_mode = (
        env.get("RATE_LIMIT_REDIS_FAILURE_MODE") or "fail_closed"
    ).strip().lower()

    if rate_limit_backend not in {"redis", "memory"}:
        errors.append("RATE_LIMIT_BACKEND 只能设置为 redis 或 memory。")
    if failure_mode not in {"fail_open", "fail_closed"}:
        errors.append("RATE_LIMIT_REDIS_FAILURE_MODE 只能设置为 fail_open 或 fail_closed。")
    if rate_limit_backend == "redis" and not redis_enabled:
        errors.append("RATE_LIMIT_BACKEND=redis 时必须启用 REDIS_ENABLED。")
    if rate_limit_backend == "redis" and failure_mode != "fail_closed":
        errors.append("生产环境使用 Redis 限流时 RATE_LIMIT_REDIS_FAILURE_MODE 必须为 fail_closed。")

    if not redis_enabled:
        return errors

    if is_placeholder(redis_url) or "replace-with-" in redis_url.lower():
        errors.append("REDIS_URL 不能使用模板占位值。")
        return errors

    try:
        parsed_url = urlsplit(redis_url)
    except ValueError:
        errors.append("REDIS_URL 格式无效。")
        return errors

    if parsed_url.scheme not in REDIS_ALLOWED_SCHEMES:
        errors.append("REDIS_URL 只支持 redis:// 或 rediss://。")
    if not parsed_url.hostname:
        errors.append("REDIS_URL 必须包含 Redis host。")

    password = parsed_url.password or ""
    if password:
        normalized_password = password.strip().lower()
        if is_placeholder(password) or normalized_password in REDIS_DEFAULT_PASSWORDS:
            errors.append("REDIS_URL 不能使用默认、弱口令或模板 Redis 密码。")
        elif len(password) < 12:
            errors.append("REDIS_URL 中的 Redis 密码过短，请使用生产级随机值。")
    elif parsed_url.hostname and not is_internal_redis_host(parsed_url.hostname):
        errors.append("REDIS_URL 指向外部 Redis 时必须使用带认证的连接串。")

    redis_port = (env.get("REDIS_PORT") or "").strip()
    if redis_port:
        if not redis_port.startswith(LOOPBACK_PREFIXES):
            errors.append("REDIS_PORT 如需暴露只能绑定到 127.0.0.1 或 localhost；生产不应公网暴露 Redis。")

    return errors


def is_internal_chroma_host(hostname: str) -> bool:
    """判断 Chroma host 是否是 Compose service、内网域名或私网地址。"""
    normalized = hostname.strip().strip("[]").lower()
    if normalized == CHROMA_COMPOSE_HOST:
        return True
    if "." not in normalized and ":" not in normalized:
        return True
    if normalized.endswith((".internal", ".local", ".lan")):
        return True

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False

    return address.is_private or address.is_link_local


def validate_chroma_settings(env: Mapping[str, str]) -> list[str]:
    """校验 Chroma client-server 连接配置和生产传输边界。"""
    errors: list[str] = []
    host = (env.get("CHROMA_HOST") or CHROMA_COMPOSE_HOST).strip()
    normalized_host = host.strip("[]").lower()
    port_value = (env.get("CHROMA_PORT") or str(CHROMA_DEFAULT_PORT)).strip()
    ssl_value = (env.get("CHROMA_SSL") or "false").strip().lower()

    if "://" in host or "/" in host:
        errors.append("CHROMA_HOST 只能填写 host，不能包含 URL scheme 或路径。")
    elif normalized_host in {"localhost", "127.0.0.1", "::1"}:
        errors.append(
            "Compose 中 CHROMA_HOST 不能使用 localhost/loopback，"
            "应使用 chroma service 名称。"
        )

    try:
        port = int(port_value)
    except ValueError:
        errors.append("CHROMA_PORT 必须是 1-65535 的整数。")
    else:
        if port < 1 or port > 65535:
            errors.append("CHROMA_PORT 必须是 1-65535 的整数。")

    if ssl_value not in BOOLEAN_ENV_VALUES:
        errors.append("CHROMA_SSL 只能设置为 true/false、1/0、yes/no 或 on/off。")
    elif not is_internal_chroma_host(normalized_host) and not parse_bool_env(
        ssl_value,
    ):
        errors.append("CHROMA_HOST 指向外部地址时必须启用 CHROMA_SSL。")

    return errors


def extract_compose_service_block(compose_text: str, service_name: str) -> str | None:
    """从 docker-compose.yml 文本中提取指定 service 的缩进块。"""
    pattern = re.compile(rf"^  {re.escape(service_name)}:\s*$", re.MULTILINE)
    match = pattern.search(compose_text)
    if match is None:
        return None

    start = match.start()
    next_match = re.search(r"^  [A-Za-z0-9_-]+:\s*$", compose_text[match.end():], re.MULTILINE)
    if next_match is None:
        return compose_text[start:]
    return compose_text[start:match.end() + next_match.start()]


def validate_compose_redis_service(
    compose_file: Path = PROJECT_ROOT / "docker-compose.yml",
) -> list[str]:
    """静态校验 Compose Redis service 不公网暴露并带 healthcheck。"""
    errors: list[str] = []
    if not compose_file.exists():
        return ["docker-compose.yml 不存在，无法检查 Redis service。"]

    compose_text = compose_file.read_text(encoding="utf-8")
    redis_block = extract_compose_service_block(compose_text, "redis")
    if redis_block is None:
        return ["docker-compose.yml 缺少 redis service。"]

    if "\n    ports:" in redis_block:
        errors.append("redis service 不应配置 ports；生产 Redis 不应直接暴露到宿主机公网。")
    if "\n    healthcheck:" not in redis_block:
        errors.append("redis service 必须配置 healthcheck。")
    if "redis-cli" not in redis_block or "ping" not in redis_block:
        errors.append("redis healthcheck 应使用 redis-cli ping 这类轻量检查。")
    if "\n    logging:" not in redis_block:
        errors.append("redis service 应复用 Docker 日志轮转配置。")

    return errors


def validate_compose_chroma_service(
    compose_file: Path = PROJECT_ROOT / "docker-compose.yml",
) -> list[str]:
    """静态校验 Compose Chroma service 和 backend/worker client-server 拓扑。"""
    errors: list[str] = []
    if not compose_file.exists():
        return ["docker-compose.yml 不存在，无法检查 Chroma service。"]

    compose_text = compose_file.read_text(encoding="utf-8")
    chroma_block = extract_compose_service_block(compose_text, "chroma")
    if chroma_block is None:
        return ["docker-compose.yml 缺少 chroma service。"]

    if "\n    ports:" in chroma_block:
        errors.append("chroma service 不应配置 ports；生产 Chroma 只能通过 Compose 内网访问。")
    if "\n    healthcheck:" not in chroma_block:
        errors.append("chroma service 必须配置 healthcheck。")
    if "8000" not in chroma_block:
        errors.append("chroma healthcheck 应检查 server 的 8000 端口或 heartbeat。")
    if "\n    logging:" not in chroma_block:
        errors.append("chroma service 应复用 Docker 日志轮转配置。")
    if "\n    volumes:" not in chroma_block or ":/data" not in chroma_block:
        errors.append("chroma service 必须把持久化目录挂载到 /data。")
    if (
        "image: chromadb/chroma:" not in chroma_block
        or "chromadb/chroma:latest" in chroma_block
    ):
        errors.append("chroma service 必须使用固定版本的 chromadb/chroma 镜像。")

    for service_name in ("backend", "worker"):
        service_block = extract_compose_service_block(compose_text, service_name)
        if service_block is None:
            errors.append(f"docker-compose.yml 缺少 {service_name} service。")
            continue
        if "CHROMA_HOST:" not in service_block:
            errors.append(
                f"{service_name} 必须配置 CHROMA_HOST，"
                "通过 HTTP client 访问 Chroma。"
            )
        if re.search(
            r"^\s+-\s+[^\n]*:/app/vector_db(?:\s|$)",
            service_block,
            re.MULTILINE,
        ):
            errors.append(
                f"{service_name} 不应挂载 /app/vector_db，"
                "避免回退为多进程 embedded Chroma。"
            )
        if "\n      chroma:\n        condition: service_healthy" not in service_block:
            errors.append(f"{service_name} 必须等待 chroma service_healthy 后启动。")

    return errors


def validate_port_bindings(env: Mapping[str, str]) -> list[str]:
    """校验 compose 暴露端口默认只绑定 loopback。"""
    errors: list[str] = []
    for key in ("FRONTEND_PORT", "BACKEND_PORT", "POSTGRES_PORT"):
        value = env.get(key, "")
        if not value:
            errors.append(f"{key} 未设置，compose 默认会绑定到所有网卡。")
            continue
        if not value.startswith(LOOPBACK_PREFIXES):
            errors.append(f"{key} 必须绑定到 127.0.0.1 或 localhost，由反向代理暴露 HTTPS。")
    return errors


def resolve_host_path(value: str | None, default: str) -> Path:
    """解析 compose bind mount 的宿主路径。"""
    raw_path = value or default
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def validate_runtime_paths(
    env: Mapping[str, str],
    *,
    require_reranker: bool = False,
) -> list[str]:
    """校验生产需要持久化的宿主目录存在。"""
    errors: list[str] = []
    required_dirs = {
        "UPLOADS_DIR": resolve_host_path(env.get("UPLOADS_DIR"), "./uploads"),
        "VECTOR_DB_DIR": resolve_host_path(env.get("VECTOR_DB_DIR"), "./vector_db"),
        "MODELS_DIR": resolve_host_path(env.get("MODELS_DIR"), "./models"),
    }

    for key, path in required_dirs.items():
        if not path.exists():
            errors.append(f"{key} 指向的宿主目录不存在，请先创建并设置备份策略。")
            continue
        if not path.is_dir():
            errors.append(f"{key} 指向的宿主路径不是目录。")

    reranker_model = required_dirs["MODELS_DIR"] / "rerankers/bge-reranker-base"
    if (
        require_reranker
        and required_dirs["MODELS_DIR"].exists()
        and not reranker_model.exists()
    ):
        errors.append("MODELS_DIR 缺少 reranker 模型目录 rerankers/bge-reranker-base。")

    return errors


def run_external_check(
    name: str,
    command: Sequence[str],
    env: Mapping[str, str],
) -> ExternalCheck:
    """运行外部检查命令，不回显 stdout/stderr，避免泄露 secret。"""
    child_env = os.environ.copy()
    child_env.update(env)
    try:
        subprocess.run(
            list(command),
            cwd=PROJECT_ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        return ExternalCheck(
            name=name,
            success=False,
            message=f"{name} 命令不可用，请确认依赖已安装。",
        )
    except subprocess.CalledProcessError:
        return ExternalCheck(
            name=name,
            success=False,
            message=f"{name} 未通过，请在受控终端手动运行对应命令查看详情。",
        )
    return ExternalCheck(name=name, success=True, message=f"{name} 已通过。")


def run_compose_check(env: Mapping[str, str]) -> ExternalCheck:
    """执行 Docker Compose 配置检查。"""
    return run_external_check(
        "Docker Compose config",
        ("docker", "compose", "config", "--quiet"),
        env,
    )


def parse_compose_ps_records(output: str) -> list[Mapping[str, object]]:
    """解析 docker compose ps --format json 的对象或逐行 JSON 输出。"""
    stripped = output.strip()
    if not stripped:
        return []

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        records: list[Mapping[str, object]] = []
        for line in stripped.splitlines():
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
        return records

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [value for value in payload if isinstance(value, dict)]
    return []


def run_chroma_runtime_health_check(env: Mapping[str, str]) -> ExternalCheck:
    """确认 Compose Chroma 容器正在运行且 Docker health 为 healthy。"""
    child_env = os.environ.copy()
    child_env.update(env)
    name = "Chroma runtime health"
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json", "chroma"],
            cwd=PROJECT_ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        return ExternalCheck(
            name=name,
            success=False,
            message="Chroma runtime health 命令不可用，请确认 Docker 已安装。",
        )
    except subprocess.CalledProcessError:
        return ExternalCheck(
            name=name,
            success=False,
            message="Chroma runtime health 未通过，请检查 docker compose ps chroma。",
        )

    try:
        records = parse_compose_ps_records(result.stdout)
    except json.JSONDecodeError:
        records = []
    if not records:
        return ExternalCheck(
            name=name,
            success=False,
            message="Chroma service 未运行；请先执行 docker compose up -d --build。",
        )

    record = records[0]
    state = str(record.get("State") or "").strip().lower()
    health = str(record.get("Health") or "").strip().lower()
    if state != "running" or health != "healthy":
        return ExternalCheck(
            name=name,
            success=False,
            message="Chroma service 未处于 running/healthy 状态，请检查容器日志。",
        )
    return ExternalCheck(
        name=name,
        success=True,
        message="Chroma runtime health 已通过。",
    )


def run_migration_dry_run(
    env: Mapping[str, str],
    env_file: Path,
    conda_env: str,
    method: str,
) -> ExternalCheck:
    """执行生产 migration dry-run。"""
    if method == "local":
        return run_external_check(
            "Migration dry-run",
            (
                "conda",
                "run",
                "-n",
                conda_env,
                "python",
                "scripts/migrate_db.py",
                "--dry-run",
                "--env-file",
                str(env_file),
            ),
            env,
        )

    return run_external_check(
        "Migration dry-run",
        (
            "docker",
            "compose",
            "run",
            "--rm",
            "migrate",
            "python",
            "/app/scripts/migrate_db.py",
            "--dry-run",
        ),
        env,
    )


def print_errors(title: str, errors: Sequence[str]) -> None:
    """按分组输出失败原因。"""
    if not errors:
        print(f"[pass] {title}")
        return

    print(f"[fail] {title}")
    for error in errors:
        print(f"  - {error}")


def run(args: argparse.Namespace) -> int:
    """执行生产 preflight。"""
    try:
        env = build_runtime_env(args.env_file)
    except FileNotFoundError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1

    groups = [
        ("Required secret settings", validate_secret_settings(env)),
        (
            "Optional provider settings",
            validate_optional_provider_settings(
                env,
                require_provider_keys=args.require_provider_keys,
            ),
        ),
        ("Database settings", validate_database_settings(env)),
        ("Redis settings", validate_redis_settings(env)),
        ("Redis Compose service", validate_compose_redis_service()),
        ("Chroma settings", validate_chroma_settings(env)),
        ("Chroma Compose service", validate_compose_chroma_service()),
        ("Port bindings", validate_port_bindings(env)),
    ]
    if not args.skip_path_check:
        groups.append((
            "Persistent directories",
            validate_runtime_paths(
                env,
                require_reranker=args.require_reranker,
            ),
        ))

    failed = False
    for title, errors in groups:
        print_errors(title, errors)
        failed = failed or bool(errors)

    external_checks: list[ExternalCheck] = []
    if not args.skip_compose_check:
        external_checks.append(run_compose_check(env))
    if args.check_runtime_health:
        external_checks.append(run_chroma_runtime_health_check(env))
    if not args.skip_migration_dry_run:
        external_checks.append(
            run_migration_dry_run(
                env,
                args.env_file,
                args.conda_env,
                args.migration_method,
            )
        )

    for check in external_checks:
        status = "pass" if check.success else "fail"
        print(f"[{status}] {check.message}")
        failed = failed or not check.success

    if failed:
        print("Production preflight failed.")
        return 1

    print("Production preflight passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
