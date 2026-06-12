from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.security import get_current_user_id
from app.services.file_service import build_storage_path, calculate_file_hash
from SqlStatement.query import exe_sql


router = APIRouter(prefix="/chat", tags=["knowledge-files"])


# 向知识库上传文件
@router.post("/knowledge-base/{knowledge_base_id}/files")
async def upload_knowledge_files(
    knowledge_base_id: UUID,
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    user_id: int = Depends(get_current_user_id),
):
    # 检查知识库存在且属于当前用户
    rows = exe_sql(
        sql_statement="""
        SELECT id
        FROM knowledge_bases
        WHERE id = %s
          AND user_id = %s
          AND deleted_at IS NULL
        """,
        args_tuple=(knowledge_base_id, user_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="知识库不存在")

    uploaded_files = []

    # 使用循环处理多个文件
    for file in files:
        # 判断文件名是否存在
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        # 计算文件hash值和文件大小
        file_hash, size_bytes = await calculate_file_hash(file)

        # 同一用户上传过相同内容时，复用已有文件，只补充知识库关联
        existing_files = exe_sql(
            sql_statement="""
            SELECT id, original_name, size_bytes, status
            FROM knowledge_files
            WHERE user_id = %s
              AND file_hash = %s
              AND deleted_at IS NULL
            LIMIT 1;
            """,
            args_tuple=(user_id, file_hash),
        )

        if existing_files:
            existing_file = existing_files[0]
            relation_rows = exe_sql(
                sql_statement="""
                INSERT INTO knowledge_base_files (
                    knowledge_base_id,
                    knowledge_file_id
                )
                VALUES (%s, %s)
                ON CONFLICT (knowledge_base_id, knowledge_file_id)
                DO NOTHING
                RETURNING knowledge_file_id;
                """,
                args_tuple=(knowledge_base_id, existing_file["id"]),
            )
            uploaded_files.append({
                **dict(existing_file),
                "reused": True,
                "already_in_knowledge_base": not bool(relation_rows),
            })
            await file.close()
            continue

        # 为文件生成UUID
        file_id = uuid4()

        # 拼接文件存储路径
        storage_path = build_storage_path(
            user_id=user_id,
            file_id=str(file_id),
            file_hash=file_hash,
            original_name=file.filename,
        )

        # 创建文件目录
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存文件，写入本地路径
        try:
            with storage_path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    output.write(chunk)

            # 同时插入文件记录和知识库关联记录
            rows = exe_sql(
                sql_statement="""
                WITH new_file AS (
                    INSERT INTO knowledge_files (
                        id,
                        user_id,
                        original_name,
                        storage_path,
                        mime_type,
                        size_bytes,
                        file_hash,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id, original_name, size_bytes, status
                ),
                new_relation AS (
                    INSERT INTO knowledge_base_files (
                        knowledge_base_id,
                        knowledge_file_id
                    )
                    SELECT %s, id
                    FROM new_file
                )
                SELECT *
                FROM new_file;
                """,
                args_tuple=(
                    file_id,
                    user_id,
                    file.filename,
                    str(storage_path),
                    file.content_type or "application/octet-stream",
                    size_bytes,
                    file_hash,
                    knowledge_base_id,
                ),
            )
            uploaded_files.append(dict(rows[0]))
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

    return {
        "success": True,
        "description": description,
        "files": uploaded_files,
    }


# 获取当前用户下所有知识库文件
@router.get("/knowledge-files")
def get_all_knowledge_files(user_id: int = Depends(get_current_user_id)):
    rows = exe_sql(
        sql_statement="""
        SELECT
            kf.id,
            kf.original_name,
            kf.mime_type,
            kf.size_bytes,
            kf.status,
            kf.created_at,
            COUNT(kbf.knowledge_base_id) AS usage_count
        FROM knowledge_files AS kf
        LEFT JOIN knowledge_base_files AS kbf
          ON kbf.knowledge_file_id = kf.id
        WHERE kf.user_id = %s
          AND kf.deleted_at IS NULL
        GROUP BY
            kf.id,
            kf.original_name,
            kf.mime_type,
            kf.size_bytes,
            kf.status,
            kf.created_at
        ORDER BY kf.created_at DESC;
        """,
        args_tuple=(user_id,),
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
                "usage_count": row["usage_count"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
    }
