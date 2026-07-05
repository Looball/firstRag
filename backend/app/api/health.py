"""系统基础设施健康检查接口。"""

from fastapi import APIRouter

from app.services.redis_service import check_redis_health


router = APIRouter(tags=["health"])


@router.get("/health")
def get_system_health() -> dict[str, object]:
    """返回后端进程和可选基础设施的安全健康摘要。"""
    redis_health = check_redis_health()
    app_status = "healthy" if redis_health.is_healthy else "degraded"
    return {
        "success": True,
        "status": app_status,
        "dependencies": {
            "redis": redis_health.to_dict(),
        },
    }
