#!/usr/bin/env python3
"""FirstRAG 生产部署前置检查入口。"""

from __future__ import annotations

import argparse
import base64
import binascii
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

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
    "replace-with-a-fernet-key",
}

LOOPBACK_PREFIXES = ("127.0.0.1:", "localhost:")


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
        "--require-provider-keys",
        action="store_true",
        help=(
            "Require LLM and embedding provider keys. Use before public smoke "
            "tests; omit it when booting first and configuring providers later."
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


def validate_optional_provider_settings(
    env: Mapping[str, str],
    *,
    require_provider_keys: bool = False,
) -> list[str]:
    """校验可后配置的 LLM 与 embedding provider Key。"""
    errors: list[str] = []

    llm_api_key = env.get("LLM_API_KEY")
    deepseek_api_key = env.get("DEEPSEEK_API_KEY")
    if has_configured_value(llm_api_key) and is_placeholder(llm_api_key):
        errors.append("LLM_API_KEY 仍是占位值，请留空或替换为真实 provider Key。")
    if has_configured_value(deepseek_api_key) and is_placeholder(deepseek_api_key):
        errors.append("DEEPSEEK_API_KEY 仍是占位值，请留空或替换为真实 provider Key。")
    if require_provider_keys and not (
        has_configured_value(llm_api_key) or has_configured_value(deepseek_api_key)
    ):
        errors.append("公开 smoke test 前需要配置 LLM_API_KEY 或 DEEPSEEK_API_KEY。")

    embedding_key = env.get("ZAI_EMD_API")
    if has_configured_value(embedding_key):
        if is_placeholder(embedding_key):
            errors.append("ZAI_EMD_API 仍是占位值，请留空或替换为真实 embedding Key。")
        elif len(embedding_key.strip()) < 12:
            errors.append("ZAI_EMD_API 长度过短，请确认是否为真实 embedding Key。")
    elif require_provider_keys:
        errors.append("公开 smoke test 前需要配置 ZAI_EMD_API。")

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
