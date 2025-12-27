"""
API Key 認證中介軟體
"""

import logging
from typing import Optional, Tuple

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger('APIAuth')

# API Key Header 定義
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key 驗證中介軟體"""

    def __init__(self, app, user_manager, exclude_paths: list = None):
        """
        初始化

        Args:
            app: FastAPI 應用
            user_manager: 用戶管理器
            exclude_paths: 不需要驗證的路徑列表
        """
        super().__init__(app)
        self.user_manager = user_manager
        self.exclude_paths = exclude_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
        ]

    async def dispatch(self, request: Request, call_next):
        """處理請求"""
        # 檢查是否需要驗證
        path = request.url.path

        # 排除不需要驗證的路徑
        if any(path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # 取得 API Key
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return self._unauthorized_response("Missing API Key")

        # 驗證 API Key
        user_id = self.user_manager.get_user_by_api_key(api_key)

        if not user_id:
            return self._unauthorized_response("Invalid API Key")

        # 將用戶 ID 存入 request state
        request.state.user_id = user_id
        request.state.api_key = api_key

        return await call_next(request)

    def _unauthorized_response(self, detail: str):
        """回傳未授權響應"""
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthorized",
                "message": detail
            },
            headers={"WWW-Authenticate": "X-API-Key"}
        )


async def get_current_user(request: Request) -> str:
    """
    取得當前用戶 ID

    從 request.state 取得經過驗證的用戶 ID

    Args:
        request: FastAPI Request

    Returns:
        str: 用戶 ID (chat_id)

    Raises:
        HTTPException: 如果未經驗證
    """
    user_id = getattr(request.state, 'user_id', None)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "X-API-Key"}
        )

    return user_id


def verify_api_key(api_key: str, user_manager) -> Optional[str]:
    """
    驗證 API Key

    Args:
        api_key: API Key
        user_manager: 用戶管理器

    Returns:
        str: 用戶 ID，驗證失敗返回 None
    """
    if not api_key:
        return None

    return user_manager.get_user_by_api_key(api_key)
