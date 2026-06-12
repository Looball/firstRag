from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user_id
from app.schemas.knowledge import CreateKnowledgeBaseRequest
from SqlStatement.query import exe_sql


router = APIRouter(prefix="/chat", tags=["knowledge-bases"])


# 获取用户的知识库
@router.get("/knowledge-bases")
def get_knowledge_bases(user_id: int = Depends(get_current_user_id)):
    # 查询当前用户未删除的知识库及文件数量
    rows = exe_sql(
        sql_statement="""
        SELECT
            kb.id,
            kb.name,
            kb.is_default,
            kb.created_at,
            kb.updated_at,
            COUNT(kbf.knowledge_file_id) AS file_count
        FROM knowledge_bases AS kb
        LEFT JOIN knowledge_base_files AS kbf
          ON kbf.knowledge_base_id = kb.id
        WHERE kb.user_id = %s
          AND kb.deleted_at IS NULL
        GROUP BY
            kb.id,
            kb.name,
            kb.is_default,
            kb.created_at,
            kb.updated_at
        ORDER BY kb.is_default DESC, kb.created_at ASC;
        """,
        args_tuple=(user_id,),
    )
    return {
        "success": True,
        "knowledge_bases": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "is_default": row["is_default"],
                "file_count": row["file_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
    }


# 新建知识库
@router.post("/knowledge-base")
def create_knowledge_base(
    req: CreateKnowledgeBaseRequest,
    user_id: int = Depends(get_current_user_id),
):
    # 去除知识库名称首尾空格
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")

    # 创建知识库
    rows = exe_sql(
        sql_statement="""
        INSERT INTO knowledge_bases (user_id, name, is_default)
        VALUES (%s, %s, FALSE)
        RETURNING id, name, is_default, created_at, updated_at;
        """,
        args_tuple=(user_id, name),
    )
    knowledge_base = rows[0]
    return {
        "success": True,
        "knowledge_base": {
            "id": str(knowledge_base["id"]),
            "name": knowledge_base["name"],
            "is_default": knowledge_base["is_default"],
            "file_count": 0,
            "created_at": knowledge_base["created_at"],
            "updated_at": knowledge_base["updated_at"],
        },
    }


# 获取当前知识库的文件信息
@router.get("/knowledge-base/{knowledge_base_id}/files")
def get_knowledge_base_files(
    knowledge_base_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    rows = exe_sql(
        sql_statement="""
        SELECT
            kf.id,
            kf.original_name,
            kf.mime_type,
            kf.size_bytes,
            kf.status,
            kf.created_at,
            kf.updated_at
        FROM knowledge_base_files AS kbf
        JOIN knowledge_bases AS kb
          ON kb.id = kbf.knowledge_base_id
        JOIN knowledge_files AS kf
          ON kf.id = kbf.knowledge_file_id
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.user_id = %s
          AND kf.deleted_at IS NULL
        ORDER BY kbf.created_at DESC;
        """,
        args_tuple=(knowledge_base_id, user_id, user_id),
    )
    return {
        "success": True,
        "files": [
            {
                "id": str(row["id"]),
                "original_name": row["original_name"],
                "mime_type": row["mime_type"],
                "size_bytes": row["size_bytes"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ],
    }


# 解除数据库与文件的关联
@router.delete("/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}")
def remove_file_from_knowledge_base(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    # 解除关联
    rows = exe_sql(
        sql_statement="""
        DELETE FROM knowledge_base_files AS kbf
        USING knowledge_bases AS kb, knowledge_files AS kf
        WHERE kbf.knowledge_base_id = kb.id
          AND kbf.knowledge_file_id = kf.id
          AND kb.id = %s
          AND kf.id = %s
          AND kb.user_id = %s
          AND kf.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.deleted_at IS NULL
        RETURNING kbf.knowledge_base_id, kbf.knowledge_file_id;
        """,
        args_tuple=(
            knowledge_base_id,
            knowledge_file_id,
            user_id,
            user_id,
        ),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="文件关联不存在")

    return {
        "success": True,
        "knowledge_base_id": str(knowledge_base_id),
        "knowledge_file_id": str(knowledge_file_id),
    }


# 增加文件和知识库的关联
@router.post("/knowledge-base/{knowledge_base_id}/files/{knowledge_file_id}")
def add_file_to_knowledge_base(
    knowledge_base_id: UUID,
    knowledge_file_id: UUID,
    user_id: int = Depends(get_current_user_id),
):
    # 仅为属于当前用户且未删除的知识库和文件建立关联
    rows = exe_sql(
        sql_statement="""
        INSERT INTO knowledge_base_files (
            knowledge_base_id,
            knowledge_file_id
        )
        SELECT kb.id, kf.id
        FROM knowledge_bases AS kb
        CROSS JOIN knowledge_files AS kf
        WHERE kb.id = %s
          AND kb.user_id = %s
          AND kb.deleted_at IS NULL
          AND kf.id = %s
          AND kf.user_id = %s
          AND kf.deleted_at IS NULL
        ON CONFLICT (knowledge_base_id, knowledge_file_id)
        DO NOTHING
        RETURNING knowledge_base_id, knowledge_file_id, created_at;
        """,
        args_tuple=(
            knowledge_base_id,
            user_id,
            knowledge_file_id,
            user_id,
        ),
    )
    # 可能是资源不存在，也可能已经关联
    if not rows:
        check_rows = exe_sql(
            sql_statement="""
            SELECT 1
            FROM knowledge_base_files
            WHERE knowledge_base_id = %s
              AND knowledge_file_id = %s;
            """,
            args_tuple=(knowledge_base_id, knowledge_file_id),
        )
        if check_rows:
            return {
                "success": True,
                "already_exists": True,
                "message": "文件已经关联到该知识库",
                "knowledge_base_id": str(knowledge_base_id),
                "knowledge_file_id": str(knowledge_file_id),
            }
        raise HTTPException(status_code=404, detail="知识库或文件不存在")

    relation = rows[0]
    return {
        "success": True,
        "already_exists": False,
        "message": "文件关联成功",
        "knowledge_base_id": str(relation["knowledge_base_id"]),
        "knowledge_file_id": str(relation["knowledge_file_id"]),
        "created_at": relation["created_at"],
    }
