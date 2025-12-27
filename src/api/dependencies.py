"""
API 依賴注入
"""

from typing import TYPE_CHECKING

from fastapi import Request, Depends, HTTPException, status

from .middleware.auth import get_current_user

if TYPE_CHECKING:
    from src.core.user_manager import UserManager
    from src.core.trigger_order_manager import TriggerOrderManager


def get_user_manager(request: Request) -> 'UserManager':
    """取得 UserManager 實例"""
    return request.app.state.user_manager


def get_trigger_manager(request: Request) -> 'TriggerOrderManager':
    """取得 TriggerOrderManager 實例"""
    return request.app.state.trigger_manager


async def get_authenticated_user(
    request: Request,
    user_id: str = Depends(get_current_user)
) -> str:
    """
    取得已認證的用戶 ID

    Args:
        request: FastAPI Request
        user_id: 從 middleware 取得的用戶 ID

    Returns:
        str: 用戶 ID
    """
    return user_id


def require_broker_config(
    user_id: str = Depends(get_authenticated_user),
    user_manager: 'UserManager' = Depends(get_user_manager)
) -> str:
    """
    要求用戶已設定券商

    Args:
        user_id: 用戶 ID
        user_manager: 用戶管理器

    Returns:
        str: 用戶 ID

    Raises:
        HTTPException: 如果未設定券商
    """
    brokers = user_manager.get_broker_names(user_id)

    if not brokers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請先在 Telegram 使用 /broker 設定券商"
        )

    return user_id
