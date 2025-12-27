"""
健康檢查路由
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health")
async def health_check(request: Request):
    """
    健康檢查

    Returns:
        dict: 健康狀態
    """
    return {
        "status": "healthy",
        "service": "trigger-order-api",
        "version": "1.0.0"
    }


@router.get("/health/ready")
async def readiness_check(request: Request):
    """
    就緒檢查

    檢查服務是否已準備好接收請求

    Returns:
        dict: 就緒狀態
    """
    # 檢查依賴服務
    user_manager = getattr(request.app.state, 'user_manager', None)
    trigger_manager = getattr(request.app.state, 'trigger_manager', None)

    ready = user_manager is not None and trigger_manager is not None

    return {
        "ready": ready,
        "dependencies": {
            "user_manager": user_manager is not None,
            "trigger_manager": trigger_manager is not None
        }
    }
