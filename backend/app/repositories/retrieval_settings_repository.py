from decimal import Decimal
from uuid import UUID

from app.db.executor import Row, fetch_one


DEFAULT_RETRIEVAL_SETTINGS = {
    "retrieval_mode": "auto",
    "enable_query_router": True,
    "enable_rerank": True,
    "top_k": 5,
    "vector_top_k": 20,
    "fulltext_top_k": 20,
    "rrf_k": 20,
    "rerank_score_threshold": 0.0,
}


def serialize_retrieval_settings(row: Row | None) -> dict:
    """将数据库行转换为稳定的检索设置结构，缺失时使用默认值。"""
    settings = dict(DEFAULT_RETRIEVAL_SETTINGS)
    if row is None:
        return settings

    for key in DEFAULT_RETRIEVAL_SETTINGS:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, Decimal):
            value = float(value)
        settings[key] = value

    return settings


def get_knowledge_base_retrieval_settings(
    knowledge_base_id: UUID,
    user_id: int,
) -> dict | None:
    """读取当前用户某个知识库的检索设置，未配置时返回默认值。"""
    row = fetch_one(
        """
        SELECT
            kb.id AS knowledge_base_id,
            COALESCE(s.retrieval_mode, 'auto') AS retrieval_mode,
            COALESCE(s.enable_query_router, TRUE) AS enable_query_router,
            COALESCE(s.enable_rerank, TRUE) AS enable_rerank,
            COALESCE(s.top_k, 5) AS top_k,
            COALESCE(s.vector_top_k, 20) AS vector_top_k,
            COALESCE(s.fulltext_top_k, 20) AS fulltext_top_k,
            COALESCE(s.rrf_k, 20) AS rrf_k,
            COALESCE(s.rerank_score_threshold, 0.000)
                AS rerank_score_threshold
        FROM knowledge_bases AS kb
        LEFT JOIN knowledge_base_retrieval_settings AS s
          ON s.knowledge_base_id = kb.id
         AND s.user_id = kb.user_id
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL;
        """,
        (knowledge_base_id, user_id),
    )
    if row is None:
        return None
    return serialize_retrieval_settings(row)


def upsert_knowledge_base_retrieval_settings(
    knowledge_base_id: UUID,
    user_id: int,
    settings: dict,
) -> dict | None:
    """保存当前用户某个知识库的检索设置。"""
    row = fetch_one(
        """
        INSERT INTO knowledge_base_retrieval_settings (
            knowledge_base_id,
            user_id,
            retrieval_mode,
            enable_query_router,
            enable_rerank,
            top_k,
            vector_top_k,
            fulltext_top_k,
            rrf_k,
            rerank_score_threshold
        )
        SELECT
            kb.id,
            kb.user_id,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        FROM knowledge_bases AS kb
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
        ON CONFLICT (knowledge_base_id)
        DO UPDATE SET
            retrieval_mode = EXCLUDED.retrieval_mode,
            enable_query_router = EXCLUDED.enable_query_router,
            enable_rerank = EXCLUDED.enable_rerank,
            top_k = EXCLUDED.top_k,
            vector_top_k = EXCLUDED.vector_top_k,
            fulltext_top_k = EXCLUDED.fulltext_top_k,
            rrf_k = EXCLUDED.rrf_k,
            rerank_score_threshold = EXCLUDED.rerank_score_threshold,
            updated_at = now()
        RETURNING
            knowledge_base_id,
            retrieval_mode,
            enable_query_router,
            enable_rerank,
            top_k,
            vector_top_k,
            fulltext_top_k,
            rrf_k,
            rerank_score_threshold;
        """,
        (
            settings["retrieval_mode"],
            settings["enable_query_router"],
            settings["enable_rerank"],
            settings["top_k"],
            settings["vector_top_k"],
            settings["fulltext_top_k"],
            settings["rrf_k"],
            settings["rerank_score_threshold"],
            knowledge_base_id,
            user_id,
        ),
    )
    if row is None:
        return None
    return serialize_retrieval_settings(row)
