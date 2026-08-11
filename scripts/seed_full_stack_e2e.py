"""为隔离的全栈 E2E 用户写入本地 provider 与检索设置。"""

from __future__ import annotations

import argparse
from urllib.parse import urlparse

from app.core.secret_cipher import build_secret_hint, encrypt_secret
from app.repositories.auth_repository import get_user_by_username
from app.repositories.knowledge_base_repository import (
    get_default_knowledge_base_id,
)
from app.repositories.retrieval_settings_repository import (
    DEFAULT_RETRIEVAL_SETTINGS,
    upsert_knowledge_base_retrieval_settings,
)
from app.repositories.user_embedding_provider_credential_repository import (
    upsert_user_embedding_provider_credential,
)
from app.repositories.user_embedding_settings_repository import (
    upsert_user_embedding_settings,
)
from app.repositories.user_llm_provider_credential_repository import (
    upsert_user_llm_provider_credential,
)
from app.repositories.user_llm_settings_repository import (
    upsert_user_llm_settings,
)


E2E_PROVIDER = "openai_compatible"
E2E_MODEL = "firstrag-e2e-model"
E2E_API_KEY = "firstrag-e2e-only-key"


def parse_args() -> argparse.Namespace:
    """解析 E2E seed 参数。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--provider-base-url",
        default="http://provider-stub:8080/v1",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=16,
    )
    return parser.parse_args()


def validate_e2e_provider_base_url(value: str) -> str:
    """只允许指向隔离 Compose 网络中的固定 provider stub。"""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "provider-stub"
        or parsed.port != 8080
        or parsed.path != "/v1"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "全栈 E2E provider 必须是 http://provider-stub:8080/v1"
        )
    return normalized


def seed_user_settings(
    username: str,
    provider_base_url: str,
    embedding_dimensions: int = 16,
) -> None:
    """为已注册测试用户写入隔离 provider 和强制检索设置。"""
    if embedding_dimensions <= 0:
        raise ValueError("embedding dimensions 必须大于 0")
    user = get_user_by_username(username)
    if user is None:
        raise RuntimeError("全栈 E2E 用户尚未注册")

    user_id = int(user["id"])
    ciphertext = encrypt_secret(E2E_API_KEY)
    credential = {
        "api_key_ciphertext": ciphertext,
        "api_key_hint": build_secret_hint(E2E_API_KEY),
        "encryption_key_version": 1,
    }
    llm_settings = {
        **credential,
        "credential_mode": "user",
        "provider": E2E_PROVIDER,
        "model": E2E_MODEL,
        "base_url": provider_base_url,
        "temperature": 0.0,
        "max_tokens": 256,
        "timeout_seconds": 10.0,
        "max_retries": 0,
    }
    embedding_settings = {
        **credential,
        "provider": E2E_PROVIDER,
        "model": E2E_MODEL,
        "base_url": provider_base_url,
        "dimensions": embedding_dimensions,
        "timeout_seconds": 10.0,
        "max_retries": 0,
    }

    if upsert_user_llm_provider_credential(
        user_id,
        E2E_PROVIDER,
        credential,
    ) is None:
        raise RuntimeError("写入全栈 E2E LLM 凭据失败")
    if upsert_user_llm_settings(user_id, llm_settings) is None:
        raise RuntimeError("写入全栈 E2E LLM 设置失败")
    if upsert_user_embedding_provider_credential(
        user_id,
        E2E_PROVIDER,
        credential,
    ) is None:
        raise RuntimeError("写入全栈 E2E embedding 凭据失败")
    if upsert_user_embedding_settings(user_id, embedding_settings) is None:
        raise RuntimeError("写入全栈 E2E embedding 设置失败")

    knowledge_base_id = get_default_knowledge_base_id(user_id)
    if knowledge_base_id is None:
        raise RuntimeError("全栈 E2E 用户没有默认知识库")
    retrieval_settings = {
        **DEFAULT_RETRIEVAL_SETTINGS,
        "retrieval_mode": "always",
        "enable_query_router": False,
        "enable_rerank": False,
    }
    if upsert_knowledge_base_retrieval_settings(
        knowledge_base_id,
        user_id,
        retrieval_settings,
    ) is None:
        raise RuntimeError("写入全栈 E2E 检索设置失败")


def main() -> None:
    """执行全栈 E2E seed。"""
    args = parse_args()
    provider_base_url = validate_e2e_provider_base_url(
        args.provider_base_url,
    )
    seed_user_settings(
        args.username,
        provider_base_url,
        args.embedding_dimensions,
    )
    print("Full-stack E2E settings seeded.")


if __name__ == "__main__":
    main()
